import datetime
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from app.db.models import RetrospectiveReport


class RetrospectiveRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, report_data: dict) -> RetrospectiveReport:
        report = RetrospectiveReport(**report_data)
        self.db.add(report)
        await self.db.commit()
        await self.db.refresh(report)
        return report

    async def get_by_id(self, report_id: str) -> Optional[RetrospectiveReport]:
        stmt = select(RetrospectiveReport).where(RetrospectiveReport.id == report_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(
        self,
        camera_id: Optional[str] = None,
        domain: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[RetrospectiveReport], int]:
        stmt = select(RetrospectiveReport)
        count_stmt = select(func.count(RetrospectiveReport.id))

        if camera_id:
            stmt = stmt.where(RetrospectiveReport.camera_id == camera_id)
            count_stmt = count_stmt.where(RetrospectiveReport.camera_id == camera_id)
        if domain:
            stmt = stmt.where(RetrospectiveReport.domain == domain.upper())
            count_stmt = count_stmt.where(RetrospectiveReport.domain == domain.upper())
        if severity:
            stmt = stmt.where(RetrospectiveReport.severity == severity.upper())
            count_stmt = count_stmt.where(RetrospectiveReport.severity == severity.upper())

        stmt = stmt.order_by(desc(RetrospectiveReport.created_at)).limit(limit).offset(offset)

        reports_res = await self.db.execute(stmt)
        count_res = await self.db.execute(count_stmt)

        return list(reports_res.scalars().all()), count_res.scalar_one()

    async def delete(self, report_id: str) -> bool:
        report = await self.get_by_id(report_id)
        if not report:
            return False
        await self.db.delete(report)
        await self.db.commit()
        return True
