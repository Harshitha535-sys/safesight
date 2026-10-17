# PipeGen stage 1 — Requirement (paste this into PipeGen v0.5.1)

> Detect people in a site camera video (file, USB camera or RTSP) and track them. A restricted zone is the
> rectangle x 0.45–0.80, y 0.25–0.55 of the frame. When a tracked person's feet enter the zone, raise an alert
> (at most one per person per 10 s). Save an annotated RTSP/video output, write JSON metadata per frame, and
> publish each alert as JSON to MQTT topic `safesight/zone-1/events`. Run in FP16 and INT8 on the GPU and report
> speed, power and accuracy.

Settings to pick in the wizard
| Stage | Choice |
|---|---|
| Pipeline IR | source → person detector (PGIE) → tracker (NvDCF/IOU) → nvdsanalytics ROI filtering → OSD → sinks: display/RTSP, JSON metadata, MQTT (msgconv + msgbroker) |
| Model | Person detector from the catalog (e.g. PeopleNet / YOLOX / YOLOv8-n, COCO "person"). The project's own `backend/models/yolox_nano.onnx` can be supplied via Deep Search/GitHub as the BYO model |
| Compiler | TensorRT **FP16** and **INT8** (INT8 needs a calibration set: ~500 frames from your venue video) |
| Run | `run.sh` on the NVIDIA GPU / Jetson with the venue USB camera or an RTSP URL |

The message published by the PipeGen app should match `docs/API.md` §"Event message" (`safesight.event.v1`) so
`pipegen/mqtt_listener.py` and the dashboard keep working. If PipeGen's msgconv payload differs, adapt the listener —
do not claim they match.

Evidence to capture for submission (see `EVIDENCE_CHECKLIST.md`): Pipeline IR node-graph screenshot, TensorRT
speed report (FP16 and INT8), terminal showing `pipegen --version` = 0.5.1, live-run recording.
