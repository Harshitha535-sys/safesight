# Submission text (honest version)

**Project name:** SafeSight AI

**One-line description:** Restricted-zone person monitoring for video: detects and tracks people with a
CPU object detector, raises timestamped alerts with snapshots when someone enters a configured zone, and stores
incidents for review and export.

**Short description (≈100 words):**
SafeSight AI is an industrial-safety prototype. Upload a video, define a restricted zone, and the system detects
and tracks people (YOLOX-nano on ONNX Runtime with OpenCV, CPU-only), flags zone entries with a cooldown to avoid
alert spam, saves snapshots, and presents a dashboard with a frame-by-frame viewer, incident log, acknowledgement
and analytics. A SQLite incident store keeps real detections strictly separate from clearly labelled simulated demo
events. Incidents export as CSV/JSON through a REST API. Current limits: video-file input only, CPU inference,
no PipeGen compilation, no TensorRT engine, no firmware, and no physical-board integration yet.

**Track:** Track A (PipeGen) is the intended fit, but the PipeGen workflow, TensorRT engine, speed report and
NVIDIA/Jetson live run are **not done**. Track B (FirmGen) is **not started**. Do not tick the boxes for them.
Ask the organisers whether a partial / "pipeline-ready, not yet compiled" entry is eligible.

**Built with:** Python, FastAPI, SQLite, OpenCV, ONNX Runtime, YOLOX-nano, React, TypeScript, Vite, Tailwind, Recharts.

**What works today (evidence):** incident store, dedupe, filtering, acknowledgement, analytics, CSV export, demo labelling
(39 automated tests run, 35 pass, 4 HTTP tests skipped in my sandbox). Detection/zone behaviour and the UI must be
demonstrated on your own machine; capture your own recording.

**What's next:** express the pipeline in CraftifAI PipeGen, compile one model to TensorRT on an NVIDIA GPU/Jetson,
publish the PipeGen speed report, emit JSON/MQTT events, and (optional) trigger a physical actuator.
