"""Tests for the SQLite incident layer, demo mode, persistence bridge and monitoring status.
Run:  cd backend && python -m unittest discover -s tests -v   (or: pytest -q)"""
import os
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from app.db import IncidentStore, make_dedupe_key, to_iso
from app.demo import DEMO_WARNING, demo_events, load_demo
from app.monitoring import monitoring_status
from app.persist import persist_job_events

T0 = "2026-03-10T10:00:00Z"


def add(store, **kw):
    base = dict(event_type="violation", source="a.mp4", job_id="j1", track_id=1, video_time_s=5.0, occurred_at=T0)
    base.update(kw)
    return store.add(**base)


class StoreCase(unittest.TestCase):
    def setUp(self):
        self.s = IncidentStore(":memory:")

    def tearDown(self):
        self.s.close()


class TestCreateAndDuplicates(StoreCase):
    def test_create_stores_all_fields(self):
        rec, created = add(self.s, confidence=0.87, zone_id="zone-1", description="d", snapshot="x.jpg")
        self.assertTrue(created)
        self.assertEqual((rec["id"], rec["event_type"], rec["severity"], rec["confidence"], rec["zone_id"]), (1, "violation", "critical", 0.87, "zone-1"))
        self.assertEqual((rec["source"], rec["processing_mode"], rec["occurred_at"], rec["acknowledged"], rec["simulated"]), ("a.mp4", "ai", T0, False, False))

    def test_confidence_optional(self):
        rec, _ = add(self.s)
        self.assertIsNone(rec["confidence"])

    def test_duplicate_returns_existing_not_new_row(self):
        a, c1 = add(self.s)
        b, c2 = add(self.s)
        self.assertTrue(c1)
        self.assertFalse(c2)
        self.assertEqual(a["id"], b["id"])
        self.assertEqual(self.s.list()[1], 1)

    def test_distinct_events_are_not_duplicates(self):
        add(self.s); add(self.s, track_id=2); add(self.s, video_time_s=9.0); add(self.s, job_id="j2"); add(self.s, event_type="zone_proximity")
        self.assertEqual(self.s.list()[1], 5)

    def test_same_event_in_demo_and_ai_are_distinct(self):
        add(self.s); add(self.s, processing_mode="demo")
        self.assertEqual(self.s.list()[1], 2)

    def test_explicit_dedupe_key(self):
        add(self.s, dedupe_key="k"); _, c = add(self.s, dedupe_key="k", track_id=99)
        self.assertFalse(c)

    def test_dedupe_key_stable(self):
        a = make_dedupe_key("ai", "j", "violation", 1, "z", 5.0, T0)
        self.assertEqual(a, make_dedupe_key("ai", "j", "violation", 1, "z", 5.0, T0))
        self.assertNotEqual(a, make_dedupe_key("ai", "j", "violation", 2, "z", 5.0, T0))


class TestInvalidInputs(StoreCase):
    def test_rejects_bad_values(self):
        for kw in (dict(severity="bogus"), dict(processing_mode="live"), dict(confidence=1.5), dict(confidence=-0.1),
                   dict(event_type="  "), dict(source=""), dict(occurred_at="not-a-date")):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                add(self.s, **kw)
        self.assertEqual(self.s.list()[1], 0)

    def test_bad_filters(self):
        for kw in (dict(severity="x"), dict(include="x"), dict(date_from="2026-13-01"), dict(date_to="yesterday")):
            with self.subTest(kw=kw), self.assertRaises(ValueError):
                self.s.list(**kw)
        with self.assertRaises(ValueError):
            self.s.list(limit=0)
        with self.assertRaises(ValueError):
            self.s.list(offset=-1)

    def test_sql_injection_text_is_inert(self):
        add(self.s, source="x'; DROP TABLE incidents;--")
        rows, total = self.s.list(q="'; DROP")
        self.assertEqual(total, 1)
        self.assertEqual(self.s.list()[1], 1)


