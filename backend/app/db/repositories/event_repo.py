import datetime
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from app.db.models import SafetyEvent, AuditLog, AlertRecord


class EventRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(
        self,
        camera_id: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        hazard_type: Optional[str] = None,
        worker_id: Optional[int] = None,
        limit: int = 50,
        offset: int = 0
    ) -> Tuple[List[SafetyEvent], int]:
        stmt = select(SafetyEvent).options(
            selectinload(SafetyEvent.audit_logs),
            selectinload(SafetyEvent.alerts),
            selectinload(SafetyEvent.camera)
        )
        count_stmt = select(func.count(SafetyEvent.id))

        if camera_id:
            stmt = stmt.where(SafetyEvent.camera_id == camera_id)
            count_stmt = count_stmt.where(SafetyEvent.camera_id == camera_id)
        if severity:
            stmt = stmt.where(SafetyEvent.severity == severity.upper())
            count_stmt = count_stmt.where(SafetyEvent.severity == severity.upper())
        if status:
            stmt = stmt.where(SafetyEvent.status == status.upper())
            count_stmt = count_stmt.where(SafetyEvent.status == status.upper())
        if hazard_type:
            stmt = stmt.where(SafetyEvent.primary_hazard == hazard_type)
            count_stmt = count_stmt.where(SafetyEvent.primary_hazard == hazard_type)
        if worker_id:
            stmt = stmt.where(SafetyEvent.worker_id == worker_id)
            count_stmt = count_stmt.where(SafetyEvent.worker_id == worker_id)

        stmt = stmt.order_by(desc(SafetyEvent.started_at)).limit(limit).offset(offset)

        events_result = await self.db.execute(stmt)
        count_result = await self.db.execute(count_stmt)

        return list(events_result.scalars().all()), count_result.scalar_one()

    async def get_by_id(self, event_id: str) -> Optional[SafetyEvent]:
        stmt = select(SafetyEvent).where(SafetyEvent.id == event_id).options(
            selectinload(SafetyEvent.audit_logs),
            selectinload(SafetyEvent.alerts),
            selectinload(SafetyEvent.camera)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_active_event_for_worker(self, camera_id: str, worker_id: int) -> Optional[SafetyEvent]:
        stmt = select(SafetyEvent).where(
            SafetyEvent.camera_id == camera_id,
            SafetyEvent.worker_id == worker_id,
            SafetyEvent.status.in_(["ALERTING", "ACKNOWLEDGED"])
        ).order_by(desc(SafetyEvent.started_at)).limit(1)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, event: SafetyEvent, actor: str = "SYSTEM") -> SafetyEvent:
        self.db.add(event)
        
        # Add initial audit log
        audit = AuditLog(
            event_id=event.id,
            action="DETECTED",
            actor=actor,
            timestamp=datetime.datetime.utcnow(),
            metadata_json={
                "risk_score": event.risk_score,
                "severity": event.severity,
                "primary_hazard": event.primary_hazard,
                "hazards": event.hazard_types
            }
        )
        self.db.add(audit)
        
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def update_event(self, event: SafetyEvent) -> SafetyEvent:
        event.updated_at = datetime.datetime.utcnow()
        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def acknowledge(self, event_id: str, actor: str = "OPERATOR") -> Optional[SafetyEvent]:
        event = await self.get_by_id(event_id)
        if not event:
            return None
        
        event.status = "ACKNOWLEDGED"
        event.acknowledged_at = datetime.datetime.utcnow()
        event.updated_at = datetime.datetime.utcnow()

        audit = AuditLog(
            event_id=event.id,
            action="ACKNOWLEDGED",
            actor=actor,
            timestamp=datetime.datetime.utcnow(),
            metadata_json={"previous_status": "ALERTING"}
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def resolve(self, event_id: str, actor: str = "OPERATOR") -> Optional[SafetyEvent]:
        event = await self.get_by_id(event_id)
        if not event:
            return None
        
        event.status = "RESOLVED"
        event.resolved_at = datetime.datetime.utcnow()
        event.updated_at = datetime.datetime.utcnow()

        audit = AuditLog(
            event_id=event.id,
            action="RESOLVED",
            actor=actor,
            timestamp=datetime.datetime.utcnow(),
            metadata_json={"resolved_by": actor}
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(event)
        return event

    async def mark_false_positive(self, event_id: str, actor: str = "OPERATOR", notes: str = "") -> Optional[SafetyEvent]:
        event = await self.get_by_id(event_id)
        if not event:
            return None
        
        event.status = "FALSE_POSITIVE"
        event.resolved_at = datetime.datetime.utcnow()
        event.updated_at = datetime.datetime.utcnow()

        audit = AuditLog(
            event_id=event.id,
            action="FALSE_POSITIVE",
            actor=actor,
            timestamp=datetime.datetime.utcnow(),
            metadata_json={"notes": notes}
        )
        self.db.add(audit)

        await self.db.commit()
        await self.db.refresh(event)
        return event
