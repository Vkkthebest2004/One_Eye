from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Zone
from app.db.repositories.zone_repo import ZoneRepository
from app.api.schemas import ZoneCreate, ZoneResponse
from app.cv.pipeline import pipeline_manager
from app.cv.zones import ZoneDefinition
from app.cv.visual_memory import visual_memory_engine

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

    policy = {
        "zone_type": payload.zone_type,
        "warning_delay_seconds": payload.warning_delay_seconds,
        "critical_delay_seconds": payload.critical_delay_seconds,
        "voice_alert_enabled": payload.voice_alert_enabled,
        "siren_enabled": payload.siren_enabled,
        "supervisor_alert_enabled": payload.supervisor_alert_enabled,
    }
    zone = Zone(
        id=payload.id,
        camera_id=payload.camera_id,
        name=payload.name,
        polygon=payload.polygon,
        severity=payload.severity,
        allowed_classes=payload.allowed_classes,
        policy=policy,
        active=payload.active
    )
    created = await repo.create(zone)

    # Register into Visual Memory Engine
    frame = None
    if payload.keyframe_b64:
        try:
            import base64
            import numpy as np
            import cv2
            b64_str = payload.keyframe_b64
            if "," in b64_str:
                b64_str = b64_str.split(",", 1)[1]
            img_bytes = base64.b64decode(b64_str)
            frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)
        except Exception as e:
            logger.warning(f"Could not decode keyframe_b64: {e}")

    if frame is None:
        pipe = pipeline_manager.get_pipeline(payload.camera_id)
        frame = pipe.latest_frame if pipe else None
        if frame is None and (payload.camera_id.startswith("CAM_MOB") or payload.camera_id == "CAM_MOBILE"):
            from app.cv.usb_mobile import mobile_manager
            web_res = mobile_manager.get_web_frame("CAM_MOBILE") or mobile_manager.get_web_frame("CAM_MOB_24151JEG")
            if web_res:
                frame = web_res[0]

    if frame is not None:
        visual_memory_engine.register_anchor(
            zone_id=created.id,
            camera_id=payload.camera_id,
            name=created.name,
            keyframe_bgr=frame,
            polygon_points_norm=created.polygon,
            severity=created.severity,
        )

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
    visual_memory_engine.unregister_anchor(zone_id)

    for pipeline in pipeline_manager.pipelines.values():
        pipeline.zone_engine.unregister_zone(zone_id)

    return None


from pydantic import BaseModel

class ZoneConfigImportRequest(BaseModel):
    camera_id: str = "CAM_01"
    name: Optional[str] = None
    config_json: Optional[dict] = None
    config_path: Optional[str] = None
    severity: int = 90


@router.post("/import-config", status_code=status.HTTP_201_CREATED)
async def import_zone_config(payload: ZoneConfigImportRequest, db: AsyncSession = Depends(get_db)):
    """
    Import a restricted zone directly from a zone_selector.py JSON configuration.
    Supports either passing config_json payload or a filepath to zone_config.json.
    """
    import json
    from pathlib import Path
    cfg = payload.config_json

    if not cfg:
        target_path = Path(payload.config_path) if payload.config_path else Path("ZoneDetection/zone_config.json")
        if not target_path.exists() and Path("backend/ZoneDetection/zone_config.json").exists():
            target_path = Path("backend/ZoneDetection/zone_config.json")
        if not target_path.exists():
            raise HTTPException(status_code=400, detail=f"Zone config file not found at {target_path}")
        try:
            with open(target_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Invalid JSON file: {err}")

    raw_poly = cfg.get("polygon")
    if not raw_poly or len(raw_poly) < 3:
        raise HTTPException(status_code=400, detail="Zone config must contain at least 3 polygon points")

    image_size = cfg.get("image_size", [1280, 720])
    fw, fh = float(image_size[0]), float(image_size[1])

    # Normalize polygon to 0.0-1.0
    norm_poly = []
    for pt in raw_poly:
        px, py = float(pt[0]), float(pt[1])
        if fw > 0 and fh > 0 and (px > 1.0 or py > 1.0):
            norm_poly.append([round(min(1.0, max(0.0, px / fw)), 4), round(min(1.0, max(0.0, py / fh)), 4)])
        else:
            norm_poly.append([round(min(1.0, max(0.0, px)), 4), round(min(1.0, max(0.0, py)), 4)])

    import time
    zid = f"ZONE_{payload.camera_id}_{int(time.time())}"
    zname = payload.name or f"Restricted: {Path(cfg.get('image', 'Custom Area')).stem}"

    # Persist in Database
    repo = ZoneRepository(db)
    zone_db = Zone(
        id=zid,
        camera_id=payload.camera_id,
        name=zname,
        polygon=norm_poly,
        severity=payload.severity,
        allowed_classes=[],
        policy={"zone_type": "NO_ENTRY", "warning_delay_seconds": 0.0, "critical_delay_seconds": 3.0},
        active=True
    )
    created = await repo.create(zone_db)

    # Register into running CV pipeline
    target_cams = [payload.camera_id]
    if payload.camera_id.startswith("CAM_MOB") or payload.camera_id == "CAM_MOBILE":
        target_cams.extend(["CAM_MOBILE", "CAM_MOB_24151JEG"])

    for cid in set(target_cams):
        pipe = pipeline_manager.get_pipeline(cid)
        if pipe:
            pipe.zone_engine.register_zone(ZoneDefinition(
                id=created.id,
                name=created.name,
                camera_id=cid,
                polygon_points=[(p[0], p[1]) for p in created.polygon],
                severity=created.severity,
                active=created.active
            ))

    return {
        "success": True,
        "message": f"Successfully imported restricted zone '{created.name}'",
        "zone": {
            "id": created.id,
            "name": created.name,
            "camera_id": created.camera_id,
            "polygon": created.polygon,
            "severity": created.severity
        }
    }
