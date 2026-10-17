import numpy as np
import pytest

from app.cv.detector import NUM_VALUES, PersonDetector, decode_yolox, letterbox, nms
from app.cv.errors import ModelLoadError, ModelNotFoundError


def test_letterbox_keeps_aspect_and_pads():
    img = np.zeros((576, 768, 3), np.uint8)
    out, r = letterbox(img, (416, 416))
    assert out.shape == (416, 416, 3)
    assert abs(r - 416 / 768) < 1e-9
    assert (out[-1, -1] == 114).all()  # padded corner


def test_nms_removes_overlap_keeps_best():
    boxes = np.array([[0, 0, 100, 100], [5, 5, 105, 105], [300, 300, 400, 400]], float)
    scores = np.array([0.6, 0.9, 0.7])
    assert sorted(nms(boxes, scores, 0.45)) == [1, 2]


def test_decode_places_box_from_known_cell():
    n = 52 * 52 + 26 * 26 + 13 * 13
    raw = np.zeros((n, NUM_VALUES), np.float32)
    # cell (x=10, y=20) on the stride-8 grid: index = 20*52 + 10
    i = 20 * 52 + 10
    raw[i, :2] = 0.5                   # offset inside cell
    raw[i, 2:4] = np.log([4.0, 8.0])   # w=4*8=32, h=8*8=64
    raw[i, 4] = 0.9                    # objectness
    raw[i, 5] = 0.8                    # person class prob
    boxes, scores = decode_yolox(raw, (416, 416))
    cx, cy = (10.5) * 8, (20.5) * 8
    assert np.allclose(boxes[i], [cx - 16, cy - 32, cx + 16, cy + 32], atol=1e-3)
    assert np.isclose(scores[i], 0.72)
    assert scores.max() == scores[i]


def test_decode_rejects_wrong_prediction_count():
    with pytest.raises(ModelLoadError):
        decode_yolox(np.zeros((100, NUM_VALUES), np.float32), (416, 416))


def test_missing_weights_raise_clear_error(tmp_path):
    with pytest.raises(ModelNotFoundError) as e:
        PersonDetector(tmp_path / "nope.onnx")
    assert "fetch_model" in e.value.message


def test_corrupt_weights_raise_load_error(tmp_path):
    bad = tmp_path / "bad.onnx"
    bad.write_bytes(b"this is not an onnx model")
    with pytest.raises(ModelLoadError):
        PersonDetector(bad)
