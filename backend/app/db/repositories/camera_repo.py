from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from app.db.models import Camera


class CameraRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self) -> List[Camera]:
        stmt = select(Camera).options(selectinload(Camera.zones), selectinload(Camera.machines))
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, camera_id: str) -> Optional[Camera]:
        stmt = select(Camera).where(Camera.id == camera_id).options(
            selectinload(Camera.zones), selectinload(Camera.machines)
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, camera: Camera) -> Camera:
        self.db.add(camera)
        await self.db.commit()
        await self.db.refresh(camera)
        return camera

    async def update(self, camera_id: str, **kwargs) -> Optional[Camera]:
        camera = await self.get_by_id(camera_id)
        if not camera:
            return None
        for key, value in kwargs.items():
            if hasattr(camera, key) and value is not None:
                setattr(camera, key, value)
        await self.db.commit()
        await self.db.refresh(camera)
        return camera

    async def delete(self, camera_id: str) -> bool:
        camera = await self.get_by_id(camera_id)
        if not camera:
            return False
        await self.db.delete(camera)
        await self.db.commit()
        return True
