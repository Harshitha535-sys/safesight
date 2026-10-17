"""Bridge from a finished processing job to the incident database."""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, Optional

from .db import SEVERITIES, IncidentStore, to_iso


def _first(d: dict, *keys: str) -> Any:
    for k in keys:
        if d.get(k) is not None:
            return d[k]
    return None


def _num(v: Any) -> Optional[float]:
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def persist_job_events(store: IncidentStore, *, job_id: str, source: str, events: Optional[Iterable[Any]],
                       zone_id: str = "zone-1", job_started_at: Any = None, processing_mode: str = "ai") -> Dict[str, int]:
    """Store a job's events. Safe to call more than once for the same job (duplicates are ignored).
    Event times in the pipeline are video time, so wall-clock time = job start + video time."""
    base = datetime.fromisoformat(to_iso(job_started_at).replace("Z", "+00:00"))
    out = {"inserted": 0, "duplicates": 0, "skipped": 0}
    for ev in events or []:
        if not isinstance(ev, dict):
            out["skipped"] += 1
            continue
        etype = str(_first(ev, "type", "event_type", "kind", "event") or "violation")
        vt = _num(_first(ev, "time_s", "video_time_s", "timestamp_s", "t", "time"))
        conf = _num(_first(ev, "confidence", "conf", "score"))
        if conf is not None and not 0 <= conf <= 1:
            conf = None
        trk = _first(ev, "track_id", "person_id", "id")
        trk = int(trk) if isinstance(trk, (int, float)) and not isinstance(trk, bool) else None
        sev = ev.get("severity") if ev.get("severity") in SEVERITIES else ("critical" if "violation" in etype.lower() else "warning")
        snap = _first(ev, "snapshot", "snapshot_url", "snapshot_path", "snapshot_file")
        desc = ev.get("description") or (
            f"Person{'' if trk is None else f' (track {trk})'}: {etype.replace('_', ' ')}"
            + ("" if vt is None else f" at video time {vt:.1f}s"))
        _, created = store.add(
            event_type=etype, severity=sev, confidence=conf, zone_id=zone_id, description=str(desc), source=source,
            processing_mode=processing_mode, job_id=job_id, track_id=trk, video_time_s=vt,
            snapshot=str(snap).replace("\\", "/").split("/")[-1] if snap else None,
            occurred_at=base + timedelta(seconds=vt or 0))
        out["inserted" if created else "duplicates"] += 1
    return out
