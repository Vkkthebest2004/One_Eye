from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Zone
from app.db.repositories.zone_repo import ZoneRepository
from app.api.schemas import ZoneCreate, ZoneResponse
from app.cv.pipeline import pipeline_manager
from app.cv.zones import ZoneDefinition

router = APIRouter(prefix="/api/zones", tags=["Zones"])


@router.get("", response_model=List[ZoneResponse])
async def list_zones(camera_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    repo = ZoneRepository(db)
    return await repo.get_all(camera_id=camera_id)


@router.post("", response_model=ZoneResponse, status_code=status.HTTP_201_CREATED)
async def create_zone(payload: ZoneCreate, db: AsyncSession = Depends(get_db)):
    repo = ZoneRepository(db)
    existing = await repo.get_by_id(payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="Zone with this ID already exists")

    zone = Zone(
        id=payload.id,
        camera_id=payload.camera_id,
        name=payload.name,
        polygon=payload.polygon,
        severity=payload.severity,
        allowed_classes=payload.allowed_classes,
        active=payload.active
    )
    created = await repo.create(zone)

    # Sync with runtime CV pipeline
    target_cams = [payload.camera_id]
    if payload.camera_id.startswith("CAM_MOB") or payload.camera_id == "CAM_MOBILE":
        target_cams.extend(["CAM_MOBILE", "CAM_MOB_24151JEG"])

    for cid in set(target_cams):
        pipeline = pipeline_manager.get_pipeline(cid)
        if pipeline:
            pipeline.zone_engine.register_zone(ZoneDefinition(
                id=created.id,
                name=created.name,
                camera_id=cid,
                polygon_points=[(p[0], p[1]) for p in created.polygon],
                severity=created.severity,
                allowed_classes=created.allowed_classes,
                active=created.active
            ))

    return created


@router.delete("/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_zone(zone_id: str, db: AsyncSession = Depends(get_db)):
    repo = ZoneRepository(db)
    zone = await repo.get_by_id(zone_id)
    if not zone:
        raise HTTPException(status_code=404, detail="Zone not found")
    await repo.delete(zone_id)

    target_cams = [zone.camera_id]
    if zone.camera_id.startswith("CAM_MOB") or zone.camera_id == "CAM_MOBILE":
        target_cams.extend(["CAM_MOBILE", "CAM_MOB_24151JEG"])

    for cid in set(target_cams):
        pipeline = pipeline_manager.get_pipeline(cid)
        if pipeline:
            pipeline.zone_engine.unregister_zone(zone_id)
    return None
