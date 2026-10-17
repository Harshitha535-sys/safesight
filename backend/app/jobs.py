"""Background processing jobs. Runs app.cv.pipeline in a worker thread; routes only call this."""
from __future__ import annotations

import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .config import settings
from .cv.detector import PersonDetector
from .cv.errors import SafeSightError
from .cv.monitor import MonitorParams
from .cv.pipeline import PipelineParams, process_video
from .cv.zone import RectZone
from .publisher import EventPublisher, publish_events


@dataclass
class Job:
    id: str
    video_path: Path
    zone: RectZone
    params: PipelineParams
    status: str = "queued"  # queued | processing | completed | failed
    progress: float = 0.0
    error: dict | None = None
    result: dict | None = None
    created_at: float = field(default_factory=time.time)


class JobManager:
    def __init__(self, data_dir: Path):
        self.data_dir = data_dir
        self.uploads = data_dir / "uploads"
        self.snapshots = data_dir / "snapshots"
        self.uploads.mkdir(parents=True, exist_ok=True)
        self.snapshots.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, Job] = {}
        self._pool = ThreadPoolExecutor(max_workers=1)  # one video at a time on CPU
        self._detector: PersonDetector | None = None
        self._lock = threading.Lock()
        self.publisher = EventPublisher.from_env(data_dir)

    def _get_detector(self) -> PersonDetector:
        with self._lock:
            if self._detector is None:
                self._detector = PersonDetector(settings.model_path, settings.conf_threshold)
            return self._detector

    def new_id(self) -> str:
        return uuid.uuid4().hex[:12]

    def submit(self, job_id: str, video_path: Path, zone: RectZone,
               cooldown_s: float, process_fps: float) -> Job:
        params = PipelineParams(process_fps=process_fps,
                                monitor=MonitorParams(cooldown_s=cooldown_s),
                                snapshot_dir=self.snapshots / job_id)
        job = Job(job_id, video_path, zone, params)
        self.jobs[job_id] = job
        self._pool.submit(self._run, job)
        return job

    def _run(self, job: Job) -> None:
        job.status = "processing"
        started = datetime.now(timezone.utc)
        try:
            detector = self._get_detector()
            job.result = process_video(
                job.video_path, detector, job.zone, job.params,
                progress=lambda done, total: setattr(job, "progress", round(done / total, 3)),
            )
            job.progress = 1.0
            job.status = "completed"
            self._after_completion(job, started)
        except SafeSightError as e:
            job.status, job.error = "failed", {"code": e.code, "message": e.message}
        except Exception as e:  # unexpected: report it, never swallow
            job.status, job.error = "failed", {"code": "internal_error", "message": f"{type(e).__name__}: {e}"}

    def _after_completion(self, job: Job, started: datetime) -> None:
        """Persist incidents and emit JSON/MQTT. A failure here must never fail the job."""
        events = (job.result or {}).get("events", [])
        try:
            from .api.incidents import get_store
            from .persist import persist_job_events
            persist_job_events(get_store(), job_id=job.id, source=job.video_path.name, events=events,
                               zone_id="zone-1", job_started_at=started)
        except Exception as e:
            job.result.setdefault("warnings", []).append(f"Incident DB write failed: {type(e).__name__}: {e}")
        try:
            publish_events(self.publisher, events, job_id=job.id, source=job.video_path.name,
                           zone_id="zone-1", started_at=started)
        except Exception as e:
            job.result.setdefault("warnings", []).append(f"Event publish failed: {type(e).__name__}: {e}")


_manager: JobManager | None = None


def get_manager() -> JobManager:
    global _manager
    if _manager is None:
        _manager = JobManager(settings.data_dir)
        from . import monitoring
        monitoring.active_jobs_provider = lambda: sum(1 for j in _manager.jobs.values() if j.status == "processing")
    return _manager
