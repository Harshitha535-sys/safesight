# Architecture

Legend: ✅ verified by execution · 🔍 read only · ⚠️ not supplied/not run · ❌ not built

```
 Browser (React + Vite) ──HTTP /api──▶ FastAPI backend ──▶ OpenCV + YOLOX-nano (ONNX Runtime, CPU)
   localStorage (job ids,                  │                      │ per-frame detections, tracks,
   acks, settings)                         │                      ▼ zone test, cooldown
                                           │                 events (+ snapshots on disk)
                                           ▼
                                  persist_job_events ──▶ SQLite  (db.py)  ✅
                                           ▲
                         /api/incidents, /api/analytics, /api/monitoring, /api/demo  🔍 (HTTP tests skipped)
```

## Components
| Component | Role | Status |
|---|---|---|
| Frontend (`App`, `store`, `api`, pages, `charts`, `ui`) | Upload video, set zone/cooldown/fps, play frame viewer with boxes, alerts, incident log, analytics, settings | 🔍 / ⚠️ not built or run |
| Backend job API (`/api/jobs*`, `/api/model*`, `/api/health`) | Accept upload, run pipeline, serve status/frames/snapshots | ⚠️ not supplied; endpoints inferred from `api.ts` |
| Detection pipeline | YOLOX-nano ONNX on CPU, tracking, zone containment, cooldown | ⚠️ not supplied |
| `db.py` incident store | SQLite, dedupe key, origin flag (`ai`/`demo`), filters, ack, analytics, CSV | ✅ |
| `persist.py` | Maps finished-job events to incident rows; idempotent re-runs | ✅ |
| `demo.py` | 8 fixed events, always `processing_mode='demo'`, `[SIMULATED]` text, no fabricated confidence | ✅ |
| `monitoring.py` | Reports model presence, demo flag, camera (always unavailable), DB health | ✅ |
| `api/incidents.py` | REST layer over the store | 🔍 |

## Data flow
1. User uploads a video + zone (fractions 0–1), cooldown, analysis fps → `POST /api/jobs`.
2. Backend processes frames; the UI polls `GET /api/jobs/{id}` every 1.5 s and loads `/frames` when done.
3. On completion `persist_job_events` writes each event (wall time = job start + video time).
4. Incident rows are readable via `/api/incidents*`; the dashboard currently reads job events instead.

## Design decisions that protect honesty
- **Origin is never mixed silently:** every row carries `processing_mode`; queries take `include=ai|demo|all`;
  analytics default to `ai`; `by_origin` always reports both. ✅ (tests `test_origin_never_mixed_silently`)
- Demo mode is a labelled data set, not a fake detector.
- `monitoring` reports demo when weights are missing/empty or `SAFESIGHT_DEMO=1`. ⚠️ I could not verify that
  the pipeline itself honours this flag.

## Not part of this system (do not claim otherwise)
- **No PipeGen.** Detection is a hand-written OpenCV/ONNX pipeline, not a PipeGen-generated or -compiled one.
- **No TensorRT.** The model is ONNX on CPU; Intel Iris Xe is unused.
- **No FirmGen, no firmware, no MCU, no MQTT, no physical actuation.**
