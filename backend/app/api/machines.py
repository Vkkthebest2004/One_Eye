from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Machine
from app.db.repositories.machine_repo import MachineRepository
from app.api.schemas import MachineCreate, MachineResponse
from app.cv.pipeline import pipeline_manager
from app.cv.proximity import MachineDefinition

router = APIRouter(prefix="/api/machines", tags=["Machines"])


@router.get("", response_model=List[MachineResponse])
async def list_machines(camera_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    repo = MachineRepository(db)
    return await repo.get_all(camera_id=camera_id)


@router.post("", response_model=MachineResponse, status_code=status.HTTP_201_CREATED)
async def create_machine(payload: MachineCreate, db: AsyncSession = Depends(get_db)):
    repo = MachineRepository(db)
    existing = await repo.get_by_id(payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="Machine with this ID already exists")

    machine = Machine(
        id=payload.id,
        camera_id=payload.camera_id,
        name=payload.name,
        geometry=payload.geometry,
        danger_radius_m=payload.danger_radius_m,
        active=payload.active
    )
    created = await repo.create(machine)

    # Sync with runtime CV pipeline
    pipeline = pipeline_manager.get_pipeline(payload.camera_id)
    if pipeline:
        # geometry is [x, y, w, h]
        gx, gy, gw, gh = payload.geometry
        pipeline.proximity_engine.register_machine(MachineDefinition(
            id=created.id,
            name=created.name,
            camera_id=created.camera_id,
            bbox=(gx, gy, gx + gw, gy + gh),
            center=(gx + gw / 2.0, gy + gh / 2.0),
            danger_radius_m=created.danger_radius_m,
            active=created.active
        ))

    return created


@router.delete("/{machine_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_machine(machine_id: str, db: AsyncSession = Depends(get_db)):
    repo = MachineRepository(db)
    machine = await repo.get_by_id(machine_id)
    if not machine:
        raise HTTPException(status_code=404, detail="Machine not found")
    deleted = await repo.delete(machine_id)
    pipeline = pipeline_manager.get_pipeline(machine.camera_id)
    if pipeline:
        pipeline.proximity_engine.unregister_machine(machine_id)
    return None
