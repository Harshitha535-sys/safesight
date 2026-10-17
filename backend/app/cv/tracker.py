"""Minimal IoU/centre-distance tracker. Gives people a stable ID between frames so that
zone state (entered / still inside / exited) can be tracked per person."""
from __future__ import annotations

from dataclasses import dataclass
from itertools import count

from .detector import Detection


def iou(a: tuple, b: tuple) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


@dataclass
class Track:
    id: int
    box: tuple[float, float, float, float]
    last_seen_t: float
    # zone state (managed by ZoneMonitor)
    in_zone: bool = False
    inside_streak: int = 0
    outside_streak: int = 0
    entry_t: float | None = None
    last_inside_t: float | None = None
    last_alert_t: float | None = None


class Tracker:
    def __init__(self, max_age_s: float = 1.5, iou_threshold: float = 0.2):
        self.max_age_s = max_age_s
        self.iou_threshold = iou_threshold
        self.tracks: list[Track] = []
        self._ids = count(1)

    def update(self, t: float, detections: list[Detection]):
        """Returns (matched [(Track, Detection)], expired [Track])."""
        pairs = sorted(
            ((iou(tr.box, d.box), ti, di)
             for ti, tr in enumerate(self.tracks) for di, d in enumerate(detections)),
            reverse=True,
        )
        used_t: set[int] = set()
        used_d: set[int] = set()
        matched: list[tuple[Track, Detection]] = []

        def take(ti: int, di: int) -> None:
            used_t.add(ti)
            used_d.add(di)
            tr = self.tracks[ti]
            tr.box = detections[di].box
            tr.last_seen_t = t
            matched.append((tr, detections[di]))

        for score, ti, di in pairs:
            if score < self.iou_threshold:
                break
            if ti not in used_t and di not in used_d:
                take(ti, di)

        # second pass: centre distance for fast movers with low IoU
        for ti, tr in enumerate(self.tracks):
            if ti in used_t:
                continue
            tcx, tcy = (tr.box[0] + tr.box[2]) / 2, (tr.box[1] + tr.box[3]) / 2
            th = tr.box[3] - tr.box[1]
            best, best_d = None, 0.6 * th
            for di, d in enumerate(detections):
                if di in used_d:
                    continue
                dist = ((tcx - (d.x1 + d.x2) / 2) ** 2 + (tcy - (d.y1 + d.y2) / 2) ** 2) ** 0.5
                if dist < best_d:
                    best, best_d = di, dist
            if best is not None:
                take(ti, best)

        for di, d in enumerate(detections):
            if di not in used_d:
                tr = Track(id=next(self._ids), box=d.box, last_seen_t=t)
                self.tracks.append(tr)
                matched.append((tr, d))

        expired = [tr for tr in self.tracks if t - tr.last_seen_t > self.max_age_s]
        if expired:
            self.tracks = [tr for tr in self.tracks if tr not in expired]
        return matched, expired
