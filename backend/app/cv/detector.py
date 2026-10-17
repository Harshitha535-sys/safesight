"""YOLOX-nano (COCO-pretrained) person detector running on CPU via ONNX Runtime.

Only the COCO 'person' class (index 0) is kept. No randomness, no simulated output:
if the weights are missing or invalid, this module raises instead of guessing.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

from .errors import ModelLoadError, ModelNotFoundError

PERSON_CLASS = 0
STRIDES = (8, 16, 32)
NUM_VALUES = 85  # 4 box + 1 objectness + 80 COCO classes


@dataclass(frozen=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float

    @property
    def box(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)


def letterbox(img: np.ndarray, size: tuple[int, int]) -> tuple[np.ndarray, float]:
    """Resize keeping aspect ratio, pad bottom/right with 114. Returns (image, ratio)."""
    h, w = img.shape[:2]
    r = min(size[0] / h, size[1] / w)
    nh, nw = max(1, int(h * r)), max(1, int(w * r))
    resized = cv2.resize(img, (nw, nh), interpolation=cv2.INTER_LINEAR)
    canvas = np.full((size[0], size[1], 3), 114, dtype=np.uint8)
    canvas[:nh, :nw] = resized
    return canvas, r


def decode_yolox(raw: np.ndarray, size: tuple[int, int]) -> tuple[np.ndarray, np.ndarray]:
    """Decode raw YOLOX head output (N, 85) -> person boxes xyxy (letterbox px) and scores."""
    out = raw.copy()
    grids, strides = [], []
    for s in STRIDES:
        hs, ws = size[0] // s, size[1] // s
        xv, yv = np.meshgrid(np.arange(ws), np.arange(hs))
        grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
        strides.append(np.full((hs * ws, 1), s))
    grid = np.concatenate(grids, 0)
    stride = np.concatenate(strides, 0)
    if out.shape[0] != grid.shape[0]:
        raise ModelLoadError(
            f"Unexpected model output: {out.shape[0]} predictions, expected {grid.shape[0]} "
            f"for input {size}. This is not a standard YOLOX export."
        )
    out[:, :2] = (out[:, :2] + grid) * stride
    out[:, 2:4] = np.exp(out[:, 2:4]) * stride
    cx, cy, w, h = out[:, 0], out[:, 1], out[:, 2], out[:, 3]
    boxes = np.stack((cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2), 1)
    scores = out[:, 4] * out[:, 5 + PERSON_CLASS]
    return boxes, scores


def nms(boxes: np.ndarray, scores: np.ndarray, iou_thr: float) -> list[int]:
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        if order.size == 1:
            break
        rest = order[1:]
        xx1 = np.maximum(boxes[i, 0], boxes[rest, 0])
        yy1 = np.maximum(boxes[i, 1], boxes[rest, 1])
        xx2 = np.minimum(boxes[i, 2], boxes[rest, 2])
        yy2 = np.minimum(boxes[i, 3], boxes[rest, 3])
        inter = np.maximum(0, xx2 - xx1) * np.maximum(0, yy2 - yy1)
        area_i = (boxes[i, 2] - boxes[i, 0]) * (boxes[i, 3] - boxes[i, 1])
        area_r = (boxes[rest, 2] - boxes[rest, 0]) * (boxes[rest, 3] - boxes[rest, 1])
        iou = inter / (area_i + area_r - inter + 1e-9)
        order = rest[iou <= iou_thr]
    return keep


class PersonDetector:
    model_name = "yolox_nano (COCO, person class)"

    def __init__(self, model_path: Path, conf_threshold: float = 0.4, nms_threshold: float = 0.45):
        self.model_path = Path(model_path)
        self.conf_threshold = conf_threshold
        self.nms_threshold = nms_threshold
        if not self.model_path.is_file():
            raise ModelNotFoundError(
                f"Model weights not found at {self.model_path}. "
                "Run `python -m app.cv.fetch_model` (or POST /api/model/download) "
                "or place the file there manually."
            )
        try:
            import onnxruntime as ort

            self.session = ort.InferenceSession(
                str(self.model_path), providers=["CPUExecutionProvider"]
            )
        except Exception as e:  # corrupt file, wrong format, missing runtime...
            raise ModelLoadError(f"Could not load model {self.model_path}: {e}") from e

        inp = self.session.get_inputs()[0]
        shape = inp.shape
        if len(shape) != 4 or not all(isinstance(d, int) for d in shape[2:]):
            raise ModelLoadError(f"Unsupported model input shape {shape}; expected [1,3,H,W].")
        self.input_name = inp.name
        self.input_size = (int(shape[2]), int(shape[3]))
        out_shape = self.session.get_outputs()[0].shape
        if len(out_shape) != 3 or out_shape[-1] != NUM_VALUES:
            raise ModelLoadError(
                f"Unsupported model output shape {out_shape}; expected [1,N,{NUM_VALUES}] (YOLOX)."
            )

    def detect(self, frame_bgr: np.ndarray) -> list[Detection]:
        if frame_bgr is None or frame_bgr.ndim != 3:
            raise ValueError("detect() needs a BGR image array")
        h, w = frame_bgr.shape[:2]
        img, ratio = letterbox(frame_bgr, self.input_size)
        blob = np.ascontiguousarray(img.transpose(2, 0, 1)[None].astype(np.float32))
        raw = self.session.run(None, {self.input_name: blob})[0][0]
        boxes, scores = decode_yolox(raw, self.input_size)
        mask = scores >= self.conf_threshold
        boxes, scores = boxes[mask], scores[mask]
        if boxes.size == 0:
            return []
        boxes = boxes / ratio
        boxes[:, [0, 2]] = boxes[:, [0, 2]].clip(0, w - 1)
        boxes[:, [1, 3]] = boxes[:, [1, 3]].clip(0, h - 1)
        keep = nms(boxes, scores, self.nms_threshold)
        return [
            Detection(float(boxes[i, 0]), float(boxes[i, 1]), float(boxes[i, 2]),
                      float(boxes[i, 3]), float(scores[i]))
            for i in keep
            if boxes[i, 2] > boxes[i, 0] and boxes[i, 3] > boxes[i, 1]
        ]
