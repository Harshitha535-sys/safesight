"""Zone-violation logic: pure Python, no video or model dependencies (easy to test).

Rules
- A person's position is the bottom-centre of their bounding box.
- Entry is confirmed after `enter_frames` consecutive processed frames inside the zone.
- A violation event fires on confirmed entry unless that person already triggered one
  less than `cooldown_s` seconds ago (then it is counted as a suppressed entry).
- Staying inside never re-alerts. Leaving (confirmed after `exit_frames` consecutive
  frames outside) and re-entering can alert again once the cooldown has elapsed.
- Time is video time (seconds), not wall-clock time.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .detector import Detection
from .tracker import Tracker, Track
from .zone import RectZone, bottom_center


@dataclass
class MonitorParams:
    cooldown_s: float = 10.0
    enter_frames: int = 2
    exit_frames: int = 3
    max_age_s: float = 1.5
    iou_threshold: float = 0.2


@dataclass
class Event:
    id: int
    type: str  # "violation" | "exit"
    track_id: int
    t: float
    frame_index: int
    box: tuple[float, float, float, float]
    confidence: float | None
    point: tuple[float, float]
    duration_s: float | None = None
    reason: str | None = None
    snapshot: str | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id, "type": self.type, "track_id": self.track_id,
            "t": round(self.t, 3), "frame_index": self.frame_index,
            "box": [round(v, 1) for v in self.box],
            "confidence": None if self.confidence is None else round(self.confidence, 3),
            "point": [round(v, 1) for v in self.point],
            "duration_s": None if self.duration_s is None else round(self.duration_s, 3),
            "reason": self.reason, "snapshot": self.snapshot,
        }


@dataclass
class TrackedDetection:
    detection: Detection
    track_id: int
    point: tuple[float, float]
    in_zone: bool  # geometric: foot point inside zone on this frame
    violating: bool  # confirmed state: this person is currently in the zone


@dataclass
class StepResult:
    events: list[Event] = field(default_factory=list)
    tracked: list[TrackedDetection] = field(default_factory=list)


class ZoneMonitor:
    def __init__(self, zone: RectZone, frame_size: tuple[int, int], params: MonitorParams | None = None):
        self.zone = zone
        self.width, self.height = frame_size
        self.params = params or MonitorParams()
        self.tracker = Tracker(self.params.max_age_s, self.params.iou_threshold)
        self.events: list[Event] = []
        self.suppressed_entries = 0
        self._next_event_id = 1
        self._lost: list[tuple[float, tuple, float | None]] = []  # (t, box, last_alert_t) of people lost inside zone
        self._last_t = 0.0
        self._last_frame = 0

    def _emit(self, **kw) -> Event:
        ev = Event(id=self._next_event_id, **kw)
        self._next_event_id += 1
        self.events.append(ev)
        return ev

    def _close(self, tr: Track, t: float, frame_index: int, reason: str) -> Event:
        dur = (tr.last_inside_t - tr.entry_t) if tr.entry_t is not None and tr.last_inside_t is not None else None
        tr.in_zone = False
        return self._emit(type="exit", track_id=tr.id, t=t, frame_index=frame_index, box=tr.box,
                          confidence=None, point=bottom_center(tr.box), duration_s=dur, reason=reason)

    def update(self, t: float, frame_index: int, detections: list[Detection]) -> StepResult:
        p = self.params
        self._last_t, self._last_frame = t, frame_index
        matched, expired = self.tracker.update(t, detections)
        res = StepResult()

        for tr in expired:
            if tr.in_zone:
                self._lost.append((t, tr.box, tr.last_alert_t))
                res.events.append(self._close(tr, t, frame_index, "track_lost"))
        self._lost = [l for l in self._lost if t - l[0] <= p.cooldown_s]

        for tr, det in matched:
            pt = bottom_center(det.box)
            inside = self.zone.contains_point(pt[0], pt[1], self.width, self.height)
            if inside:
                tr.inside_streak += 1
                tr.outside_streak = 0
                tr.last_inside_t = t
            else:
                tr.outside_streak += 1
                tr.inside_streak = 0

            if not tr.in_zone and tr.inside_streak >= p.enter_frames:
                tr.in_zone = True
                tr.entry_t = t
                if tr.last_alert_t is None:
                    tr.last_alert_t = self._inherit_alert_time(det)
                if tr.last_alert_t is None or (t - tr.last_alert_t) >= p.cooldown_s:
                    tr.last_alert_t = t
                    res.events.append(self._emit(
                        type="violation", track_id=tr.id, t=t, frame_index=frame_index,
                        box=det.box, confidence=det.confidence, point=pt))
                else:
                    self.suppressed_entries += 1
            elif tr.in_zone and tr.outside_streak >= p.exit_frames:
                res.events.append(self._close(tr, t, frame_index, "left_zone"))

            res.tracked.append(TrackedDetection(det, tr.id, pt, inside, tr.in_zone))
        return res

    def _inherit_alert_time(self, det: Detection) -> float | None:
        """A new track appearing right where someone was just lost inside the zone is most
        likely that same (briefly occluded) person: inherit their alert time so the cooldown
        applies instead of raising a duplicate alert. Trade-off: a different person entering
        the same spot within the cooldown is also suppressed."""
        cx, cy = (det.x1 + det.x2) / 2, (det.y1 + det.y2) / 2
        best = None
        for t_lost, box, alert_t in self._lost:
            if alert_t is None:
                continue
            lx, ly = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            if ((cx - lx) ** 2 + (cy - ly) ** 2) ** 0.5 <= 1.5 * (box[3] - box[1]):
                best = alert_t if best is None else max(best, alert_t)
        return best

    def finalize(self) -> list[Event]:
        """Close people still in the zone when the video ends."""
        out = []
        for tr in self.tracker.tracks:
            if tr.in_zone:
                out.append(self._close(tr, self._last_t, self._last_frame, "end_of_video"))
        return out
