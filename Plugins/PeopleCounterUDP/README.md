\# PeopleCounterUDP (UE 5.4.4)



\## Build

\- Copia la cartella `PeopleCounterUDP` in `YourProject/Plugins/`

\- Apri il progetto con Unreal 5.4.4, consenti la build del plugin.



\## Python Hub

\- `pip install pyrealsense2 ultralytics opencv-python numpy`

\- Esegui:

&nbsp; - Depth pseudo-color (modello allenato su depth):

&nbsp;   ```

&nbsp;   python sensor\_hub\_udp.py --model=yolov8\_topview.pt --use-depth-input \\

&nbsp;     --udp-host=127.0.0.1 --data-port=7777 --cmd-port=7780 --interval=0.0

&nbsp;   ```

&nbsp; - RGB (modello allenato su RGB):

&nbsp;   ```

&nbsp;   python sensor\_hub\_udp.py --model=yolov8\_topview\_rgb.pt \\

&nbsp;     --udp-host=127.0.0.1

&nbsp;   ```



\## Blueprint Setup

1\. Aggiungi in scena un Actor (es. `BP\_PeopleManager`)

2\. Aggiungi componenti:

&nbsp;  - `UDPJsonReceiverComponent`: `ListenPort=7777` (bAutoStart=true)

&nbsp;  - `UDPJsonSenderComponent`: `TargetHost=<ip hub>`, `TargetPort=7780`

3\. `BeginPlay`:

&nbsp;  - (opzionale) `SendJsonString("{\\"cmd\\":\\"set\_interval\\",\\"seconds\\":1.0}")`

&nbsp;  - oppure usa un Timer UE per inviare: `SendJsonString("{\\"cmd\\":\\"capture\\"}")`

4\. Bind `OnJsonReceived` del Receiver:

&nbsp;  - `ParsePeopleCountPacket(Json, OutSensors, Timestamp)`

&nbsp;  - Somma per aree (da tuo DataTable) e aggiorna logiche/trigger



\## Comandi supportati (UE -> Hub)

\- `{"cmd":"capture"}`

\- `{"cmd":"set\_interval","seconds":2.0}`

\- `{"cmd":"list\_sensors"}`

\- `{"cmd":"set\_conf","conf":0.6}`

\- `{"cmd":"toggle\_depth\_input","enabled":true}`

\- `{"cmd":"shutdown"}`



\## Output (Hub -> UE)

```json

{

&nbsp; "schema":"people\_count\_v1",

&nbsp; "type":"snapshot\_counts",

&nbsp; "timestamp": 1730000000.12,

&nbsp; "sensors":\[

&nbsp;   {"id":"SENSORE001","count":3},

&nbsp;   {"id":"SENSORE002","count":10}

&nbsp; ]

}



