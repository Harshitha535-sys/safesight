"""Video processing: OpenCV decode -> detector -> ZoneMonitor. No FastAPI imports here."""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import cv2

from .detector import PersonDetector
from .errors import ProcessingError, VideoOpenError
from .monitor import MonitorParams, ZoneMonitor, StepResult
from .zone import RectZone


@dataclass
class PipelineParams:
    process_fps: float = 5.0  # frames analysed per second of video (CPU-friendly)
    monitor: MonitorParams = field(default_factory=MonitorParams)
    snapshot_dir: Path | None = None


def open_video(path: Path) -> cv2.VideoCapture:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise VideoOpenError(
            "OpenCV could not open this video. The file may be corrupt or use a codec "
            "that this OpenCV build cannot decode. Try re-encoding to H.264 MP4."
        )
    return cap


def draw_overlay(frame, zone: RectZone, step: StepResult, highlight_ids: set[int] | None = None):
    h, w = frame.shape[:2]
    img = frame.copy()
    zx1, zy1, zx2, zy2 = (int(v) for v in zone.to_pixels(w, h))
    overlay = img.copy()
    cv2.rectangle(overlay, (zx1, zy1), (zx2, zy2), (0, 0, 255), -1)
    img = cv2.addWeighted(overlay, 0.2, img, 0.8, 0)
    cv2.rectangle(img, (zx1, zy1), (zx2, zy2), (0, 0, 255), 2)
    for td in step.tracked:
        d = td.detection
        hot = td.violating or (highlight_ids and td.track_id in highlight_ids)
        color = (0, 0, 255) if hot else (0, 200, 0)
        cv2.rectangle(img, (int(d.x1), int(d.y1)), (int(d.x2), int(d.y2)), color, 2)
        cv2.circle(img, (int(td.point[0]), int(td.point[1])), 4, (0, 255, 255), -1)
        cv2.putText(img, f"#{td.track_id} {d.confidence:.2f}", (int(d.x1), max(12, int(d.y1) - 4)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1, cv2.LINE_AA)
    return img


def process_video(
    video_path: Path,
    detector: PersonDetector,
    zone: RectZone,
    params: PipelineParams | None = None,
    progress: Callable[[int, int], None] | None = None,
) -> dict:
    params = params or PipelineParams()
    cap = open_video(video_path)
    warnings: list[str] = []
    try:
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or fps > 240:
            warnings.append(f"Video reports an invalid FPS ({fps}); assumed 25. Event times may be off.")
            fps = 25.0
        if width <= 0 or height <= 0:
            raise VideoOpenError("Video has no readable frame dimensions.")

        stride = max(1, round(fps / params.process_fps))
        to_process = (total + stride - 1) // stride if total > 0 else 0
        monitor = ZoneMonitor(zone, (width, height), params.monitor)
        if params.snapshot_dir:
            params.snapshot_dir.mkdir(parents=True, exist_ok=True)

        frames: list[dict] = []
        frames_read = 0
        infer_s = 0.0
        t_start = time.perf_counter()
        idx = -1
        while True:
            ok, frame = cap.read()
            if not ok:
                break
            idx += 1
            frames_read += 1
            if idx % stride:
                continue
            t = idx / fps
            t0 = time.perf_counter()
            try:
                dets = detector.detect(frame)
            except Exception as e:
                raise ProcessingError(f"Detection failed on frame {idx}: {e}") from e
            infer_s += time.perf_counter() - t0

            step = monitor.update(t, idx, dets)
            for ev in step.events:
                if ev.type == "violation" and params.snapshot_dir:
                    name = f"event_{ev.id:03d}_t{t:07.2f}.jpg"
                    cv2.imwrite(str(params.snapshot_dir / name), draw_overlay(frame, zone, step, {ev.track_id}),
                                [cv2.IMWRITE_JPEG_QUALITY, 85])
                    ev.snapshot = name
            frames.append({
                "frame_index": idx, "t": round(t, 3), "people_count": len(dets),
                "detections": [{
                    "box": [round(td.detection.x1, 1), round(td.detection.y1, 1),
                            round(td.detection.x2, 1), round(td.detection.y2, 1)],
                    "confidence": round(td.detection.confidence, 3),
                    "track_id": td.track_id, "in_zone": td.in_zone,
                } for td in step.tracked],
            })
            if progress and to_process:
                progress(len(frames), to_process)

        if frames_read == 0:
            raise VideoOpenError("The video opened but no frames could be decoded.")
        if total > 0 and frames_read < 0.9 * total:
            warnings.append(f"Only {frames_read} of {total} reported frames could be decoded; "
                            "results cover the decodable part only.")
        monitor.finalize()
        elapsed = time.perf_counter() - t_start
    finally:
        cap.release()

    counts = [f["people_count"] for f in frames]
    events = [e.to_dict() for e in monitor.events]
    return {
        "video": {"width": width, "height": height, "fps": round(fps, 3),
                  "frames_read": frames_read, "duration_s": round(frames_read / fps, 2)},
        "zone": zone.to_dict(),
        "processing": {
            "model": detector.model_name, "device": "cpu (onnxruntime)",
            "frame_stride": stride, "frames_analysed": len(frames),
            "elapsed_s": round(elapsed, 2),
            "avg_inference_ms": round(1000 * infer_s / len(frames), 1) if frames else None,
            "conf_threshold": detector.conf_threshold,
            "cooldown_s": params.monitor.cooldown_s,
        },
        "summary": {
            "max_people": max(counts, default=0),
            "avg_people": round(sum(counts) / len(counts), 2) if counts else 0.0,
            "violations": sum(1 for e in events if e["type"] == "violation"),
            "suppressed_entries": monitor.suppressed_entries,
            "unique_people_tracked": len({d["track_id"] for f in frames for d in f["detections"]}),
        },
        "events": events,
        "frames": frames,
        "warnings": warnings,
    }
