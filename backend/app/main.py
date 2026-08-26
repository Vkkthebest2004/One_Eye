import os
import logging
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path
from pydantic import BaseModel
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.database import init_db, AsyncSessionLocal
from app.db.repositories.camera_repo import CameraRepository
from app.cv.pipeline import pipeline_manager
from app.websocket.manager import ws_manager

# Routers
from app.api.cameras import router as cameras_router
from app.api.zones import router as zones_router
from app.api.machines import router as machines_router
from app.api.events import router as events_router
from app.api.analytics import router as analytics_router
from app.api.calibration import router as calibration_router
from app.api.health import router as health_router
from app.api.demo import router as demo_router
from app.api.mobile import router as mobile_router

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("oneeye")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing ONE EYE Safety Intelligence Backend...")
    # 1. Initialize Database
    await init_db()

    # 2. Seed initial cameras and danger zones
    from app.db.seed import seed_initial_data
    await seed_initial_data()

    # 3. Ensure directories exist
    settings.get_evidence_dir().mkdir(parents=True, exist_ok=True)
    (settings.base_dir / "videos" / "demo").mkdir(parents=True, exist_ok=True)

    # 4. Bootstrap default camera pipeline
    try:
        async with AsyncSessionLocal() as db:
            repo = CameraRepository(db)
            cams = await repo.get_all()
            for cam in cams:
                if cam.status == "ONLINE":
                    pipe = pipeline_manager.register_camera(cam.id, cam.source)
                    if cam.calibration_matrix:
                        calibration_points = cam.calibration_points or {}
                        pipe.homography.set_matrix(
                            cam.calibration_matrix,
                            calibration_points.get("image"),
                            calibration_points.get("world"),
                        )
                    # Register zones & machines
                    from app.cv.zones import ZoneDefinition
                    from app.cv.proximity import MachineDefinition
                    for z in cam.zones:
                        pipe.zone_engine.register_zone(ZoneDefinition(
                            id=z.id, name=z.name, camera_id=z.camera_id,
                            polygon_points=[(p[0], p[1]) for p in z.polygon],
                            severity=z.severity, active=z.active
                        ))
                    for m in cam.machines:
                        gx, gy, gw, gh = m.geometry
                        pipe.proximity_engine.register_machine(MachineDefinition(
                            id=m.id, name=m.name, camera_id=m.camera_id,
                            bbox=(gx, gy, gx + gw, gy + gh),
                            center=(gx + gw/2.0, gy + gh/2.0),
                            danger_radius_m=m.danger_radius_m, active=m.active
                        ))
                    pipe.start()
    except Exception as e:
        logger.warning(f"Note on camera startup: {e}")

    try:
        from app.cv.usb_mobile import mobile_manager as mm
        mm.scan()
    except Exception as e:
        logger.warning(f"Initial mobile scan: {e}")

    logger.info("ONE EYE Backend is ONLINE and ready.")
    yield
    # Shutdown
    logger.info("Stopping ONE EYE Safety pipelines...")
    await pipeline_manager.stop_all()
    # Disconnect all USB mobile cameras
    from app.cv.usb_mobile import mobile_manager as mm
    mm.disconnect_all()


