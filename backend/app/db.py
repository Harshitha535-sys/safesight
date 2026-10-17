"""SQLite incident store (standard library only).

Default file: backend/data/safesight.db (override with SAFESIGHT_DB).
Every incident records its origin in `processing_mode`: 'ai' (real detection)
or 'demo' (simulated). Nothing here mixes the two silently: queries take an
`include` argument ('ai' | 'demo' | 'all') and every row carries `simulated`.
"""
import csv
import hashlib
import io
import os
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SEVERITIES = ("critical", "warning", "info")
MODES = ("ai", "demo")
INCLUDES = ("ai", "demo", "all")

SCHEMA = """
CREATE TABLE IF NOT EXISTS incidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT NOT NULL UNIQUE,
    job_id TEXT,
    track_id INTEGER,
    event_type TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('critical','warning','info')),
    confidence REAL CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1)),
    zone_id TEXT,
    description TEXT NOT NULL DEFAULT '',
    source TEXT NOT NULL,
    processing_mode TEXT NOT NULL CHECK (processing_mode IN ('ai','demo')),
    video_time_s REAL,
    snapshot TEXT,
    occurred_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    acknowledged_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_incidents_occurred ON incidents (occurred_at);
CREATE INDEX IF NOT EXISTS ix_incidents_mode ON incidents (processing_mode);
"""

CSV_COLUMNS = [
    "id", "occurred_at", "event_type", "severity", "confidence", "zone_id", "description",
    "source", "processing_mode", "origin", "job_id", "track_id", "video_time_s",
    "acknowledged", "acknowledged_at",
]


def default_db_path() -> Path:
    env = os.environ.get("SAFESIGHT_DB")
    return Path(env) if env else Path(__file__).resolve().parents[1] / "data" / "safesight.db"


def to_iso(value: Any = None) -> str:
    """Normalise a datetime / ISO string / None (= now) to UTC 'YYYY-MM-DDTHH:MM:SSZ'."""
    if value is None:
        dt = datetime.now(timezone.utc)
    elif isinstance(value, datetime):
        dt = value
    else:
        s = str(value).strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(s)
        except ValueError:
            raise ValueError(f"invalid timestamp: {value!r}") from None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _day(value: str) -> str:
    try:
        return datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        raise ValueError(f"invalid date (expected YYYY-MM-DD): {value!r}") from None


def make_dedupe_key(mode: str, job_id: Optional[str], event_type: str, track_id: Optional[int],
                    zone_id: Optional[str], video_time_s: Optional[float], occurred_at: str) -> str:
    when = f"{video_time_s:.2f}" if video_time_s is not None else occurred_at
    raw = "|".join(str(x) for x in (mode, job_id or "", event_type, "" if track_id is None else track_id, zone_id or "", when))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _csv_safe(v: Any) -> Any:
    """Neutralise spreadsheet formula injection (source names come from uploaded file names)."""
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def _row(r: sqlite3.Row) -> Dict[str, Any]:
    d = dict(r)
    d["acknowledged"] = bool(d["acknowledged"])
    d["simulated"] = d["processing_mode"] == "demo"
    return d


