# API reference

Base URL `http://localhost:8000`. All routes are under `/api`. Invalid parameters return **422**, unknown
ids **404**.

## A. Incident, analytics, monitoring, demo routes  (`app/api/incidents.py`)
Status: 🔍 source-reviewed; underlying store ✅ tested; the 4 HTTP tests are ⚠️ skipped in my environment.

### Incident record
`id, dedupe_key, job_id, track_id, event_type, severity (critical|warning|info), confidence (0–1 or null),
zone_id, description, source, processing_mode (ai|demo), simulated (bool), video_time_s, snapshot,
occurred_at (UTC ISO), created_at, acknowledged (bool), acknowledged_at`

### Shared filters
`severity`, `event_type` (≤100), `acknowledged` (bool), `source` (≤300), `q` (≤200, substring on type/source/description/zone, `%`/`_` literal),
`date_from`, `date_to` (`YYYY-MM-DD`, UTC day of `occurred_at`).

| Method & path | Params | Returns |
|---|---|---|
| `GET /api/incidents` | filters + `include=ai\|demo\|all` (default **all**), `limit` 1–1000 (100), `offset` ≥0 | `{items,total,limit,offset}` newest first |
| `GET /api/incidents/export` | filters + `include`, `format=csv\|json` (csv) | file download `safesight-incidents.<fmt>`; CSV has an `origin` column (`simulated`/`detected`) and formula-safe cells |
| `GET /api/incidents/{id}` | `id` ≥1 | one record |
| `PATCH /api/incidents/{id}/acknowledge` | optional JSON `{"acknowledged": true\|false}` (default true) | updated record; re-ack keeps first timestamp |
| `GET /api/analytics/summary` | filters + `include` (default **ai**) | `total, today, unacknowledged, by_severity, by_event_type, by_day, by_origin, latest_at, today_utc, note` |
| `GET /api/monitoring/status` | — | `mode (ai\|demo), demo, demo_reason, warning, model_present, camera{available:false}, database{ok,engine,incidents}, active_jobs, server_time` |
| `POST /api/demo/events` | — | `{warning, inserted, already_present}`; idempotent; rows are `processing_mode=demo` |
| `DELETE /api/demo/events` | — | `{deleted}`; removes demo rows only |

```bash
curl "http://localhost:8000/api/incidents?include=ai&severity=critical&limit=20"
curl -X PATCH http://localhost:8000/api/incidents/1/acknowledge -H "Content-Type: application/json" -d '{"acknowledged":true}'
curl -o incidents.csv "http://localhost:8000/api/incidents/export?include=ai"
```

## B. Job / model routes  (inferred from the frontend client `api.ts`)
Status: ⚠️ the backend source was not supplied. These are what the frontend *calls*; confirm against `main.py`.

| Method & path | Notes |
|---|---|
| `GET /api/health` | liveness; polled every 8 s |
| `GET /api/model/status` | frontend reads a boolean from `present/available/ready/exists/valid/ok/loaded` |
| `POST /api/model/download` | fetch model weights |
| `POST /api/jobs` | multipart: `file`, `zone_x1`,`zone_y1`,`zone_x2`,`zone_y2` (0–1), `cooldown_s`, `process_fps`; returns `id` or `job_id` |
| `GET /api/jobs/{id}` | `status`, `progress`, `summary`, `events[]`, `errors` |
| `GET /api/jobs/{id}/frames` | per-frame detections (`bbox`, `confidence`, `track_id`, `in_zone`) |
| `GET /api/jobs/{id}/snapshots/{name}` | violation snapshot image |

There is **no** MQTT, WebSocket, camera or TensorRT interface.
