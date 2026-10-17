"""API tests for validation and honest error reporting. The blank video is only a carrier file."""
import time

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from app import jobs
from app.config import settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "data_dir", tmp_path / "data")
    monkeypatch.setattr(settings, "model_path", tmp_path / "missing.onnx")
    monkeypatch.setattr(jobs, "_manager", None)
    return TestClient(app)


def blank_video(path, frames=10):
    w = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (160, 120))
    for _ in range(frames):
        w.write(np.zeros((120, 160, 3), np.uint8))
    w.release()


ZONE = {"zone_x1": 0.2, "zone_y1": 0.2, "zone_x2": 0.8, "zone_y2": 0.8}


def test_model_status_reports_missing(client):
    r = client.get("/api/model/status")
    assert r.status_code == 200 and r.json()["available"] is False


def test_invalid_zone_422(client, tmp_path):
    p = tmp_path / "v.avi"; blank_video(p)
    r = client.post("/api/jobs", files={"file": ("v.avi", p.read_bytes())},
                    data={**ZONE, "zone_x1": 0.9})
    assert r.status_code == 422


def test_bad_extension_415(client):
    r = client.post("/api/jobs", files={"file": ("x.txt", b"hi")}, data=ZONE)
    assert r.status_code == 415


def test_undecodable_video_400(client):
    r = client.post("/api/jobs", files={"file": ("x.mp4", b"not a video at all")}, data=ZONE)
    assert r.status_code == 400


def test_missing_model_fails_job_honestly(client, tmp_path):
    p = tmp_path / "v.avi"; blank_video(p)
    r = client.post("/api/jobs", files={"file": ("v.avi", p.read_bytes())}, data=ZONE)
    assert r.status_code == 202
    job_id = r.json()["job_id"]
    for _ in range(50):
        body = client.get(f"/api/jobs/{job_id}").json()
        if body["status"] in ("completed", "failed"):
            break
        time.sleep(0.1)
    assert body["status"] == "failed"
    assert body["error"]["code"] == "model_missing"
    assert "fetch_model" in body["error"]["message"]
    assert "events" not in body  # no fabricated results


def test_unknown_job_404(client):
    assert client.get("/api/jobs/nope").status_code == 404
