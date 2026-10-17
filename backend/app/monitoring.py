"""Monitoring status: is the AI model usable, is there a camera, is the DB healthy, are we in demo mode."""
import os
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from .db import IncidentStore, to_iso
from .demo import DEMO_WARNING

DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "yolox_nano.onnx"
# Optional hook: set to a function returning the number of running jobs (jobs.py is not touched by this module).
active_jobs_provider: Optional[Callable[[], int]] = None


def monitoring_status(store: IncidentStore, model_path: Any = None) -> Dict[str, Any]:
    mp = Path(model_path or os.environ.get("SAFESIGHT_MODEL_PATH") or DEFAULT_MODEL_PATH)
    present = mp.is_file() and mp.stat().st_size > 0
    forced = os.environ.get("SAFESIGHT_DEMO") == "1"
    demo = forced or not present
    jobs = None
    if active_jobs_provider is not None:
        try:
            jobs = int(active_jobs_provider())
        except Exception:
            jobs = None
    ok = store.ping()
    return {
        "mode": "demo" if demo else "ai",
        "demo": demo,
        "demo_reason": "forced by SAFESIGHT_DEMO=1" if forced else ("AI model weights not found" if not present else None),
        "warning": DEMO_WARNING if demo else None,
        "model_present": present,  # presence only; integrity is checked by the existing fetch_model tool
        "camera": {"available": False, "reason": "Live camera input is not implemented; video-file jobs only."},
        "database": {"ok": ok, "engine": "sqlite", "incidents": store.list(limit=1)[1] if ok else None},
        "active_jobs": jobs,
        "server_time": to_iso(),
    }
