from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.db.models import Zone


class ZoneRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, camera_id: Optional[str] = None) -> List[Zone]:
        stmt = select(Zone)
        if camera_id:
            stmt = stmt.where(Zone.camera_id == camera_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, zone_id: str) -> Optional[Zone]:
        stmt = select(Zone).where(Zone.id == zone_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, zone: Zone) -> Zone:
        self.db.add(zone)
        await self.db.commit()
        await self.db.refresh(zone)
        return zone

    async def update(self, zone_id: str, **kwargs) -> Optional[Zone]:
        zone = await self.get_by_id(zone_id)
        if not zone:
            return None
        for key, value in kwargs.items():
            if hasattr(zone, key) and value is not None:
                setattr(zone, key, value)
        await self.db.commit()
        await self.db.refresh(zone)
        return zone

    async def delete(self, zone_id: str) -> bool:
        zone = await self.get_by_id(zone_id)
        if not zone:
            return False
        await self.db.delete(zone)
        await self.db.commit()
        return True
