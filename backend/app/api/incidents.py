"""Incident, analytics, monitoring and demo endpoints. Thin layer over db.py (validation only)."""
from typing import Any, Dict, Optional
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from pydantic import BaseModel

from ..db import IncidentStore
from ..demo import DEMO_WARNING, load_demo
from ..monitoring import monitoring_status

router = APIRouter(prefix="/api", tags=["incidents"])
_store: Optional[IncidentStore] = None


def get_store() -> IncidentStore:
    global _store
    if _store is None:
        _store = IncidentStore()
    return _store


Severity = Literal["critical", "warning", "info"]
Include = Literal["ai", "demo", "all"]


def filters(severity: Optional[Severity] = None, event_type: Optional[str] = Query(None, max_length=100),
            acknowledged: Optional[bool] = None, source: Optional[str] = Query(None, max_length=300),
            q: Optional[str] = Query(None, max_length=200), date_from: Optional[str] = None,
            date_to: Optional[str] = None) -> Dict[str, Any]:
    return dict(severity=severity, event_type=event_type, acknowledged=acknowledged, source=source, q=q,
                date_from=date_from, date_to=date_to)


def _bad(e: ValueError) -> HTTPException:
    return HTTPException(status_code=422, detail=str(e))


@router.get("/incidents")
def list_incidents(f: Dict[str, Any] = Depends(filters), include: Include = "all",
                   limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0),
                   store: IncidentStore = Depends(get_store)):
    try:
        items, total = store.list(limit=limit, offset=offset, include=include, **f)
    except ValueError as e:
        raise _bad(e)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


# NOTE: declared before "/incidents/{incident_id}" so "export" is not parsed as an id.
@router.get("/incidents/export")
def export_incidents(f: Dict[str, Any] = Depends(filters), include: Include = "all",
                     format: Literal["csv", "json"] = "csv", store: IncidentStore = Depends(get_store)):
    try:
        if format == "json":
            items, _ = store.list(limit=1_000_000, include=include, **f)
            import json
            body, mime = json.dumps(items, indent=2), "application/json"
        else:
            body, mime = store.to_csv(include=include, **f), "text/csv"
    except ValueError as e:
        raise _bad(e)
    return Response(content=body, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="safesight-incidents.{format}"'})


@router.get("/incidents/{incident_id}")
def get_incident(incident_id: int = Path(..., ge=1), store: IncidentStore = Depends(get_store)):
    row = store.get(incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return row


class AckBody(BaseModel):
    acknowledged: bool = True


@router.patch("/incidents/{incident_id}/acknowledge")
def acknowledge(incident_id: int = Path(..., ge=1), body: Optional[AckBody] = None,
                store: IncidentStore = Depends(get_store)):
    row = store.acknowledge(incident_id, True if body is None else body.acknowledged)
    if row is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return row


@router.get("/analytics/summary")
def analytics_summary(f: Dict[str, Any] = Depends(filters), include: Include = "ai",
                      store: IncidentStore = Depends(get_store)):
    try:
        return store.summary(include=include, **f)
    except ValueError as e:
        raise _bad(e)


@router.get("/monitoring/status")
def monitoring(store: IncidentStore = Depends(get_store)):
    return monitoring_status(store)


@router.post("/demo/events")
def demo_load(store: IncidentStore = Depends(get_store)):
    """Load the fixed demo events (stored as processing_mode='demo'). Idempotent."""
    return {"warning": DEMO_WARNING, **load_demo(store)}


@router.delete("/demo/events")
def demo_clear(store: IncidentStore = Depends(get_store)):
    return {"deleted": store.delete_mode("demo")}
