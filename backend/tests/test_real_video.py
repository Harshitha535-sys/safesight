"""End-to-end on the real model + real sample video. Skipped if either file is absent."""
from pathlib import Path

import pytest

from app.config import settings
from app.cv.detector import PersonDetector
from app.cv.monitor import MonitorParams
from app.cv.pipeline import PipelineParams, process_video
from app.cv.zone import RectZone

VIDEO = Path(__file__).resolve().parents[1] / "data" / "samples" / "vtest.avi"
pytestmark = pytest.mark.skipif(not (settings.model_path.is_file() and VIDEO.is_file()),
                                reason="model weights or sample video not present")


def test_real_detection_and_zone_events(tmp_path):
    det = PersonDetector(settings.model_path)
    res = process_video(VIDEO, det, RectZone(0.45, 0.25, 0.80, 0.55),
                        PipelineParams(process_fps=2.5, monitor=MonitorParams(cooldown_s=10),
                                       snapshot_dir=tmp_path))
    assert res["summary"]["max_people"] >= 3          # the clip really contains several walkers
    assert res["processing"]["frames_analysed"] > 50
    assert res["summary"]["violations"] >= 1
    for ev in res["events"]:
        if ev["type"] == "violation":
            assert (tmp_path / ev["snapshot"]).is_file()
    # no violation may fire twice for the same track inside the cooldown
    by_track = {}
    for ev in res["events"]:
        if ev["type"] == "violation":
            by_track.setdefault(ev["track_id"], []).append(ev["t"])
    for ts in by_track.values():
        assert all(b - a >= 10 for a, b in zip(ts, ts[1:]))