class IncidentStore:
    def __init__(self, path: Any = None) -> None:
        p = str(path) if path is not None else str(default_db_path())
        if p != ":memory:":
            Path(p).parent.mkdir(parents=True, exist_ok=True)
        self.path = p
        self._lock = threading.RLock()
        self._db = sqlite3.connect(p, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        if p != ":memory:":
            self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(SCHEMA)
        self._db.commit()

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def ping(self) -> bool:
        try:
            with self._lock:
                self._db.execute("SELECT 1").fetchone()
            return True
        except sqlite3.Error:
            return False

    # ---- writes -----------------------------------------------------------------
    def add(self, *, event_type: str, source: str, processing_mode: str = "ai", severity: str = "critical",
            confidence: Optional[float] = None, zone_id: Optional[str] = None, description: str = "",
            job_id: Optional[str] = None, track_id: Optional[int] = None, video_time_s: Optional[float] = None,
            snapshot: Optional[str] = None, occurred_at: Any = None,
            dedupe_key: Optional[str] = None) -> Tuple[Dict[str, Any], bool]:
        """Insert an incident. Returns (record, created); created=False if it already existed."""
        if not str(event_type or "").strip():
            raise ValueError("event_type is required")
        if not str(source or "").strip():
            raise ValueError("source is required")
        if severity not in SEVERITIES:
            raise ValueError(f"severity must be one of {SEVERITIES}")
        if processing_mode not in MODES:
            raise ValueError(f"processing_mode must be one of {MODES}")
        if confidence is not None and not (isinstance(confidence, (int, float)) and 0 <= confidence <= 1):
            raise ValueError("confidence must be between 0 and 1")
        occurred = to_iso(occurred_at)
        key = dedupe_key or make_dedupe_key(processing_mode, job_id, event_type, track_id, zone_id, video_time_s, occurred)
        with self._lock:
            cur = self._db.execute(
                "INSERT OR IGNORE INTO incidents (dedupe_key, job_id, track_id, event_type, severity, confidence, zone_id,"
                " description, source, processing_mode, video_time_s, snapshot, occurred_at, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (key, job_id, track_id, event_type.strip(), severity, confidence, zone_id, description, source.strip(),
                 processing_mode, video_time_s, snapshot, occurred, to_iso()))
            self._db.commit()
            created = cur.rowcount == 1
            row = self._db.execute("SELECT * FROM incidents WHERE dedupe_key=?", (key,)).fetchone()
        return _row(row), created

    def acknowledge(self, incident_id: int, acknowledged: bool = True, now: Any = None) -> Optional[Dict[str, Any]]:
        """Acknowledge (idempotent; keeps the first timestamp) or re-open. None if not found."""
        with self._lock:
            if acknowledged:
                cur = self._db.execute(
                    "UPDATE incidents SET acknowledged=1, acknowledged_at=COALESCE(acknowledged_at, ?) WHERE id=?",
                    (to_iso(now), incident_id))
            else:
                cur = self._db.execute("UPDATE incidents SET acknowledged=0, acknowledged_at=NULL WHERE id=?", (incident_id,))
            self._db.commit()
            if cur.rowcount == 0:
                return None
        return self.get(incident_id)

    def delete_mode(self, mode: str) -> int:
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        with self._lock:
            cur = self._db.execute("DELETE FROM incidents WHERE processing_mode=?", (mode,))
            self._db.commit()
            return cur.rowcount

    # ---- reads ------------------------------------------------------------------
    def get(self, incident_id: int) -> Optional[Dict[str, Any]]:
        with self._lock:
            r = self._db.execute("SELECT * FROM incidents WHERE id=?", (incident_id,)).fetchone()
        return _row(r) if r else None

    def _where(self, severity=None, event_type=None, acknowledged=None, include="all", source=None, q=None,
               date_from=None, date_to=None) -> Tuple[str, List[Any]]:
        c: List[str] = []
        p: List[Any] = []
        if severity is not None:
            if severity not in SEVERITIES:
                raise ValueError(f"severity must be one of {SEVERITIES}")
            c.append("severity=?"); p.append(severity)
        if include not in INCLUDES:
            raise ValueError(f"include must be one of {INCLUDES}")
        if include != "all":
            c.append("processing_mode=?"); p.append(include)
        if event_type:
            c.append("event_type=?"); p.append(event_type)
        if acknowledged is not None:
            c.append("acknowledged=?"); p.append(1 if acknowledged else 0)
        if source:
            c.append("source=?"); p.append(source)
        if q:
            like = "%" + q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
            c.append("(event_type LIKE ? ESCAPE '\\' OR source LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\' OR zone_id LIKE ? ESCAPE '\\')")
            p += [like] * 4
        if date_from:
            c.append("substr(occurred_at,1,10)>=?"); p.append(_day(date_from))
        if date_to:
            c.append("substr(occurred_at,1,10)<=?"); p.append(_day(date_to))
        return (" WHERE " + " AND ".join(c)) if c else "", p

    def list(self, limit: int = 100, offset: int = 0, **filters: Any) -> Tuple[List[Dict[str, Any]], int]:
        if limit < 1 or offset < 0:
            raise ValueError("limit must be >= 1 and offset >= 0")
        where, p = self._where(**filters)
        with self._lock:
            total = self._db.execute("SELECT COUNT(*) FROM incidents" + where, p).fetchone()[0]
            rows = self._db.execute("SELECT * FROM incidents" + where + " ORDER BY occurred_at DESC, id DESC LIMIT ? OFFSET ?",
                                    p + [limit, offset]).fetchall()
        return [_row(r) for r in rows], total

    def summary(self, include: str = "ai", now: Any = None, **filters: Any) -> Dict[str, Any]:
        where, p = self._where(include=include, **filters)
        today = to_iso(now)[:10]
        joiner = " AND " if where else " WHERE "
        with self._lock:
            q = lambda sql, params: self._db.execute(sql, params).fetchall()  # noqa: E731
            total = q("SELECT COUNT(*) FROM incidents" + where, p)[0][0]
            n_today = q("SELECT COUNT(*) FROM incidents" + where + joiner + "substr(occurred_at,1,10)=?", p + [today])[0][0]
            unack = q("SELECT COUNT(*) FROM incidents" + where + joiner + "acknowledged=0", p)[0][0]
            by_sev = {r[0]: r[1] for r in q("SELECT severity, COUNT(*) FROM incidents" + where + " GROUP BY severity", p)}
            by_type = {r[0]: r[1] for r in q("SELECT event_type, COUNT(*) FROM incidents" + where + " GROUP BY event_type ORDER BY 2 DESC, 1", p)}
            by_day = [{"day": r[0], "count": r[1]} for r in q(
                "SELECT substr(occurred_at,1,10) d, COUNT(*) FROM incidents" + where + " GROUP BY d ORDER BY d", p)]
            latest = q("SELECT MAX(occurred_at) FROM incidents" + where, p)[0][0]
            by_origin = {m: 0 for m in MODES}
            by_origin.update({r[0]: r[1] for r in q("SELECT processing_mode, COUNT(*) FROM incidents GROUP BY processing_mode", [])})
        return {
            "include": include, "total": total, "today": n_today, "unacknowledged": unack,
            "by_severity": {s: by_sev.get(s, 0) for s in SEVERITIES}, "by_event_type": by_type,
            "by_day": by_day, "by_origin": by_origin, "latest_at": latest, "today_utc": today,
            "note": "Counts reflect only the origin selected by 'include'; by_origin always shows both.",
        }

    def to_csv(self, **filters: Any) -> str:
        rows, _ = self.list(limit=1_000_000, **filters)
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(CSV_COLUMNS)
        for r in rows:
            r = dict(r, origin="simulated" if r["simulated"] else "detected")
            w.writerow([_csv_safe("" if r.get(c) is None else r[c]) for c in CSV_COLUMNS])
        return buf.getvalue()
