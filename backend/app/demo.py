"""Deterministic demonstration events. Used only when explicitly loaded; always stored with
processing_mode='demo' so they can never be mistaken for real detections."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

DEMO_WARNING = "DEMO MODE — Events are simulated and do not represent live AI detections."
DEMO_SOURCE = "demo-simulator"
DEMO_JOB_ID = "demo"
DEMO_ZONE = "zone-demo"
_BASE = datetime(2026, 1, 1, 9, 0, 0, tzinfo=timezone.utc)  # fixed: identical on every run

# (seconds after base, event_type, severity, track_id, description)
_SCRIPT = [
    (12, "violation", "critical", 1, "Simulated person enters restricted zone"),
    (47, "zone_proximity", "warning", 2, "Simulated person near restricted-zone boundary"),
    (95, "violation", "critical", 3, "Simulated person enters restricted zone"),
    (130, "zone_proximity", "warning", 4, "Simulated person near restricted-zone boundary"),
    (260, "violation", "critical", 5, "Simulated person re-enters restricted zone after cooldown"),
    (3600 + 20, "violation", "critical", 6, "Simulated person enters restricted zone"),
    (86400 + 31, "violation", "critical", 7, "Simulated person enters restricted zone"),
    (86400 + 400, "zone_proximity", "warning", 8, "Simulated person near restricted-zone boundary"),
]


def demo_events() -> List[Dict[str, Any]]:
    return [dict(
        event_type=t, severity=sev, track_id=trk, zone_id=DEMO_ZONE, source=DEMO_SOURCE,
        processing_mode="demo", job_id=DEMO_JOB_ID, video_time_s=float(off), confidence=None,  # no fabricated confidence
        occurred_at=_BASE + timedelta(seconds=off), description="[SIMULATED] " + desc,
    ) for off, t, sev, trk, desc in _SCRIPT]


def load_demo(store) -> Dict[str, int]:
    """Idempotent: loading twice adds nothing the second time."""
    ins = dup = 0
    for ev in demo_events():
        _, created = store.add(**ev)
        ins += created
        dup += not created
    return {"inserted": ins, "already_present": dup}
