import datetime
from typing import Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc, case
from app.db.models import SafetyEvent, Camera
from app.config import settings
from app.cv.pipeline import pipeline_manager


class AnalyticsRepository:
    """
    Real-time Industrial Safety Analytics & KPI Repository.
    Computes precise live operational telemetry and historical event audit metrics.
    """
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_summary(self) -> Dict[str, Any]:
        now = datetime.datetime.utcnow()
        day_ago = now - datetime.timedelta(days=1)
        is_demo_filter = SafetyEvent.is_demo == settings.DEMO_MODE

        # 1. Event Counts from Database (filtered strictly by current operational mode)
        total_stmt = select(func.count(SafetyEvent.id)).where(is_demo_filter)
        active_stmt = select(func.count(SafetyEvent.id)).where(
            is_demo_filter,
            SafetyEvent.status.in_(["ALERTING", "ACKNOWLEDGED"])
        )
        critical_stmt = select(func.count(SafetyEvent.id)).where(
            is_demo_filter,
            SafetyEvent.severity == "CRITICAL",
            SafetyEvent.status.in_(["ALERTING", "ACKNOWLEDGED"])
        )
        high_stmt = select(func.count(SafetyEvent.id)).where(
            is_demo_filter,
            SafetyEvent.severity == "HIGH",
            SafetyEvent.status.in_(["ALERTING", "ACKNOWLEDGED"])
        )
        resolved_stmt = select(func.count(SafetyEvent.id)).where(
            is_demo_filter,
            SafetyEvent.status == "RESOLVED"
        )
        recent_24h_stmt = select(func.count(SafetyEvent.id)).where(
            is_demo_filter,
            SafetyEvent.started_at >= day_ago
        )

        total = (await self.db.execute(total_stmt)).scalar_one() or 0
        active = (await self.db.execute(active_stmt)).scalar_one() or 0
        critical = (await self.db.execute(critical_stmt)).scalar_one() or 0
        high = (await self.db.execute(high_stmt)).scalar_one() or 0
        resolved = (await self.db.execute(resolved_stmt)).scalar_one() or 0
        recent_24h = (await self.db.execute(recent_24h_stmt)).scalar_one() or 0

        # 2. Real-Time In-Memory Telemetry from Live Pipelines
        active_pipelines = list(pipeline_manager.pipelines.values())
        cameras_total = len(active_pipelines) if active_pipelines else 1
        cameras_online = sum(1 for p in active_pipelines if p.measured_fps > 0 or p.latest_frame is not None)
        total_live_workers = sum(p.active_tracks_count for p in active_pipelines)

        # 3. Real-Time Average Risk Score
        # Calculate from live tracks if workers are present, otherwise average of active events
        live_risk_scores = []
        for p in active_pipelines:
            for t in p.latest_tracks:
                if t.get("category") == "PERSON" or "Worker" in t.get("label", ""):
                    live_risk_scores.append(t.get("current_risk_score", 0))

        if live_risk_scores:
            avg_risk = sum(live_risk_scores) / len(live_risk_scores)
        elif active > 0:
            avg_risk_stmt = select(func.avg(SafetyEvent.risk_score)).where(
                is_demo_filter,
                SafetyEvent.status.in_(["ALERTING", "ACKNOWLEDGED"])
            )
            avg_risk = (await self.db.execute(avg_risk_stmt)).scalar_one() or 0.0
        else:
            avg_risk = 0.0

        return {
            "total_events": total,
            "active_alerts": active,
            "critical_events": critical,
            "high_risk_events": high,
            "resolved_events": resolved,
            "avg_risk_score": round(float(avg_risk), 1),
            "events_24h": recent_24h,
            "cameras_total": cameras_total,
            "cameras_online": cameras_online,
            "workers_tracked": total_live_workers
        }

    async def get_trends(self, days: int = 7) -> List[Dict[str, Any]]:
        now = datetime.datetime.utcnow()
        start_date = now - datetime.timedelta(days=days)
        is_demo_filter = SafetyEvent.is_demo == settings.DEMO_MODE

        stmt = select(SafetyEvent).where(
            is_demo_filter,
            SafetyEvent.started_at >= start_date
        ).order_by(SafetyEvent.started_at)
        result = await self.db.execute(stmt)
        events = result.scalars().all()

        daily_data: Dict[str, Dict[str, int]] = {}
        for d in range(days):
            date_key = (start_date + datetime.timedelta(days=d)).strftime("%b %d")
            daily_data[date_key] = {"total": 0, "critical": 0, "high": 0, "medium": 0, "advisory": 0}

        for ev in events:
            date_key = ev.started_at.strftime("%b %d")
            if date_key in daily_data:
                daily_data[date_key]["total"] += 1
                sev = (ev.severity or "advisory").lower()
                if sev in daily_data[date_key]:
                    daily_data[date_key][sev] += 1

        return [{"date": k, **v} for k, v in daily_data.items()]

    async def get_hazard_distribution(self) -> List[Dict[str, Any]]:
        is_demo_filter = SafetyEvent.is_demo == settings.DEMO_MODE
        stmt = select(
            SafetyEvent.primary_hazard,
            func.count(SafetyEvent.id)
        ).where(is_demo_filter).group_by(SafetyEvent.primary_hazard)
        
        result = await self.db.execute(stmt)
        rows = result.all()
        return [{"hazard": r[0] or "UNKNOWN", "count": r[1]} for r in rows]

    async def get_camera_risk_ranking(self) -> List[Dict[str, Any]]:
        is_demo_filter = SafetyEvent.is_demo == settings.DEMO_MODE
        stmt = select(
            SafetyEvent.camera_id,
            func.count(SafetyEvent.id).label("total_events"),
            func.avg(SafetyEvent.risk_score).label("avg_risk"),
            func.sum(case((SafetyEvent.severity == "CRITICAL", 1), else_=0)).label("critical_events")
        ).where(is_demo_filter).group_by(SafetyEvent.camera_id).order_by(desc("total_events"))
        
        result = await self.db.execute(stmt)
        rows = result.all()
        return [
            {
                "camera_id": r[0],
                "total_events": r[1],
                "avg_risk": round(float(r[2] or 0), 1),
                "critical_events": int(r[3] or 0)
            }
            for r in rows
        ]