app = FastAPI(
    title="ONE EYE — Industrial Safety Intelligence Platform API",
    description="Real-time CCTV & Video AI safety monitoring, hazard detection, spatial reasoning, compound risk scoring, and alert dispatch.",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Directories for Evidence Snapshots & Demo Videos
evidence_path = settings.get_evidence_dir()
evidence_path.mkdir(parents=True, exist_ok=True)
app.mount("/evidence", StaticFiles(directory=str(evidence_path)), name="evidence")

videos_path = (settings.base_dir / "videos").resolve()
videos_path.mkdir(parents=True, exist_ok=True)
app.mount("/videos", StaticFiles(directory=str(videos_path)), name="videos")

# Include Routers
app.include_router(health_router)
app.include_router(cameras_router)
app.include_router(zones_router)
app.include_router(machines_router)
app.include_router(events_router)
app.include_router(analytics_router)
app.include_router(calibration_router)
app.include_router(demo_router)
app.include_router(mobile_router)


# ---------------------------------------------------------------------------
# Root Gateway Endpoint
# ---------------------------------------------------------------------------
@app.get("/")
async def root():
    """Root Gateway for ONE EYE Backend API."""
    return {
        "system": "ONE EYE Industrial Safety Intelligence Platform",
        "status": "ONLINE",
        "version": "1.0.0",
        "frontend_url": "http://localhost:3001",
        "api_docs_url": "http://localhost:8001/docs",
        "health_check_url": "http://localhost:8001/api/health",
        "cameras_url": "http://localhost:8001/api/cameras",
        "events_url": "http://localhost:8001/api/events",
        "message": "Backend API is running. Open the Frontend UI at http://localhost:3001 or API Docs at http://localhost:8001/docs"
    }


# ---------------------------------------------------------------------------
# Global System Control: Camera-Only vs Full-AI Mode
# ---------------------------------------------------------------------------
@app.get("/api/system/mode")
async def get_system_mode():
    """Return whether AI safety hazard detection is active or in Camera-Only standby."""
    return {
        "ai_enabled": pipeline_manager.ai_enabled,
        "mode": "FULL_AI" if pipeline_manager.ai_enabled else "CAMERA_ONLY",
        "message": "AI Safety hazard detection is active" if pipeline_manager.ai_enabled else "Camera-Only Mode (Hazard Scanning & Alerts Paused)",
    }


class ToggleAIRequest(BaseModel):
    enabled: Optional[bool] = None


@app.post("/api/system/toggle-ai")
async def toggle_system_ai(payload: ToggleAIRequest = ToggleAIRequest()):
    """Pause or resume all AI hazard detection, PPE checks, and alert dispatching."""
    new_state = pipeline_manager.toggle_ai(payload.enabled)
    # Broadcast system mode change via dispatcher
    await ws_manager.broadcast({
        "type": "SYSTEM_MODE_CHANGED",
        "data": {
            "ai_enabled": new_state,
            "mode": "FULL_AI" if new_state else "CAMERA_ONLY",
        }
    })
    return {
        "ai_enabled": new_state,
        "mode": "FULL_AI" if new_state else "CAMERA_ONLY",
        "message": "AI Safety hazard detection activated" if new_state else "Switched to Camera-Only Mode (Hazard Scanning & Alerts Paused)",
    }


# ---------------------------------------------------------------------------
# Global System Control: Perception Model Engine (YOLO vs Qwen2-VL vs Hybrid)
# ---------------------------------------------------------------------------
class PerceptionModeRequest(BaseModel):
    mode: str = "YOLO"


@app.get("/api/system/perception-mode")
async def get_perception_mode():
    """Return the active perception engine mode (YOLO, QWEN_VL, or HYBRID)."""
    mode = pipeline_manager.perception_mode
    label = (
        "⚡ YOLOv8 (Ultra-Fast)" if mode == "YOLO"
        else ("🧠 Qwen2-VL (Cognitive)" if mode == "QWEN_VL"
        else "🔄 Hybrid Dual-AI")
    )
    return {
        "perception_mode": mode,
        "mode_label": label,
        "available_modes": ["YOLO", "QWEN_VL", "HYBRID"],
    }


@app.post("/api/system/perception-mode")
async def set_perception_mode(payload: PerceptionModeRequest):
    """Switch active perception engine between YOLO, Qwen2-VL, and Hybrid."""
    new_mode = pipeline_manager.set_perception_mode(payload.mode)
    await ws_manager.broadcast({
        "type": "PERCEPTION_MODE_CHANGED",
        "data": {
            "perception_mode": new_mode,
        }
    })
    return {
        "success": True,
        "perception_mode": new_mode,
        "message": f"Active AI perception engine switched to: {new_mode}",
    }


# ---------------------------------------------------------------------------
# Global System Control: Live Production Mode vs Demo Simulation Mode
# ---------------------------------------------------------------------------
@app.get("/api/system/demo-mode")
async def get_demo_mode():
    """Return whether the system is in Live Production Mode or Demo Simulation Mode."""
    return {
        "demo_mode": settings.DEMO_MODE,
        "mode_label": "DEMO SIMULATION" if settings.DEMO_MODE else "LIVE PRODUCTION",
    }


class ToggleDemoModeRequest(BaseModel):
    enabled: Optional[bool] = None


@app.post("/api/system/toggle-demo-mode")
async def toggle_demo_mode(payload: ToggleDemoModeRequest = ToggleDemoModeRequest()):
    """Toggle between Live Production Mode (100% physical camera feeds) and Demo Simulation Mode."""
    if payload.enabled is not None:
        settings.DEMO_MODE = payload.enabled
    else:
        settings.DEMO_MODE = not settings.DEMO_MODE

    await ws_manager.broadcast({
        "type": "DEMO_MODE_CHANGED",
        "data": {
            "demo_mode": settings.DEMO_MODE,
            "mode_label": "DEMO SIMULATION" if settings.DEMO_MODE else "LIVE PRODUCTION",
        }
    })
    return {
        "demo_mode": settings.DEMO_MODE,
        "mode_label": "DEMO SIMULATION" if settings.DEMO_MODE else "LIVE PRODUCTION",
        "message": f"Switched to {'Demo Simulation Mode' if settings.DEMO_MODE else 'Live Production Mode'}",
    }


# WebSocket Endpoints
@app.websocket("/ws")
@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Echo or process client pings
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket error: {e}")
        ws_manager.disconnect(websocket)
