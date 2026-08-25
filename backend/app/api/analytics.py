from typing import Dict, Any, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.analytics_repo import AnalyticsRepository

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])


@router.get("/summary")
async def get_summary(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    repo = AnalyticsRepository(db)
    return await repo.get_summary()


@router.get("/trends")
async def get_trends(days: int = Query(7, ge=1, le=90), db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    repo = AnalyticsRepository(db)
    return await repo.get_trends(days=days)


@router.get("/hazards")
async def get_hazards(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    repo = AnalyticsRepository(db)
    return await repo.get_hazard_distribution()


@router.get("/camera-risk")
async def get_camera_risk(db: AsyncSession = Depends(get_db)) -> List[Dict[str, Any]]:
    repo = AnalyticsRepository(db)
    return await repo.get_camera_risk_ranking()
