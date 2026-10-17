"""Actionable output: every confirmed event is emitted as a JSON message.

Sinks (all optional, failures never break processing):
  * JSON Lines file   data/events.jsonl            (always on)
  * MQTT              topic  safesight/<zone>/events   (on when SAFESIGHT_MQTT_HOST is set and paho-mqtt is installed)

Message schema (also documented in docs/API.md):
  {"schema":"safesight.event.v1","incident_id":..,"type":"violation|exit","severity":..,"zone_id":..,
   "source":..,"job_id":..,"track_id":..,"video_time_s":..,"confidence":..,"occurred_at":ISO8601,"snapshot":..}
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

log = logging.getLogger("safesight.publisher")
SCHEMA = "safesight.event.v1"


class EventPublisher:
    def __init__(self, jsonl_path: Optional[Path] = None, mqtt_host: Optional[str] = None,
                 mqtt_port: int = 1883, topic_prefix: str = "safesight"):
        self.jsonl_path = Path(jsonl_path) if jsonl_path else None
        self.topic_prefix = topic_prefix
        self._lock = threading.Lock()
        self._client = None
        self.mqtt_error: Optional[str] = None
        if mqtt_host:
            try:
                import paho.mqtt.client as mqtt  # optional dependency
                try:
                    self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)  # paho >= 2
                except AttributeError:
                    self._client = mqtt.Client()  # paho 1.x
                self._client.connect(mqtt_host, mqtt_port, keepalive=30)
                self._client.loop_start()
            except Exception as e:  # missing package or broker down
                self._client = None
                self.mqtt_error = f"{type(e).__name__}: {e}"
                log.warning("MQTT disabled: %s", self.mqtt_error)

    @classmethod
    def from_env(cls, data_dir: Path) -> "EventPublisher":
        return cls(jsonl_path=Path(os.environ.get("SAFESIGHT_EVENTS_JSONL", data_dir / "events.jsonl")),
                   mqtt_host=os.environ.get("SAFESIGHT_MQTT_HOST") or None,
                   mqtt_port=int(os.environ.get("SAFESIGHT_MQTT_PORT", "1883")),
                   topic_prefix=os.environ.get("SAFESIGHT_MQTT_PREFIX", "safesight"))

    @property
    def mqtt_enabled(self) -> bool:
        return self._client is not None

    def publish(self, message: dict) -> dict:
        """Send one message to every sink. Returns {'jsonl': bool, 'mqtt': bool}."""
        payload = json.dumps(message, separators=(",", ":"))
        sent = {"jsonl": False, "mqtt": False}
        if self.jsonl_path:
            try:
                with self._lock:
                    self.jsonl_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.jsonl_path, "a", encoding="utf-8") as f:
                        f.write(payload + "\n")
                sent["jsonl"] = True
            except OSError as e:
                log.warning("JSONL write failed: %s", e)
        if self._client is not None:
            try:
                topic = f"{self.topic_prefix}/{message.get('zone_id', 'zone-1')}/events"
                info = self._client.publish(topic, payload, qos=1)
                sent["mqtt"] = info.rc == 0
            except Exception as e:
                log.warning("MQTT publish failed: %s", e)
        return sent

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass


def build_message(ev: dict, *, job_id: str, source: str, zone_id: str, started_at: datetime) -> dict:
    t = ev.get("t")
    when = started_at + timedelta(seconds=t or 0)
    return {
        "schema": SCHEMA, "type": ev.get("type", "violation"),
        "severity": "critical" if ev.get("type", "violation") == "violation" else "info",
        "zone_id": zone_id, "source": source, "job_id": job_id, "track_id": ev.get("track_id"),
        "video_time_s": t, "confidence": ev.get("confidence"),
        "occurred_at": when.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "snapshot": ev.get("snapshot"),
    }


def publish_events(pub: EventPublisher, events: Iterable[dict], *, job_id: str, source: str,
                   zone_id: str = "zone-1", started_at: Optional[datetime] = None) -> int:
    started_at = started_at or datetime.now(timezone.utc)
    n = 0
    for ev in events or []:
        if isinstance(ev, dict) and ev.get("type") == "violation":  # only alerts go to actuators/subscribers
            pub.publish(build_message(ev, job_id=job_id, source=source, zone_id=zone_id, started_at=started_at))
            n += 1
    return n
