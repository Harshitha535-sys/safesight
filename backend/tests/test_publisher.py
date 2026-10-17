import json, tempfile, unittest
from datetime import datetime, timezone
from pathlib import Path

from app.publisher import EventPublisher, build_message, publish_events


class PublisherTests(unittest.TestCase):
    def test_jsonl_only_violations_and_schema(self):
        with tempfile.TemporaryDirectory() as d:
            pub = EventPublisher(jsonl_path=Path(d) / "e.jsonl")
            evs = [{"type": "violation", "track_id": 3, "t": 12.5, "confidence": 0.8, "snapshot": "a.jpg"},
                   {"type": "exit", "track_id": 3, "t": 20.0}]
            n = publish_events(pub, evs, job_id="j1", source="v.mp4",
                               started_at=datetime(2026, 1, 1, tzinfo=timezone.utc))
            self.assertEqual(n, 1)
            lines = (Path(d) / "e.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            m = json.loads(lines[0])
            self.assertEqual(m["schema"], "safesight.event.v1")
            self.assertEqual(m["occurred_at"], "2026-01-01T00:00:12.500000Z")
            self.assertEqual(m["severity"], "critical")

    def test_mqtt_failure_is_contained(self):
        with tempfile.TemporaryDirectory() as d:
            pub = EventPublisher(jsonl_path=Path(d) / "e.jsonl", mqtt_host="127.0.0.1", mqtt_port=1)
            self.assertFalse(pub.mqtt_enabled)
            self.assertTrue(pub.publish(build_message({"type": "violation", "t": 1}, job_id="j", source="s",
                            zone_id="z", started_at=datetime.now(timezone.utc)))["jsonl"])


if __name__ == "__main__":
    unittest.main()
