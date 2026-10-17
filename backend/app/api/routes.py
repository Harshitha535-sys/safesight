"""HTTP layer only: validates input, delegates to JobManager / model_manager."""
from __future__ import annotations

import cv2
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from ..config import settings
from ..cv.errors import ModelDownloadError
from ..cv.model_manager import download_model, model_status
from ..cv.zone import RectZone
from ..jobs import get_manager

router = APIRouter(prefix="/api")
ALLOWED_EXT = {".mp4", ".avi", ".mov", ".mkv", ".webm"}


@router.get("/model/status")
def model_status_route() -> dict:
    return {**model_status(settings.model_path, settings.model_sha256),
            "model": "YOLOX-nano (COCO)", "source_url": settings.model_url}


@router.post("/model/download")
def model_download_route() -> dict:
    try:
        download_model(settings.model_url, settings.model_path, settings.model_sha256)
    except ModelDownloadError as e:
        raise HTTPException(status_code=502, detail={"code": e.code, "message": e.message})
    get_manager()._detector = None  # force reload of the new weights
    return model_status(settings.model_path, settings.model_sha256)


@router.post("/jobs", status_code=202)
async def create_job(
    file: UploadFile = File(...),
    zone_x1: float = Form(...), zone_y1: float = Form(...),
    zone_x2: float = Form(...), zone_y2: float = Form(...),
    cooldown_s: float = Form(10.0), process_fps: float = Form(5.0),
) -> dict:
    try:
        zone = RectZone(zone_x1, zone_y1, zone_x2, zone_y2)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Invalid zone: {e}")
    if not (0 <= cooldown_s <= 3600):
        raise HTTPException(status_code=422, detail="cooldown_s must be between 0 and 3600")
    if not (0.5 <= process_fps <= 30):
        raise HTTPException(status_code=422, detail="process_fps must be between 0.5 and 30")

    from pathlib import Path
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXT:
        raise HTTPException(status_code=415, detail=f"Unsupported file type '{ext}'. Allowed: {sorted(ALLOWED_EXT)}")

    mgr = get_manager()
    job_id = mgr.new_id()
    dest = mgr.uploads / f"{job_id}{ext}"
    limit = settings.max_upload_mb * 1024 * 1024
    size = 0
    with open(dest, "wb") as out:
        while chunk := await file.read(1 << 20):
            size += len(chunk)
            if size > limit:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail=f"Upload exceeds {settings.max_upload_mb} MB")
            out.write(chunk)

    cap = cv2.VideoCapture(str(dest))
    ok = cap.isOpened() and cap.read()[0]
    cap.release()
    if not ok:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File could not be decoded as video by OpenCV (corrupt or unsupported codec).")

    mgr.submit(job_id, dest, zone, cooldown_s, process_fps)
    return {"job_id": job_id, "status": "queued"}


def _job_or_404(job_id: str):
    job = get_manager().jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Unknown job")
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    job = _job_or_404(job_id)
    body = {"job_id": job.id, "status": job.status, "progress": job.progress, "error": job.error}
    if job.result:
        body.update({k: job.result[k] for k in ("video", "zone", "processing", "summary", "events", "warnings")})
    return body


@router.get("/jobs/{job_id}/frames")
def get_frames(job_id: str) -> dict:
    job = _job_or_404(job_id)
    if job.status != "completed" or not job.result:
        raise HTTPException(status_code=409, detail=f"Job is {job.status}")
    return {"frames": job.result["frames"]}


@router.get("/jobs/{job_id}/snapshots/{name}")
def get_snapshot(job_id: str, name: str):
    _job_or_404(job_id)
    path = get_manager().snapshots / job_id / name
    if "/" in name or "\\" in name or not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path, media_type="image/jpeg")
