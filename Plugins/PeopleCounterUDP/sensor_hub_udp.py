#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sensor_hub_udp.py
Hub multi-sensore RealSense con:
- auto-discovery dinamico dei device
- stream warm (depth+color)
- snapshot "on timer" o via comando UDP
- pre-process depth->pseudo-color (JET) opzionale (per modelli allenati su depth)
- inferenza batch YOLOv8 (classe: person)
- invio risultati UDP/JSON a UE (data-port) + ricezione comandi (cmd-port)

Esempi:
python sensor_hub_udp.py --model=yolov8_topview.pt --use-depth-input \
  --udp-host=192.168.1.50 --data-port=7777 --cmd-port=7780 --interval=1.0
"""

import argparse, json, socket, struct, sys, threading, time, queue, signal
from typing import Dict, List, Tuple
import numpy as np
import cv2
from pathlib import Path

# RealSense
import pyrealsense2 as rs

# YOLO (Ultralytics)
try:
    from ultralytics import YOLO
except Exception as e:
    YOLO = None

###############################################################################
# Utility
###############################################################################

def make_colormap_jet_from_depth(depth_z16: np.ndarray, clip_min_mm: int = 300, clip_max_mm: int = 4500) -> np.ndarray:
    """Converte depth 16-bit (millimetri) in BGR 8-bit con COLORMAP_JET."""
    depth = depth_z16.astype(np.float32)
    depth = np.clip(depth, clip_min_mm, clip_max_mm)
    depth = (depth - clip_min_mm) / float(clip_max_mm - clip_min_mm)
    depth = (1.0 - depth)  # vicino->valori alti (più "caldo")
    depth8 = (depth * 255.0).astype(np.uint8)
    colored = cv2.applyColorMap(depth8, cv2.COLORMAP_JET)  # BGR
    return colored

def now_ts() -> float:
    return time.time()

def auto_calibrate_depth_percentiles(depth_frames: List[np.ndarray],
                                     p_low: float = 5.0,
                                     p_high: float = 95.0) -> Tuple[int, int]:
    """
    Calibra (min,max) su più frame di depth usando percentili per ignorare outlier.
    Ritorna valori in millimetri (int).
    """
    if not depth_frames:
        return 400, 3500
    # concatena solo valori validi > 0
    vals = np.concatenate([df[df > 0].ravel() for df in depth_frames if df is not None])
    if vals.size < 100:
        return 400, 3500
    dmin = int(np.percentile(vals, p_low))
    dmax = int(np.percentile(vals, p_high))
    # sicurezza: mai invertiti e con margine minimo
    if dmax <= dmin:
        dmin, dmax = 400, 3500
    return dmin, dmax


###############################################################################
# RealSense Manager
###############################################################################

class RealSenseManager:
    """Gestisce auto-discovery, apertura pipeline e snapshot sincronizzati."""
    def __init__(self, use_depth_input: bool, width: int = 640, height: int = 480, fps: int = 30):
        self.use_depth_input = use_depth_input
        self.w, self.h, self.fps = width, height, fps
        self.lock = threading.RLock()
        self.running = True
        self.ctx = rs.context()
        self.devices: Dict[str, Dict] = {}  # serial -> {pipeline, align, profile, color_frame, depth_frame}
        self.discovery_thread = threading.Thread(target=self._discovery_loop, daemon=True)
        self.discovery_thread.start()

    def _open_device(self, serial: str):
        pipeline = rs.pipeline(self.ctx)
        cfg = rs.config()
        cfg.enable_device(serial)
        # Stream depth + color
        cfg.enable_stream(rs.stream.depth, self.w, self.h, rs.format.z16, self.fps)
        cfg.enable_stream(rs.stream.color, self.w, self.h, rs.format.bgr8, self.fps)
        profile = pipeline.start(cfg)
        align = rs.align(rs.stream.color)  # allinea depth->color
        self.devices[serial] = {
            "pipeline": pipeline,
            "align": align,
            "profile": profile,
            "last_frames": None,
        }

    def _close_device(self, serial: str):
        try:
            d = self.devices.pop(serial, None)
            if d:
                d["pipeline"].stop()
        except Exception:
            pass

    def _discovery_loop(self):
        known = set()
        while self.running:
            try:
                current = set([d.get_info(rs.camera_info.serial_number) for d in self.ctx.query_devices()])
                # Aggiungi nuovi
                for serial in current - known:
                    try:
                        self._open_device(serial)
                    except Exception as e:
                        # log minimale
                        print(f"[RS] open {serial} failed: {e}", flush=True)
                # Rimuovi disconnessi
                for serial in known - current:
                    self._close_device(serial)
                known = current
            except Exception as e:
                print(f"[RS] discovery err: {e}", flush=True)
            time.sleep(1.0)

    def list_serials(self) -> List[str]:
        with self.lock:
            return list(self.devices.keys())

    def capture_all(self) -> Dict[str, Dict[str, np.ndarray]]:
        """Ritorna frames allineati per ogni device: {'serial': {'color':..., 'depth':...}}"""
        out = {}
        with self.lock:
            for serial, d in list(self.devices.items()):
                try:
                    frames = d["pipeline"].wait_for_frames(timeout_ms=200)
                    frames = d["align"].process(frames)
                    depth = frames.get_depth_frame()
                    color = frames.get_color_frame()
                    if not depth or not color:
                        continue
                    depth_np = np.asanyarray(depth.get_data())
                    color_np = np.asanyarray(color.get_data())
                    out[serial] = {"depth": depth_np, "color": color_np}
                except Exception as e:
                    print(f"[RS] capture {serial} err: {e}", flush=True)
                    # se fallisce riprova al prossimo giro
        return out

    def shutdown(self):
        self.running = False
        self.discovery_thread.join(timeout=2.0)
        with self.lock:
            for serial in list(self.devices.keys()):
                self._close_device(serial)

###############################################################################
# YOLO Inference
###############################################################################

class PeopleDetector:
    def __init__(self, model_path: str, conf: float = 0.55, device: str = None):
        if YOLO is None:
            raise RuntimeError("Ultralytics non disponibile. Installa con: pip install ultralytics")
        self.model = YOLO(model_path)
        # device: None -> auto; 'cuda' o 'cpu'
        if device:
            self.model.to(device)
        self.conf = conf

    def set_conf(self, conf: float):
        self.conf = float(conf)

    def infer_batch(self, imgs_bgr: List[np.ndarray]) -> List[int]:
        """
        Ritorna la lista dei conteggi (bbox class=person) per immagini in BGR.
        """
        if not imgs_bgr:
            return []
        # Ultralytics accetta liste np.ndarray (BGR/RGB ok, gestisce internamente)
        res = self.model.predict(source=imgs_bgr, conf=self.conf, verbose=False)
        counts = []
        for r in res:
            # r.boxes.cls -> class ids; r.names -> dict; in YOLOv8 default 'person' è 0 (se singola classe, è 0)
            if r.boxes is None or r.boxes.cls is None:
                counts.append(0)
                continue
            cls = r.boxes.cls.detach().cpu().numpy().astype(int)
            # se il training è single-class 'person', conta tutte le bbox
            counts.append(int((cls == cls).sum()))  # oppure len(cls)
        return counts



    def infer_batch_full(self, imgs_bgr: List[np.ndarray]):
        """
        Ritorna (counts, plotted_bgr, boxes_list)
        - counts: lista int per immagine
        - plotted_bgr: lista np.ndarray (BGR) con bbox disegnate
        - boxes_list: lista np.ndarray (N,4) xyxy per immagine
        """
        if not imgs_bgr:
            return [], [], []
        res = self.model.predict(source=imgs_bgr, conf=self.conf, verbose=False)
        counts, plotted, boxes_all = [], [], []
        for r in res:
            n = 0
            xyxy = None
            if r.boxes is not None and r.boxes.xyxy is not None:
                xyxy = r.boxes.xyxy.detach().cpu().numpy()
                n = int(xyxy.shape[0])
            counts.append(n)
            boxes_all.append(xyxy if xyxy is not None else np.empty((0, 4)))
            plotted.append(r.plot())  # immagine BGR con bbox/label/conf
        return counts, plotted, boxes_all

###############################################################################
# UDP Server (commands) + Sender (data)
###############################################################################

class UdpEndpoints:
    def __init__(self, host: str, data_port: int, cmd_port: int):
        # Sender (data -> UE)
        self.target_addr = (host, data_port)
        self.sock_send = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_send.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

        # Receiver (UE -> commands)
        self.sock_cmd = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock_cmd.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock_cmd.bind(("0.0.0.0", cmd_port))
        self.cmd_q = queue.Queue()
        self.running = True
        self.rx_thread = threading.Thread(target=self._rx_loop, daemon=True)
        self.rx_thread.start()

    def _rx_loop(self):
        while self.running:
            try:
                data, addr = self.sock_cmd.recvfrom(65535)
                try:
                    s = data.decode("utf-8", errors="ignore")
                    self.cmd_q.put((s, addr))
                except Exception:
                    pass
            except Exception:
                time.sleep(0.01)

    def get_command(self, timeout: float = 0.01):
        try:
            return self.cmd_q.get(timeout=timeout)
        except queue.Empty:
            return None

    def send_json(self, payload: dict):
        data = json.dumps(payload).encode("utf-8")
        self.sock_send.sendto(data, self.target_addr)

    def shutdown(self):
        self.running = False
        try:
            self.sock_cmd.close()
        except Exception:
            pass
        try:
            self.sock_send.close()
        except Exception:
            pass
        self.rx_thread.join(timeout=1.0)

###############################################################################
# Hub Orchestrator
###############################################################################

class SensorHub:
    def __init__(self, args):
        self.args = args
        self.rs = RealSenseManager(use_depth_input=args.use_depth_input,
                                   width=args.width, height=args.height, fps=args.fps)
        self.detector = PeopleDetector(args.model, conf=args.conf, device=args.device)
        self.udp = UdpEndpoints(args.udp_host, args.data_port, args.cmd_port)
        self.interval = args.interval
        self.use_depth_input = args.use_depth_input
        self.schema = "people_count_v1"
        self.running = True

        self.depth_min = args.depth_min_mm
        self.depth_max = args.depth_max_mm
        self.save_frames = args.save_frames
        self.session_total = 0
        self.save_root = Path(args.save_dir)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.save_root / f"session_{ts}"
        self.auto_depth = args.auto_depth
        self.auto_depth_plow = args.auto_depth_plow
        self.auto_depth_phigh = args.auto_depth_phigh
        self.auto_depth_refresh = args.auto_depth_refresh_sec
        self._last_auto_depth_ts = 0.0
        self._did_initial_autodepth = False
        if self.save_frames:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            # log per sessione
            (self.session_dir / "events.ndjson").write_text("", encoding="utf-8")

    #

    # Prepara input per YOLO (lista immagini BGR)


    def _prepare_inputs(self, frames: Dict[str, Dict[str, np.ndarray]]) -> Tuple[List[str], List[np.ndarray]]:
        serials, imgs = [], []

        for serial, fd in frames.items():
            if self.use_depth_input:
                d = fd["depth"].astype(np.float32)

                # 1) fix valori invalidi (0, nan, inf) -> li porto al massimo (sfondo)
                invalid = ~np.isfinite(d) | (d <= 0)
                if invalid.any():
                    # stima dello sfondo: mediana dei validi
                    bg = np.median(d[~invalid]) if np.any(~invalid) else (
                        self.depth_max if self.depth_max > self.depth_min else 4000.0)
                    d[invalid] = bg

                # 2) leggero denoise (riduce speckle)
                d = cv2.medianBlur(d, 3)

                # 3) normalizzazione su range definito
                d_min, d_max = float(self.depth_min), float(self.depth_max)
                # fallback: se range stretto/errato, usa percentili robusti
                if d_max - d_min < 50:
                    p5, p95 = np.percentile(d, [5, 95])
                    d_min, d_max = float(p5), float(p95 if p95 > p5 else p5 + 50)

                # mappo vicino->scuro (coerente col dataset): valore basso = più vicino = nero
                d = np.clip(d, d_min, d_max)
                depth_norm = ((d - d_min) / (d_max - d_min) * 255.0)
                depth_u8 = depth_norm.astype(np.uint8)

                # opzionale: leggero smooth per uniformare il fondo
                depth_u8 = cv2.GaussianBlur(depth_u8, (3, 3), 0)

                # 4) a 3 canali (YOLO)
                img = cv2.cvtColor(depth_u8, cv2.COLOR_GRAY2BGR)
            else:
                img = fd["color"]

            # 5) resize al target del modello
            if img.shape[1] != self.args.width or img.shape[0] != self.args.height:
                img = cv2.resize(img, (self.args.width, self.args.height), interpolation=cv2.INTER_LINEAR)

            serials.append(serial)
            imgs.append(img)

        return serials, imgs

    def _tick_capture_and_send(self):
        frames = self.rs.capture_all()

        # --- AUTO DEPTH ---
        if self.auto_depth and frames:
            tnow = now_ts()

            # Fase 1: autocalibrazione iniziale (una volta, appena disponibili i primi frame)
            if not self._did_initial_autodepth:
                depth_frames = [fd["depth"] for fd in frames.values() if "depth" in fd]
                if depth_frames:
                    dmin, dmax = auto_calibrate_depth_percentiles(
                        depth_frames, self.auto_depth_plow, self.auto_depth_phigh
                    )
                    self.depth_min, self.depth_max = dmin, dmax
                    self._did_initial_autodepth = True
                    self._last_auto_depth_ts = tnow
                    print(f"[AutoDepth][init] depth_min={dmin} mm  depth_max={dmax} mm", flush=True)

            # Fase 2: refresh periodico (se richiesto)
            if self.auto_depth_refresh > 0.0 and (tnow - self._last_auto_depth_ts) >= self.auto_depth_refresh:
                depth_frames = [fd["depth"] for fd in frames.values() if "depth" in fd]
                if depth_frames:
                    dmin, dmax = auto_calibrate_depth_percentiles(
                        depth_frames, self.auto_depth_plow, self.auto_depth_phigh
                    )
                    # piccola media mobile per evitare salti bruschi
                    alpha = 0.5
                    self.depth_min = int(alpha * dmin + (1 - alpha) * self.depth_min)
                    self.depth_max = int(alpha * dmax + (1 - alpha) * self.depth_max)
                    self._last_auto_depth_ts = tnow
                    print(f"[AutoDepth][refresh] depth_min={self.depth_min}  depth_max={self.depth_max}", flush=True)
        # --- fine AUTO DEPTH ---

        serials, imgs = self._prepare_inputs(frames)

        if not imgs:
            payload = {"schema": self.schema, "type": "snapshot_counts",
                       "timestamp": now_ts(), "sensors": []}
            self.udp.send_json(payload)
            return

        counts, plotted, boxes_all = self.detector.infer_batch_full(imgs)

        # ordina per serial per stabilità
        serials_sorted = sorted(zip(serials, counts, plotted), key=lambda x: x[0])

        sensors_json = []
        for idx, (serial, c, img_anno) in enumerate(serials_sorted, start=1):
            sensors_json.append({"id": f"SENSORE{idx:03d}", "count": int(c)})

            # salvataggio frame annotato (uno per device a tick)
            if self.save_frames:
                fname = self.session_dir / f"{time.time():.3f}_{serial}_c{c}.jpg"
                cv2.imwrite(str(fname), img_anno)

        # aggiorna totale sessione
        self.session_total += sum(counts)

        payload = {"schema": self.schema, "type": "snapshot_counts",
                   "timestamp": now_ts(), "sensors": sensors_json}
        self.udp.send_json(payload)

        # log evento (append)
        if self.save_frames:
            event = {"t": now_ts(),
                     "sensors": sensors_json,
                     "session_total": int(self.session_total)}
            with (self.session_dir / "events.ndjson").open("a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _handle_command(self, s: str, addr):
        try:
            cmd = json.loads(s)
        except Exception:
            return
        t = cmd.get("cmd", "").lower()
        if t == "capture":
            self._tick_capture_and_send()
        elif t == "set_interval":
            sec = float(cmd.get("seconds", self.interval))
            self.interval = max(0.0, sec)
        elif t == "list_sensors":
            lst = self.rs.list_serials()
            payload = {
                "schema": self.schema,
                "type": "sensor_list",
                "timestamp": now_ts(),
                "serials": lst
            }
            self.udp.send_json(payload)
        elif t == "set_conf":
            conf = float(cmd.get("conf", self.detector.conf))
            self.detector.set_conf(conf)
        elif t == "toggle_depth_input":
            self.use_depth_input = bool(cmd.get("enabled", self.use_depth_input))

        elif t == "set_depth_range":
            dmin = int(cmd.get("min_mm", self.depth_min))
            dmax = int(cmd.get("max_mm", self.depth_max))
            if dmax > dmin:
                self.depth_min, self.depth_max = dmin, dmax
                print(f"[CMD] depth range set to {dmin}..{dmax} mm", flush=True)
        elif t == "set_auto_depth":
            self.auto_depth = bool(cmd.get("enabled", True))
            print(f"[CMD] auto_depth={'ON' if self.auto_depth else 'OFF'}", flush=True)

        elif t == "shutdown":
            self.running = False

    def run(self):
        next_shot = now_ts() + (self.interval if self.interval > 0 else 1e9)
        while self.running:
            # comandi
            got = self.udp.get_command(timeout=0.01)
            if got:
                s, addr = got
                self._handle_command(s, addr)

            # timer
            t = now_ts()
            if self.interval > 0 and t >= next_shot:
                self._tick_capture_and_send()
                next_shot = t + self.interval
            time.sleep(0.001)

        # graceful
        self.udp.shutdown()
        self.rs.shutdown()
        if self.save_frames:
            summary = {"ended_at": now_ts(), "session_total": int(self.session_total)}
            with (self.session_dir / "summary.json").open("w", encoding="utf-8") as f:
                json.dump(summary, f, ensure_ascii=False, indent=2)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True, help="Percorso modello YOLO (allenato top-view)")
    ap.add_argument("--device", default=None, help="Forza device (es. 'cuda' o 'cpu')")
    ap.add_argument("--use-depth-input", action="store_true", help="Usa depth pseudo-color come input (match training)")
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--conf", type=float, default=0.55)
    ap.add_argument("--udp-host", default="127.0.0.1")
    ap.add_argument("--data-port", type=int, default=7777)
    ap.add_argument("--cmd-port", type=int, default=7780)
    ap.add_argument("--interval", type=float, default=0.0, help="Intervallo auto-capture (0 = solo su comando)")
    ap.add_argument("--save-frames", action="store_true",
                    help="Salva immagini annotate con bbox durante l'esecuzione")
    ap.add_argument("--save-dir", default="test_img",
                    help="Cartella dove salvare le immagini annotate")
    ap.add_argument("--depth-min-mm", type=int, default=300,
                    help="Clip inferiore depth per pseudo-color (mm)")
    ap.add_argument("--depth-max-mm", type=int, default=4500,
                    help="Clip superiore depth per pseudo-color (mm)")
    ap.add_argument("--auto-depth", action="store_true",
                    help="Autocalibra depth_min/max dai frame di depth all'avvio")
    ap.add_argument("--auto-depth-refresh-sec", type=float, default=0.0,
                    help="Se >0, ricalibra periodicamente ogni N secondi")
    ap.add_argument("--auto-depth-plow", type=float, default=5.0,
                    help="Percentile basso per autocalibrazione (default 5)")
    ap.add_argument("--auto-depth-phigh", type=float, default=95.0,
                    help="Percentile alto per autocalibrazione (default 95)")

    args = ap.parse_args()

    hub = SensorHub(args)

    def _sigint(sig, frm):
        hub.running = False
    signal.signal(signal.SIGINT, _sigint)
    signal.signal(signal.SIGTERM, _sigint)

    hub.run()

if __name__ == "__main__":
    main()
