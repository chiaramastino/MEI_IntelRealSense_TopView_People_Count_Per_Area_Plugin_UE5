# MEI - SPOKE 4 - Intel RealSense Top-View People Count Per Area Plugin for Unreal Engine 5  

**Open multi-sensor real-time people-counting system integrating Intel RealSense depth cameras, YOLO top-view AI, and Unreal Engine 5 for interactive spatial analytics and immersive installations.**

---

## Table of Contents
- [Overview](#-overview)
- [System Architecture](#-system-architecture)
- [YOLO Top-View Model](#-yolo-top-view-model)
- [Unreal Engine Plugin Features](#-unreal-engine-plugin-features)
- [Blueprint Quick-Start](#-blueprint-quick-start)
- [Python Hub Setup](#-python-hub-setup)
- [Performance and Best Practices](#-performance-and-best-practices)
- [Privacy and Ethics](#-privacy-and-ethics)
- [Example Use Cases](#-example-use-cases)
- [Repository Structure](#-repository-structure)
- [Installation Checklist](#-installation-checklist)
- [Future Developments](#-future-developments)
- [Citation](#-citation)
- [License](#-license)

---

## Overview  

This repository provides a **modular Unreal Engine 5 plugin** and a **Python-based multi-sensor hub** for top-view people detection using Intel RealSense depth sensors.  

Originally developed within the **MEI (Museo Egizio Immersive)** project in Turin (Italy) for the **Egyptian Museum** , it enables real-time people counting and spatial aggregation across defined areas — ideal for **museums, exhibitions, smart spaces, and interactive experiences**.  

All data are anonymized (no RGB images stored or transmitted).

> **Goal:** Enable Unreal Engine 5 to interact with a distributed sensor network for responsive, data-driven immersive environments.

---

## ⚙️ System Architecture  

### Components  

| Component | Language | Role |
|------------|-----------|------|
| **Python Hub (`sensor_hub_udp.py`)** | Python 3.9 + | Manages multiple RealSense sensors, performs YOLO inferenence, and sends JSON results over UDP. |
| **Unreal Engine Plugin (`PeopleCounterUDP`)** | C++ / Blueprint | Receives and parses people-count packets, exposing Blueprint events for real-time logic. |

---

### Data Flow  

Unreal Engine  →  UDP  →  Python Hub  →  YOLOv8 inference  →  UDP  →  Unreal Engine 5.4.4

1. UE sends `{ "cmd": "capture" }` to the Hub.  
2. The Hub captures synchronized frames from all RealSense devices.  
3. YOLO top-view detects people and counts per sensor.  
4. A JSON packet is returned to UE with results only (no images).

### Example Payload

 ```{ "schema": "people_count_v1", "timestamp": 1730000000.12, "sensors": [   {"id": "SENSOR001", "count": 3}, {"id": "SENSOR002", "count": 10  ]} ```


### YOLO Top-View Model

Architecture: YOLOv8 fine-tuned for overhead (zenithal) perspective

Dataset: GOTPD-1 (Gait and Object Top-View People Detection)

Input: Depth or RGB 640×480 @ 30 fps

Output: Single class "person"

Performance: 30–60 fps (batch mode, RTX-class GPU)

Privacy: No images transmitted — only numeric counts!

Unreal Engine  5.4.4 Plugin Features

Runtime module: PeopleCounterUDP

---

### Blueprint Components:

UDPJsonReceiverComponent — listens on UDP port (e.g. 7777)

UDPJsonSenderComponent — sends commands (port 7780)

ParsePeopleCountPacket — returns TMap<FString,int32> (count per sensor)

Event: OnJsonReceived triggers logic when new data arrive

Supports: Area aggregation via DataTables (multiple sensors → one zone)

Example Blueprint: BP_PeopleManager



### Example Applications

Adaptive lighting and responsive media | Audience-triggered projections or audio | Live occupancy dashboards for exhibitions | Blueprint Quick-Start | Create Actor: BP_PeopleManager

Add Components:
1. UDPJsonReceiverComponent (Port 7777, Auto Start = OFF)
2. UDPJsonSenderComponent (Target Host = 127.0.0.1, Port 7780)

Event Graph → BeginPlay:
1. Call Start Receiver()
2. Set Timer (1 s) to send {"cmd":"capture"} periodically (you can call them with another variable in your project, for e.g.: when the audience needs to make a decision and the timer ends, you will capture their position and process data and know which area is the most "populated" and compare regions). 

On Json Received:
1. Use ParsePeopleCountPacket to get sensor IDs and counts

Aggregate and trigger scene changes

Python Hub example launch
 ```python sensor_hub_udp.py `
  --model gotpd_depth_s_topview.pt `
  --device cuda `
  --use-depth-input `
  --width 640 --height 480 `
  --conf 0.55 `
  --udp-host 127.0.0.1 `
  --data-port 7777 `
  --cmd-port 7780 `
  --interval 0.0 `
  --save-frames `
  --save-dir "[YourOwnProjectPath]\MEI_IntelRealSense_TopView_People_Count_Per_Area_Plugin_UE5\Plugins\PeopleCounterUDP\test_img" `
  --depth-min-mm 1350 `
  --depth-max-mm 1900 ```

Replace 127.0.0.1 with the IP address of the UE machine if running on separate devices.
You will see there are some depth measures. If you have your sensors at a certain height (In our case, we had 3 Intel Realsense D435 e D435i in top-view) at 3.20 m height - the model works well detecting people height included in the range 1350-1900 mm. 

### Python Hub Setup
You need to create your own environment.

Requirements
 ```python -m pip install -r requirements.txt ```
 ```Dependencies: pyrealsense2, opencv-python, ultralytics, numpy, asyncio. ```

### Main Commands
## Command	Description
 ```{"cmd":"capture"} ```	Acquire and send counts. 
 ```{"cmd":"set_interval","seconds":1.0} ```	Auto-capture every X seconds. 
 ```{"cmd":"list_sensors"} ```	Return connected sensor IDs.
 ```{"cmd":"set_conf","conf":0.6} ```	Adjust YOLO confidence.
 ```{"cmd":"toggle_depth_input","enabled":true} ```	Enable depth mode.
 ```{"cmd":"shutdown"} ```	Stop Hub gracefully.

## Performance and Best Practices
Metric	Typical Value	Note
Snapshot latency	< 100 ms	Depth stream always active
YOLO throughput	30–60 fps	Batch mode on RTX GPU
Sensors tested	Up to 20	Single machine
Protocol	UDP (JSON, UTF-8)	Lightweight and low latency
Privacy	Numeric only	No images transferred
Tips

Use batch inference to reduce GPU load.

Keep Auto Start OFF for Receiver to avoid Editor crashes.

Verify UDP ports 7777/7780 are open on both machines.

---

### Privacy and Ethics

Designed for GDPR compliance — no image storage or transmission.

Only anonymized numeric counts are shared.

Suitable for public spaces and research installations.


--- 

### Example Use Cases

Real-time visitor analytics in museums and exhibitions

Adaptive lighting and sound based on presence

Branching storytelling in interactive experiences

Behavioral and accessibility research

---


### Repository Structure
MEI\_IntelRealSense\_TopView\_People\_Count\_Per\_Area\_Plugin\_UE5/

├── .git/                       # (if using Git)

├── .vs/                        # Visual Studio cache

├── Config/                     # project INI files

├── Content/                    # Unreal assets

├── DerivedDataCache/           # UE cache

├── Plugins/

│   └── PeopleCounterUDP/

│       ├── Binaries/           # plugin build outputs

│       ├── Intermediate/       # temporary build files

│       ├── Source/             # plugin C++ source

│       ├── session\_frames/     # debug frames/snapshots

│       ├── test\_img/           # test images

│       ├── yoloenv/            # (optional) YOLO env/resources

│       ├── gotpd\_depth\_s\_topview.pt      # \*\*MODEL IN USE\*\*

│       ├── best.pt                         # alternative model (not used)

│       ├── sensor\_hub\_udp.py              # Python hub (RealSense + YOLO -> UDP)

│       ├── millumin\_router.py             # optional bridge to Millumin

│       ├── PeopleCounterUDP.uplugin       # plugin descriptor

│       ├── prepare inputs.txt             # setup notes

│       └── README.md

├── Saved/                      # autosaves, logs

├── Source/                     # project C++ (if any)

├── LICENSE

├── sensors\_mei.sln             # Visual Studio solution

├── sensors\_mei.uproject        # Unreal Engine project file

└── Docs/                       # (supporting folder we add)

    ├── D4.11\_Technical\_Guide.pdf

    └── workflow/\*.png          # workflow diagrams/images

---

### Installation Checklist
Step	Action
1. Enable PeopleCounterUDP plugin in UE (Edit → Plugins).	
2. Install Python 3.9+ and required packages.	
3. Connect Intel RealSense sensors and verify depth stream.	
4. Run the Hub with correct IP and ports.	
5. Start the Unreal scene and receive JSON counts in Blueprints.	

---

### Future Developments

1. Long-term analytics dashboard and data logging

2. Integration with DMX, Art-Net, or DALI lighting systems

3. WebSocket bridge for Unity, TouchDesigner, and Processing

4. Multi-machine sensor cluster support

---

### Citation

If you use this repository in research or exhibitions, please cite:

Chiara Mastino et al.
“MEI Intel RealSense Top-View People Counting System for Unreal Engine 5,”
Media Engineer & Immersive Developer, Ribes Digilab SRL, Turin (2025).

---

### License

MIT License — free to use, modify, and redistribute with attribution.

---

### Contributors and Acknowledgments

Core concept, Unreal integration, and documentation: Chiara Mastino

Unreal Engine plugin development and Blueprint workflows: Chiara Mastino


Thanks to the broader community contributing datasets, tools, and field insights in multi-sensor interaction and cultural heritage tech.

Contributions are welcome via issues and pull requests. Please follow standard GitHub workflows and include clear descriptions, test steps, and rationale in your PRs.


