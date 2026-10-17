"""CLI: python -m app.cv.run_video VIDEO --zone X1 Y1 X2 Y2 [--out result.json] [--snapshots DIR]
Zone is normalized (0..1). Runs the real detector; fails loudly if the model is unavailable."""
import argparse
import json
import sys
from pathlib import Path

from ..config import settings
from .detector import PersonDetector
from .errors import SafeSightError
from .monitor import MonitorParams
from .pipeline import PipelineParams, process_video
from .zone import RectZone


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--zone", type=float, nargs=4, required=True, metavar=("X1", "Y1", "X2", "Y2"))
    ap.add_argument("--process-fps", type=float, default=5.0)
    ap.add_argument("--cooldown", type=float, default=10.0)
    ap.add_argument("--conf", type=float, default=settings.conf_threshold)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--snapshots", type=Path)
    a = ap.parse_args()
    try:
        det = PersonDetector(settings.model_path, conf_threshold=a.conf)
        res = process_video(a.video, det, RectZone(*a.zone),
                            PipelineParams(a.process_fps, MonitorParams(cooldown_s=a.cooldown), a.snapshots))
    except (SafeSightError, ValueError) as e:
        print(f"ERROR [{getattr(e, 'code', 'invalid_input')}]: {e}", file=sys.stderr)
        return 1
    if a.out:
        a.out.write_text(json.dumps(res))
    print(json.dumps({k: res[k] for k in ("video", "zone", "processing", "summary", "warnings")}, indent=2))
    for e in res["events"]:
        print(f"  {e['type']:<9} t={e['t']:>6}s track=#{e['track_id']} {e.get('reason') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
