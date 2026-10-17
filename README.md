# SafeSight AI

A local workplace-safety prototype that analyzes uploaded video, detects and tracks people, flags entries into a configured restricted zone, and provides incident review and exports.

## Run on Ubuntu

Prerequisites: Python 3.10 or newer, Node.js 18 or newer, npm, and internet access for installing packages. The YOLOX-nano model is included. The first launch installs dependencies and may take a few minutes.

Open two terminals in the extracted project folder (the folder containing `README.md` and `scripts/`).

Terminal 1 — backend:

```bash
bash scripts/run_backend.sh
```

Terminal 2 — frontend:

```bash
bash scripts/run_frontend.sh
```

Open http://localhost:5173. The backend health check is http://127.0.0.1:8000/api/health and API documentation is http://127.0.0.1:8000/docs. Keep both terminals open while using the app; press Ctrl+C in each to stop it.

If virtual-environment creation reports that `ensurepip` is missing, install Ubuntu's venv package (`sudo apt install python3-venv`) and rerun the backend command. If the model file is missing, the backend script attempts to download it, so internet access is required.

## Use the prototype

Open **Live Monitoring**, choose an MP4/AVI/MOV/MKV/WEBM video, and select **Start analysis**. Configure the restricted zone, cooldown, and processing rate under **Settings**. Review results in Live Monitoring, Incidents, and Analytics. Jobs are held in backend memory and disappear if you restart the backend. This prototype processes video files; it is not the PipeGen live pipeline.

## Hackathon status

This package is a runnable CPU video prototype and preparation for Track A. It does not by itself satisfy either mandatory track. The official brief requires a completed PipeGen workflow, a TensorRT engine and PipeGen speed report, and a live run on an NVIDIA GPU or Jetson for Track A. Track B requires FirmGen-built firmware running on a physical ESP32/STM32, acceptance evidence, and a traceability report. See [docs/COMPLIANCE.md](docs/COMPLIANCE.md) for the requirement-by-requirement status and [pipegen/EVIDENCE_CHECKLIST.md](pipegen/EVIDENCE_CHECKLIST.md) for evidence to capture on qualifying hardware.

The project includes a PipeGen requirement draft, MQTT/JSON event support, and a firmware PRD draft as preparation. These are not proof of a completed PipeGen or FirmGen workflow. Do not present the CPU prototype as a TensorRT or physical-board demo.

## Troubleshooting

- Frontend says **Backend unreachable**: confirm the backend terminal still shows Uvicorn running on port 8000.
- Port 8000 or 5173 is in use: stop the process already using that port, then rerun the corresponding script.
- Python dependency installation fails: use Python 3.10–3.12 and recreate `backend/.venv`.
- Upload fails: use a supported video format and keep the file below the backend upload limit (200 MB).

See [docs/API.md](docs/API.md), [docs/DEMO_SCRIPT.md](docs/DEMO_SCRIPT.md), and [docs/COMPLIANCE.md](docs/COMPLIANCE.md).