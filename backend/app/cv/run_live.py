"""Live monitoring from a USB camera, RTSP stream or video file (CPU, ONNX Runtime).

    python -m app.cv.run_live --source 0 --zone 0.4 0.3 0.9 0.9 [--mqtt-host localhost] [--display]
    python -m app.cv.run_live --source rtsp://user:pw@cam/stream --zone ...

Each confirmed zone entry is stored in the incident DB and emitted as JSON (data/events.jsonl and, if
configured, MQTT topic safesight/<zone>/events). This is the CPU reference pipeline - NOT a PipeGen/DeepStream
pipeline. See pipegen/ for the GPU/TensorRT path.
"""
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path

import cv2

from ..config import settings
from ..db import IncidentStore
from ..persist import persist_job_events
from ..publisher import EventPublisher, publish_events
from .detector import PersonDetector
from .errors import SafeSightError
from .monitor import MonitorParams, ZoneMonitor
from .pipeline import draw_overlay
from .zone import RectZone


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default="0", help="camera index, RTSP URL or video path")
    ap.add_argument("--zone", type=float, nargs=4, required=True, metavar=("X1", "Y1", "X2", "Y2"))
    ap.add_argument("--process-fps", type=float, default=5.0)
    ap.add_argument("--cooldown", type=float, default=10.0)
    ap.add_argument("--mqtt-host"); ap.add_argument("--mqtt-port", type=int, default=1883)
    ap.add_argument("--display", action="store_true", help="show a window (needs a desktop session)")
    ap.add_argument("--max-seconds", type=float, default=0, help="stop after N seconds (0 = run until q/Ctrl-C)")
    ap.add_argument("--snapshots", type=Path, default=settings.data_dir / "snapshots" / "live")
    a = ap.parse_args()

    try:
        detector = PersonDetector(settings.model_path, settings.conf_threshold)
    except SafeSightError as e:
        print(f"[{e.code}] {e.message}")
        return 2
    src = int(a.source) if a.source.isdigit() else a.source
    cap = cv2.VideoCapture(src)
    if not cap.isOpened():
        print(f"Could not open source {a.source!r}")
        return 2
    w, h = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    zone = RectZone(*a.zone)
    monitor = ZoneMonitor(zone, (w, h), MonitorParams(cooldown_s=a.cooldown))
    pub = EventPublisher.from_env(settings.data_dir)
    if a.mqtt_host:
        pub = EventPublisher(pub.jsonl_path, a.mqtt_host, a.mqtt_port)
    store, session = IncidentStore(), f"live-{int(time.time())}"
    a.snapshots.mkdir(parents=True, exist_ok=True)
    started = datetime.now(timezone.utc)
    t0 = last = time.perf_counter()
    idx, sent, lat = -1, 0, []
    print(f"Live run on {a.source!r} {w}x{h}; MQTT={'on' if pub.mqtt_enabled else 'off'}; Ctrl-C or q to stop")
    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            idx += 1
            now = time.perf_counter()
            if now - last < 1.0 / a.process_fps:
                continue
            last, t = now, now - t0
            ts = time.perf_counter()
            step = monitor.update(t, idx, detector.detect(frame))
            lat.append((time.perf_counter() - ts) * 1000)
            evs = []
            for ev in step.events:
                if ev.type == "violation":
                    ev.snapshot = f"event_{ev.id:03d}_t{t:07.2f}.jpg"
                    cv2.imwrite(str(a.snapshots / ev.snapshot), draw_overlay(frame, zone, step, {ev.track_id}))
                evs.append(ev.to_dict())
            if evs:
                persist_job_events(store, job_id=session, source=str(a.source), events=evs, job_started_at=started)
                sent += publish_events(pub, evs, job_id=session, source=str(a.source), started_at=started)
                print(f"  t={t:6.1f}s  ALERT x{len(evs)}  (published {sent} total)")
            if a.display:
                cv2.imshow("SafeSight live", draw_overlay(frame, zone, step))
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
            if a.max_seconds and t >= a.max_seconds:
                break
    except KeyboardInterrupt:
        pass
    finally:
        cap.release(); pub.close(); cv2.destroyAllWindows()
    if lat:
        print(f"Done: {len(lat)} frames analysed, avg {sum(lat)/len(lat):.1f} ms/frame, {sent} alerts published")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