class TestPersistence(unittest.TestCase):
    def test_survives_reopen(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "sub" / "t.db"
            s = IncidentStore(p)
            rec, _ = add(s, confidence=0.5)
            s.acknowledge(rec["id"])
            s.close()
            s2 = IncidentStore(p)
            got = s2.get(rec["id"])
            self.assertEqual((got["event_type"], got["confidence"], got["acknowledged"]), ("violation", 0.5, True))
            _, created = add(s2, confidence=0.5)  # duplicate protection also survives restarts
            self.assertFalse(created)
            s2.close()

    def test_default_path_uses_env(self):
        with tempfile.TemporaryDirectory() as d, mock.patch.dict(os.environ, {"SAFESIGHT_DB": str(Path(d) / "e.db")}):
            s = IncidentStore(); add(s); s.close()
            self.assertTrue((Path(d) / "e.db").exists())


class TestRetrieval(StoreCase):
    def setUp(self):
        super().setUp()
        add(self.s, occurred_at="2026-03-08T09:00:00Z", track_id=1, source="a.mp4", description="Person in zone")
        add(self.s, occurred_at="2026-03-09T09:00:00Z", track_id=2, source="b.mp4", event_type="zone_proximity", severity="warning")
        add(self.s, occurred_at="2026-03-10T09:00:00Z", track_id=3, source="c_100%.mp4")
        add(self.s, occurred_at="2026-03-10T11:00:00Z", track_id=4, processing_mode="demo", source="demo-simulator")

    def test_get_and_missing(self):
        self.assertEqual(self.s.get(2)["event_type"], "zone_proximity")
        self.assertIsNone(self.s.get(999))

    def test_order_newest_first_and_pagination(self):
        rows, total = self.s.list()
        self.assertEqual([r["track_id"] for r in rows], [4, 3, 2, 1])
        self.assertEqual(total, 4)
        page, total = self.s.list(limit=2, offset=2)
        self.assertEqual([r["track_id"] for r in page], [2, 1])
        self.assertEqual(total, 4)

    def test_filters(self):
        self.assertEqual(self.s.list(severity="warning")[1], 1)
        self.assertEqual(self.s.list(event_type="violation")[1], 3)
        self.assertEqual(self.s.list(include="ai")[1], 3)
        self.assertEqual(self.s.list(include="demo")[1], 1)
        self.assertEqual(self.s.list(source="b.mp4")[1], 1)
        self.assertEqual(self.s.list(date_from="2026-03-09", date_to="2026-03-09")[1], 1)
        self.assertEqual(self.s.list(date_from="2026-03-10")[1], 2)
        self.assertEqual(self.s.list(acknowledged=True)[1], 0)
        self.assertEqual(self.s.list(acknowledged=False)[1], 4)

    def test_search_and_wildcard_escaping(self):
        self.assertEqual(self.s.list(q="person in")[1], 1)
        self.assertEqual(self.s.list(q="100%")[1], 1)   # literal %, not a wildcard
        self.assertEqual(self.s.list(q="%")[1], 1)
        self.assertEqual(self.s.list(q="nomatch")[1], 0)


class TestAcknowledge(StoreCase):
    def test_ack_reopen_idempotent_missing(self):
        rec, _ = add(self.s)
        a = self.s.acknowledge(rec["id"], now="2026-03-10T12:00:00Z")
        self.assertTrue(a["acknowledged"])
        self.assertEqual(a["acknowledged_at"], "2026-03-10T12:00:00Z")
        again = self.s.acknowledge(rec["id"], now="2026-03-11T12:00:00Z")
        self.assertEqual(again["acknowledged_at"], "2026-03-10T12:00:00Z")  # first timestamp kept
        re = self.s.acknowledge(rec["id"], False)
        self.assertEqual((re["acknowledged"], re["acknowledged_at"]), (False, None))
        self.assertIsNone(self.s.acknowledge(12345))

    def test_filter_by_ack(self):
        a, _ = add(self.s); add(self.s, track_id=2)
        self.s.acknowledge(a["id"])
        self.assertEqual(self.s.list(acknowledged=True)[1], 1)
        self.assertEqual(self.s.list(acknowledged=False)[1], 1)


class TestAnalytics(StoreCase):
    NOW = datetime(2026, 3, 10, 15, 0, tzinfo=timezone.utc)

    def setUp(self):
        super().setUp()
        add(self.s, occurred_at="2026-03-09T09:00:00Z", track_id=1)
        add(self.s, occurred_at="2026-03-10T09:00:00Z", track_id=2)
        add(self.s, occurred_at="2026-03-10T10:00:00Z", track_id=3, event_type="zone_proximity", severity="warning")
        a, _ = add(self.s, occurred_at="2026-03-10T11:00:00Z", track_id=4)
        self.s.acknowledge(a["id"])
        for i in range(2):
            add(self.s, occurred_at="2026-03-10T12:00:00Z", track_id=10 + i, processing_mode="demo", source="demo-simulator")

    def test_counts_ai_only_by_default_semantics(self):
        r = self.s.summary(include="ai", now=self.NOW)
        self.assertEqual((r["total"], r["today"], r["unacknowledged"]), (4, 3, 3))
        self.assertEqual(r["by_severity"], {"critical": 3, "warning": 1, "info": 0})
        self.assertEqual(r["by_event_type"], {"violation": 3, "zone_proximity": 1})
        self.assertEqual(r["by_day"], [{"day": "2026-03-09", "count": 1}, {"day": "2026-03-10", "count": 3}])
        self.assertEqual(r["latest_at"], "2026-03-10T11:00:00Z")

    def test_origin_never_mixed_silently(self):
        ai, demo, both = (self.s.summary(include=i, now=self.NOW) for i in ("ai", "demo", "all"))
        self.assertEqual((ai["total"], demo["total"], both["total"]), (4, 2, 6))
        for r in (ai, demo, both):
            self.assertEqual(r["by_origin"], {"ai": 4, "demo": 2})
        self.assertEqual(demo["by_event_type"], {"violation": 2})

    def test_filters_apply_and_empty_db(self):
        self.assertEqual(self.s.summary(include="ai", severity="warning", now=self.NOW)["total"], 1)
        e = IncidentStore(":memory:").summary(now=self.NOW)
        self.assertEqual((e["total"], e["today"], e["by_day"], e["latest_at"]), (0, 0, [], None))
        self.assertEqual(e["by_severity"], {"critical": 0, "warning": 0, "info": 0})


class TestExport(StoreCase):
    def test_csv_header_rows_and_filters(self):
        add(self.s, description="hello, \"world\"")
        add(self.s, track_id=2, processing_mode="demo", source="demo-simulator")
        out = self.s.to_csv(include="all").strip().splitlines()
        self.assertTrue(out[0].startswith("id,occurred_at,event_type,severity,confidence"))
        self.assertEqual(len(out), 3)
        self.assertIn("simulated", self.s.to_csv(include="demo"))
        self.assertEqual(len(self.s.to_csv(include="ai").strip().splitlines()), 2)

    def test_csv_formula_injection_neutralised(self):
        add(self.s, source="=HYPERLINK(\"http://x\")")
        self.assertIn("'=HYPERLINK", self.s.to_csv())


class TestDemoMode(StoreCase):
    def test_warning_text_exact(self):
        self.assertEqual(DEMO_WARNING, "DEMO MODE — Events are simulated and do not represent live AI detections.")

    def test_deterministic(self):
        self.assertEqual(demo_events(), demo_events())
        self.assertEqual(len(demo_events()), 8)

    def test_events_clearly_simulated_and_no_fake_confidence(self):
        for e in demo_events():
            self.assertEqual(e["processing_mode"], "demo")
            self.assertTrue(e["description"].startswith("[SIMULATED]"))
            self.assertIsNone(e["confidence"])

    def test_load_idempotent_and_flagged(self):
        self.assertEqual(load_demo(self.s), {"inserted": 8, "already_present": 0})
        self.assertEqual(load_demo(self.s), {"inserted": 0, "already_present": 8})
        rows, total = self.s.list()
        self.assertEqual(total, 8)
        self.assertTrue(all(r["simulated"] for r in rows))
        self.assertEqual(self.s.list(include="ai")[1], 0)
        self.assertEqual(self.s.summary(include="ai")["total"], 0)  # default analytics exclude demo data

    def test_delete_only_demo(self):
        add(self.s); load_demo(self.s)
        self.assertEqual(self.s.delete_mode("demo"), 8)
        self.assertEqual(self.s.list()[1], 1)
        with self.assertRaises(ValueError):
            self.s.delete_mode("x")


class TestPersistBridge(StoreCase):
    EVENTS = [
        {"type": "violation", "time_s": 12.4, "track_id": 3, "confidence": 0.9, "snapshot": "data/snap/j/v1.jpg"},
        {"type": "violation", "time_s": 40, "track_id": 4},
        "garbage",
        {"event_type": "note", "t": 2},
    ]

    def test_maps_and_wallclock(self):
        r = persist_job_events(self.s, job_id="j9", source="cam.mp4", events=self.EVENTS, zone_id="zone-1", job_started_at="2026-03-10T10:00:00Z")
        self.assertEqual(r, {"inserted": 3, "duplicates": 0, "skipped": 1})
        rows, _ = self.s.list(source="cam.mp4")
        first = [x for x in rows if x["track_id"] == 3][0]
        self.assertEqual((first["occurred_at"], first["confidence"], first["snapshot"], first["severity"]), ("2026-03-10T10:00:12Z", 0.9, "v1.jpg", "critical"))
        self.assertEqual([x for x in rows if x["event_type"] == "note"][0]["severity"], "warning")

    def test_rerun_does_not_duplicate(self):
        kw = dict(job_id="j9", source="cam.mp4", events=self.EVENTS, job_started_at="2026-03-10T10:00:00Z")
        persist_job_events(self.s, **kw)
        again = persist_job_events(self.s, **kw)
        self.assertEqual((again["inserted"], again["duplicates"]), (0, 3))
        self.assertEqual(self.s.list()[1], 3)

    def test_empty_and_bad_confidence(self):
        self.assertEqual(persist_job_events(self.s, job_id="j", source="s", events=None)["inserted"], 0)
        persist_job_events(self.s, job_id="j", source="s", events=[{"type": "violation", "time_s": 1, "confidence": 7}])
        self.assertIsNone(self.s.list()[0][0]["confidence"])


class TestMonitoring(StoreCase):
    def test_model_missing_means_demo_with_warning(self):
        s = monitoring_status(self.s, model_path="/nonexistent/model.onnx")
        self.assertEqual((s["mode"], s["demo"], s["warning"], s["model_present"]), ("demo", True, DEMO_WARNING, False))
        self.assertFalse(s["camera"]["available"])
        self.assertEqual(s["database"], {"ok": True, "engine": "sqlite", "incidents": 0})

    def test_model_present_means_ai(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as f:
            f.write(b"x"); f.flush()
            s = monitoring_status(self.s, model_path=f.name)
        self.assertEqual((s["mode"], s["demo"], s["warning"]), ("ai", False, None))

    def test_forced_demo_and_empty_model_file(self):
        with tempfile.NamedTemporaryFile(suffix=".onnx") as f:
            f.write(b"x"); f.flush()
            with mock.patch.dict(os.environ, {"SAFESIGHT_DEMO": "1"}):
                self.assertTrue(monitoring_status(self.s, model_path=f.name)["demo"])
        with tempfile.NamedTemporaryFile(suffix=".onnx") as f:  # zero bytes = unusable
            self.assertEqual(monitoring_status(self.s, model_path=f.name)["mode"], "demo")

    def test_db_down_reported(self):
        self.s.close()
        self.assertFalse(monitoring_status(self.s, model_path="/x")["database"]["ok"])


# ---- HTTP layer: needs fastapi + httpx; skipped (not faked) when unavailable -------------
try:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.api.incidents import get_store, router
    HAVE_API = True
except Exception:  # pragma: no cover
    HAVE_API = False


@unittest.skipUnless(HAVE_API, "fastapi/httpx not installed")
class TestApi(unittest.TestCase):
    def setUp(self):
        self.store = IncidentStore(":memory:")
        app = FastAPI()
        app.include_router(router)
        app.dependency_overrides[get_store] = lambda: self.store
        self.c = TestClient(app)
        add(self.store)

    def test_list_get_ack(self):
        self.assertEqual(self.c.get("/api/incidents").json()["total"], 1)
        self.assertEqual(self.c.get("/api/incidents/1").json()["event_type"], "violation")
        r = self.c.patch("/api/incidents/1/acknowledge")
        self.assertTrue(r.json()["acknowledged"])
        self.assertFalse(self.c.patch("/api/incidents/1/acknowledge", json={"acknowledged": False}).json()["acknowledged"])

    def test_not_found_and_invalid(self):
        self.assertEqual(self.c.get("/api/incidents/99").status_code, 404)
        self.assertEqual(self.c.patch("/api/incidents/99/acknowledge").status_code, 404)
        for url in ("/api/incidents/abc", "/api/incidents/0", "/api/incidents?severity=bogus", "/api/incidents?limit=0",
                    "/api/incidents?limit=100000", "/api/incidents?date_from=nope", "/api/incidents?include=x",
                    "/api/analytics/summary?date_to=2026-99-99", "/api/incidents/export?format=xml"):
            with self.subTest(url=url):
                self.assertEqual(self.c.get(url).status_code, 422)

    def test_export_not_shadowed_by_id_route(self):
        r = self.c.get("/api/incidents/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["content-type"])
        self.assertEqual(self.c.get("/api/incidents/export?format=json").json()[0]["id"], 1)

    def test_summary_monitoring_demo(self):
        self.assertEqual(self.c.get("/api/analytics/summary").json()["total"], 1)
        self.assertEqual(self.c.post("/api/demo/events").json()["inserted"], 8)
        self.assertEqual(self.c.get("/api/analytics/summary").json()["total"], 1)  # demo excluded by default
        self.assertEqual(self.c.get("/api/analytics/summary?include=all").json()["total"], 9)
        self.assertIn("mode", self.c.get("/api/monitoring/status").json())
        self.assertEqual(self.c.delete("/api/demo/events").json()["deleted"], 8)


if __name__ == "__main__":
    unittest.main()
