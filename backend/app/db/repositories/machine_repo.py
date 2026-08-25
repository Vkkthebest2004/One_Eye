from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.db.models import Machine


class MachineRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all(self, camera_id: Optional[str] = None) -> List[Machine]:
        stmt = select(Machine)
        if camera_id:
            stmt = stmt.where(Machine.camera_id == camera_id)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, machine_id: str) -> Optional[Machine]:
        stmt = select(Machine).where(Machine.id == machine_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, machine: Machine) -> Machine:
        self.db.add(machine)
        await self.db.commit()
        await self.db.refresh(machine)
        return machine

    async def update(self, machine_id: str, **kwargs) -> Optional[Machine]:
        machine = await self.get_by_id(machine_id)
        if not machine:
            return None
        for key, value in kwargs.items():
            if hasattr(machine, key) and value is not None:
                setattr(machine, key, value)
        await self.db.commit()
        await self.db.refresh(machine)
        return machine

    async def delete(self, machine_id: str) -> bool:
        machine = await self.get_by_id(machine_id)
        if not machine:
            return False
        await self.db.delete(machine)
        await self.db.commit()
        return True
