from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.event_repo import EventRepository
from app.api.schemas import (
    SafetyEventResponse,
    EventAcknowledgeRequest,
    EventResolveRequest,
    EventFalsePositiveRequest
)
from app.alerts.dispatcher import dispatcher

router = APIRouter(prefix="/api/events", tags=["Events"])


@router.get("", response_model=dict)
async def list_events(
    camera_id: Optional[str] = None,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    hazard_type: Optional[str] = None,
    worker_id: Optional[int] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    repo = EventRepository(db)
    events, total = await repo.get_all(
        camera_id=camera_id,
        severity=severity,
        status=status,
        hazard_type=hazard_type,
        worker_id=worker_id,
        limit=limit,
        offset=offset
    )
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "events": [SafetyEventResponse.model_validate(e) for e in events]
    }


@router.get("/{event_id}", response_model=SafetyEventResponse)
async def get_event(event_id: str, db: AsyncSession = Depends(get_db)):
    repo = EventRepository(db)
    event = await repo.get_by_id(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return SafetyEventResponse.model_validate(event)


@router.post("/{event_id}/acknowledge", response_model=SafetyEventResponse)
async def acknowledge_event(
    event_id: str,
    payload: EventAcknowledgeRequest,
    db: AsyncSession = Depends(get_db)
):
    repo = EventRepository(db)
    updated = await repo.acknowledge(event_id, actor=payload.actor)
    if not updated:
        raise HTTPException(status_code=404, detail="Event not found")

    await dispatcher.broadcast_event_update(
        event_id=event_id,
        status="ACKNOWLEDGED",
        actor=payload.actor
    )
    return SafetyEventResponse.model_validate(updated)


@router.post("/{event_id}/resolve", response_model=SafetyEventResponse)
async def resolve_event(
    event_id: str,
    payload: EventResolveRequest,
    db: AsyncSession = Depends(get_db)
):
    repo = EventRepository(db)
    updated = await repo.resolve(event_id, actor=payload.actor)
    if not updated:
        raise HTTPException(status_code=404, detail="Event not found")

    await dispatcher.broadcast_event_update(
        event_id=event_id,
        status="RESOLVED",
        actor=payload.actor
    )
    return SafetyEventResponse.model_validate(updated)


@router.post("/{event_id}/false-positive", response_model=SafetyEventResponse)
async def false_positive_event(
    event_id: str,
    payload: EventFalsePositiveRequest,
    db: AsyncSession = Depends(get_db)
):
    repo = EventRepository(db)
    updated = await repo.mark_false_positive(event_id, actor=payload.actor, notes=payload.notes)
    if not updated:
        raise HTTPException(status_code=404, detail="Event not found")

    await dispatcher.broadcast_event_update(
        event_id=event_id,
        status="FALSE_POSITIVE",
        actor=payload.actor
    )
    return SafetyEventResponse.model_validate(updated)
