import os
import time
from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.database import get_db
from app.cv.pipeline import pipeline_manager
from app.websocket.manager import ws_manager
from app.config import settings

router = APIRouter(prefix="/api/health", tags=["Health & Observability"])


@router.get("")
async def get_system_health(db: AsyncSession = Depends(get_db)) -> Dict[str, Any]:
    # Check DB
    db_status = "ONLINE"
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        db_status = "OFFLINE"

    # Inspect pipelines
    camera_metrics = {}
    total_active_tracks = 0
    for cam_id, pipe in pipeline_manager.pipelines.items():
        camera_metrics[cam_id] = {
            "status": "ONLINE" if pipe.is_running else "OFFLINE",
            "fps": round(pipe.measured_fps, 1),
            "inference_ms": pipe.avg_inference_ms,
            "active_tracks": pipe.active_tracks_count
        }
        total_active_tracks += pipe.active_tracks_count

    return {
        "status": "HEALTHY",
        "system": "ONE EYE Industrial Safety Intelligence",
        "version": "1.0.0-mvp",
        "database": db_status,
        "cv_engine": "ONLINE" if pipeline_manager.pipelines else "READY",
        "model_device": settings.MODEL_DEVICE,
        "active_ws_clients": len(ws_manager.active_connections),
        "demo_mode": settings.DEMO_MODE,
        "cameras": camera_metrics,
        "total_active_tracks": total_active_tracks,
        "timestamp": time.time()
    }
