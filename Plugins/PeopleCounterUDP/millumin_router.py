#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse, json, socket, threading, time
from typing import Dict, Tuple, Optional
from pythonosc import udp_client
from pythonosc.dispatcher import Dispatcher
from pythonosc.osc_server import BlockingOSCUDPServer

def udp_json_listener(bind_port:int, on_msg):
    """Ascolta JSON dall'hub (snapshot_counts)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("0.0.0.0", bind_port))
    sock.settimeout(0.25)
    while True:
        try:
            data, _ = sock.recvfrom(65535)
            try:
                payload = json.loads(data.decode("utf-8", errors="ignore"))
                on_msg(payload)
            except Exception:
                pass
        except socket.timeout:
            pass

class Router:
    def __init__(self, args):
        self.args = args
        self.last_snapshot: Optional[Dict] = None
        self.hub_cmd_addr = (args.hub_host, args.cmd_port)
        self.hub_cmd_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.millumin = udp_client.SimpleUDPClient(args.millumin_host, args.millumin_port)

    def on_snapshot(self, payload: Dict):
        if payload.get("type") == "snapshot_counts":
            self.last_snapshot = payload

    def _send_capture(self):
        cmd = {"cmd": "capture"}
        self.hub_cmd_sock.sendto(json.dumps(cmd).encode("utf-8"), self.hub_cmd_addr)

    def _pick_suffix(self, snapshot: Dict) -> Optional[str]:
        # snapshot["sensors"] = [{"id":"SENSORE001","count":N}, ...]
        counts = {s["id"]: int(s.get("count",0)) for s in snapshot.get("sensors", [])}
        # ordine di priorità in caso di pari
        rank = [("SENSORE001","a"), ("SENSORE002","b"), ("SENSORE003","c")]
        best = None; best_cnt = -1; best_suffix = None
        for sid, suf in rank:
            c = counts.get(sid,0)
            if c > best_cnt:
                best, best_cnt, best_suffix = sid, c, suf
        return best_suffix

    def _launch_on_millumin(self, column_name: str):
        # Path OSC standard di Millumin per lanciare una colonna per nome
        # (se preferisci per indice, cambia path/argomento)
        self.millumin.send_message("/millumin/action/launchColumn", column_name)
        print(f"[OSC -> Millumin] launchColumn '{column_name}'")

    # --- handler chiamato da OSC quando una scena termina ---
    def on_scene_ended(self, addr, *args):
        try:
            base_scene = str(args[0])  # "1" / "2" / "3"
        except Exception:
            return
        print(f"[Router] Scene '{base_scene}' ended → CAPTURE")
        self._send_capture()

        # attendi il prossimo snapshot fresco
        t0 = time.time()
        snap = None
        while time.time()-t0 < 3.0:  # timeout 3s
            if self.last_snapshot and self.last_snapshot.get("timestamp",0) >= t0:
                snap = self.last_snapshot
                break
            time.sleep(0.02)

        if not snap:
            print("[Router] Nessun snapshot ricevuto in tempo.")
            return

        suf = self._pick_suffix(snap)
        if not suf:
            print("[Router] Nessun sensore valido nello snapshot.")
            return

        target = f"{base_scene}{suf}"   # es: "1b"
        print(f"[Router] winner → '{target}'  sensors={snap.get('sensors')}")
        if self.args.send_to_millumin:
            self._launch_on_millumin(target)
        else:
            print("[Router] --send-to-millumin non attivo: niente OSC inviato.")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hub-host", default="127.0.0.1", help="IP dell'hub (Windows) per inviare i comandi")
    ap.add_argument("--data-port", type=int, default=7777, help="Porta su cui l'hub invia i snapshot_counts")
    ap.add_argument("--cmd-port",  type=int, default=7780, help="Porta comandi dell'hub")
    ap.add_argument("--osc-in-port", type=int, default=5001, help="Porta dove riceviamo /router/sceneEnded da Millumin")
    ap.add_argument("--millumin-host", default="127.0.0.1")
    ap.add_argument("--millumin-port", type=int, default=5000)
    ap.add_argument("--send-to-millumin", action="store_true", help="Se attivo, manda l'OSC a Millumin")
    args = ap.parse_args()

    router = Router(args)

    # thread listener JSON dall'hub
    t = threading.Thread(target=udp_json_listener, args=(args.data_port, router.on_snapshot), daemon=True)
    t.start()

    # server OSC per messaggi da Millumin
    disp = Dispatcher()
    disp.map("/router/sceneEnded", router.on_scene_ended)  # es.: /router/sceneEnded "1"
    server = BlockingOSCUDPServer(("0.0.0.0", args.osc_in_port), disp)
    print(f"[Router] pronto. OSC in : {args.osc_in_port}  | Millumin: {args.millumin_host}:{args.millumin_port}")
    print(f"[Router] invia a hub Windows cmd-port {args.cmd_port} e ascolta data-port {args.data_port}")
    server.serve_forever()

if __name__ == "__main__":
    main()
