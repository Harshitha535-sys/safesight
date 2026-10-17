"""Event-logic tests. These feed hand-written coordinate sequences into ZoneMonitor to test
the rules (entry, cooldown, exit, re-entry). They are logic tests, not detector results."""
from app.cv.detector import Detection
from app.cv.monitor import MonitorParams, ZoneMonitor
from app.cv.zone import RectZone

W = H = 1000
ZONE = RectZone(0.4, 0.4, 0.8, 0.8)  # pixels 400..800
DT = 0.2  # seconds between processed frames


def det(foot_x, foot_y, conf=0.9):
    """Person box whose bottom-centre is (foot_x, foot_y)."""
    return Detection(foot_x - 40, foot_y - 200, foot_x + 40, foot_y, conf)


def run(monitor, script, start_frame=0):
    """script: list of lists of Detection (one list per processed frame)."""
    events = []
    for i, dets in enumerate(script):
        events += monitor.update((start_frame + i) * DT, start_frame + i, dets).events
    return events


def walk(x0, x1, y, steps):
    return [[det(x0 + (x1 - x0) * i / (steps - 1), y)] for i in range(steps)]


def vwalk(x, y0, y1, steps):
    """Person moving vertically in small steps (continuous motion, like a real walker)."""
    return [[det(x, y0 + (y1 - y0) * i / (steps - 1))] for i in range(steps)]


def mk(**kw):
    return ZoneMonitor(ZONE, (W, H), MonitorParams(**kw))


def types(events):
    return [e.type for e in events]


def test_person_outside_never_triggers():
    m = mk()
    assert run(m, [[det(100, 900)] for _ in range(30)]) == []


def test_entry_creates_one_violation_and_staying_does_not_repeat():
    m = mk(cooldown_s=5)
    script = walk(100, 600, 600, 20) + [[det(600, 600)] for _ in range(100)]  # enters, then stays 20 s
    ev = run(m, script)
    assert types(ev) == ["violation"]
    assert ev[0].track_id == 1 and ev[0].confidence == 0.9


def test_violation_uses_foot_point_position():
    m = mk()
    ev = run(m, [[det(600, 600)]] * 3)
    assert ev[0].point == (600.0, 600)


def test_single_frame_blip_ignored_with_enter_frames_2():
    m = mk(enter_frames=2)
    script = [[det(300, 600)], [det(600, 600)], [det(300, 600)], [det(300, 600)]]
    assert run(m, script) == []


def test_exit_then_reentry_after_cooldown_gives_second_violation():
    m = mk(cooldown_s=3, exit_frames=2)
    script = (
        [[det(600, 600)]] * 4                     # enter (t≈0.2)
        + vwalk(600, 600, 900, 8)                 # walk out (feet end below zone)
        + [[det(600, 900)]] * 20                  # stay away > cooldown
        + vwalk(600, 900, 600, 8)                 # walk back in
    )
    ev = run(m, script)
    assert types(ev) == ["violation", "exit", "violation"]
    assert ev[1].reason == "left_zone"
    assert ev[2].t - ev[0].t >= 3


def test_reentry_within_cooldown_is_suppressed_and_counted():
    m = mk(cooldown_s=60, exit_frames=2)
    script = [[det(600, 600)]] * 4 + vwalk(600, 600, 900, 8) + vwalk(600, 900, 600, 8)
    ev = run(m, script)
    assert types(ev) == ["violation", "exit"]
    assert m.suppressed_entries == 1


def test_exit_event_reports_duration():
    m = mk(exit_frames=2)
    script = [[det(600, 600)]] * 11 + vwalk(600, 620, 900, 10)  # inside frames t=0..2.0 (+ a few while walking out)
    ev = run(m, script)
    exit_ev = [e for e in ev if e.type == "exit"][0]
    assert exit_ev.reason == "left_zone"
    entry = [e for e in ev if e.type == "violation"][0]
    # duration = last frame with feet inside (y<=800) minus confirmed entry time
    assert exit_ev.duration_s > 1.5 and exit_ev.t > entry.t + exit_ev.duration_s


def test_short_detection_dropout_keeps_same_person_no_new_alert():
    m = mk(cooldown_s=5, max_age_s=1.5)
    script = [[det(600, 600)]] * 4 + [[]] * 3 + [[det(600, 600)]] * 4  # 0.6 s gap
    ev = run(m, script)
    assert types(ev) == ["violation"]


def test_two_people_get_separate_violations():
    m = mk()
    script = [[det(500, 500), det(700, 700)]] * 4
    ev = run(m, script)
    assert types(ev) == ["violation", "violation"]
    assert len({e.track_id for e in ev}) == 2


def test_track_lost_inside_zone_closes_with_reason():
    m = mk(max_age_s=1.0)
    script = [[det(600, 600)]] * 4 + [[]] * 10
    ev = run(m, script)
    assert types(ev) == ["violation", "exit"]
    assert ev[1].reason == "track_lost"


def test_finalize_closes_people_still_inside():
    m = mk()
    run(m, [[det(600, 600)]] * 5)
    closing = m.finalize()
    assert [e.reason for e in closing] == ["end_of_video"]


def test_tracked_flags_in_step_result():
    m = mk()
    r1 = m.update(0.0, 0, [det(600, 600)])
    r2 = m.update(0.2, 1, [det(600, 600)])
    assert r1.tracked[0].in_zone and not r1.tracked[0].violating  # not confirmed yet
    assert r2.tracked[0].violating


def test_reappearing_after_occlusion_in_zone_does_not_realert_within_cooldown():
    """Person vanishes inside the zone (occluded), returns as a new track next to the same spot."""
    m = mk(cooldown_s=10, max_age_s=1.0)
    script = [[det(600, 600)]] * 4 + [[]] * 8 + [[det(610, 600)]] * 4  # ~1.6 s gap > max_age
    ev = run(m, script)
    assert types(ev) == ["violation", "exit"]
    assert ev[1].reason == "track_lost"
    assert m.suppressed_entries == 1


def test_different_person_far_away_still_alerts_after_a_loss():
    m = mk(cooldown_s=10, max_age_s=1.0)
    script = [[det(450, 450)]] * 4 + [[]] * 8 + [[det(780, 780)]] * 4
    ev = run(m, script)
    assert types(ev).count("violation") == 2
