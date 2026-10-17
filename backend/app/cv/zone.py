"""Rectangular restricted zone, stored in normalized (0..1) frame coordinates
so it is independent of video resolution."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RectZone:
    x1: float
    y1: float
    x2: float
    y2: float

    def __post_init__(self) -> None:
        for name in ("x1", "y1", "x2", "y2"):
            v = getattr(self, name)
            if not (0.0 <= v <= 1.0):
                raise ValueError(f"zone {name}={v} must be between 0 and 1")
        if not (self.x1 < self.x2 and self.y1 < self.y2):
            raise ValueError("zone must satisfy x1 < x2 and y1 < y2")

    def to_pixels(self, width: int, height: int) -> tuple[float, float, float, float]:
        return (self.x1 * width, self.y1 * height, self.x2 * width, self.y2 * height)

    def contains_point(self, x: float, y: float, width: int, height: int) -> bool:
        """Pixel point inside zone; edges count as inside."""
        px1, py1, px2, py2 = self.to_pixels(width, height)
        return px1 <= x <= px2 and py1 <= y <= py2

    def to_dict(self) -> dict:
        return {"x1": self.x1, "y1": self.y1, "x2": self.x2, "y2": self.y2}


def bottom_center(box: tuple[float, float, float, float]) -> tuple[float, float]:
    """Foot-point proxy of a person's bounding box (x1, y1, x2, y2)."""
    x1, _, x2, y2 = box
    return ((x1 + x2) / 2.0, y2)
