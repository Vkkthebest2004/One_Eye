"""
ONE EYE — REST API for USB Mobile Phone Camera Management

Endpoints:
  GET    /api/mobile/status           — Overall mobile subsystem status
  POST   /api/mobile/scan             — Trigger a device scan
  GET    /api/mobile/devices          — List all discovered devices
  POST   /api/mobile/connect          — Connect a device
  POST   /api/mobile/disconnect       — Disconnect a device
  GET    /api/mobile/stream/{serial}  — MJPEG frame stream for preview
"""

import asyncio
import logging
import os
import platform
import shutil
import time
from typing import Optional

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Camera
from app.db.repositories.camera_repo import CameraRepository
from app.cv.pipeline import pipeline_manager
from app.cv.usb_mobile import (
    ConnectionMode,
    MobileConnectionManager,
    mobile_manager,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mobile", tags=["Mobile USB"])


# ---------------------------------------------------------------------------
# Request / Response Schemas
# ---------------------------------------------------------------------------

class RTSPConnectRequest(BaseModel):
    url: str = Field(..., description="RTSP or HTTP IP Camera URL (e.g. rtsp://192.168.1.105:8554/live or http://192.168.1.105:8080/video)")
    camera_id: str = Field(default="CAM_MOB_24151JEG")
    name: str = Field(default="Mobile RTSP Camera (Pixel 6a)")


class ConnectRequest(BaseModel):
    serial: str = Field(..., json_schema_extra={"example": "RFXXXXXXXXXXXXXX"})
    mode: str = Field(
        default="auto",
        json_schema_extra={
            "example": "auto",
            "description": "Connection mode: auto | uvc_webcam | adb_scrcpy | adb_ipwebcam",
        },
    )
    camera_id: Optional[str] = Field(
        default=None,
        json_schema_extra={
            "example": "MOB_01",
            "description": "Optional ONE EYE camera ID to register under.",
        },
    )


class DisconnectRequest(BaseModel):
    serial: str = Field(..., json_schema_extra={"example": "RFXXXXXXXXXXXXXX"})


class MobileStatusResponse(BaseModel):
    adb_available: bool
    scrcpy_available: bool
    platform: str
    device_count: int
    connected_count: int


class DeviceResponse(BaseModel):
    serial: str
    model: str
    manufacturer: str
    os: str
    os_version: str
    connection_mode: str
    is_connected: bool
    video_device_index: Optional[int] = None
    forwarded_port: Optional[int] = None
    error_message: str
    last_heartbeat: float


class ConnectResponse(BaseModel):
    success: bool
    serial: str
    model: str
    connection_mode: str
    error_message: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/status", response_model=MobileStatusResponse)
async def get_mobile_status():
    """Return the aggregate status of the mobile USB subsystem without disruptive hardware re-scanning."""
    devices = list(mobile_manager.devices.values())
    return MobileStatusResponse(
        adb_available=mobile_manager.adb.available,
        scrcpy_available=bool(shutil.which("scrcpy")),
        platform=platform.system(),
        device_count=len(devices),
        connected_count=sum(1 for d in devices if d.is_connected),
    )


@router.post("/scan", response_model=list[DeviceResponse])
async def scan_devices():
    """Trigger a fresh scan for USB-connected mobile phones."""
    status = await asyncio.to_thread(mobile_manager.scan)
    return [
        DeviceResponse(**d)
        for d in mobile_manager.get_all_status()
    ]


@router.get("/devices", response_model=list[DeviceResponse])
async def list_devices():
    """List all currently known mobile devices (without a fresh scan)."""
    return [
        DeviceResponse(**d)
        for d in mobile_manager.get_all_status()
    ]


@router.post("/connect", response_model=ConnectResponse)
async def connect_device(payload: ConnectRequest):
    """
    Connect to a USB-attached mobile phone camera.

    Requires either:
    - Phone in UVC Webcam mode (Android 14+ Developer Options > USB Webcam)
    - ADB + IP Webcam app running on the phone
    - ADB + scrcpy installed on the host
    """
    try:
        mode = ConnectionMode(payload.mode)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid mode '{payload.mode}'. "
                   f"Valid: auto, uvc_webcam, adb_scrcpy, adb_ipwebcam",
        )

    success, device = await asyncio.to_thread(
        mobile_manager.connect_device,
        payload.serial,
        mode,
        payload.camera_id,
    )

    if success:
        # Register into ONE EYE CCTV Pipeline & Database
        cam_id = payload.camera_id or f"CAM_MOB_{device.serial[:8].upper()}"
        source_uri = f"mobile:{device.serial}"
        try:
            from app.cv.pipeline import pipeline_manager
            from app.db.database import AsyncSessionLocal
            from app.db.repositories.camera_repo import CameraRepository
            from app.db.models import Camera

            pipeline_manager.register_camera(cam_id, source_uri)
            pipeline_manager.start_camera(cam_id)

            async with AsyncSessionLocal() as db:
                repo = CameraRepository(db)
                existing = await repo.get_by_id(cam_id)
                if not existing:
                    new_cam = Camera(
                        id=cam_id,
                        name=f"Mobile ({device.model})",
                        source=source_uri,
                        source_type="mobile",
                        status="ONLINE",
                        resolution="1280x720",
                        fps=30.0,
                    )
                    await repo.create(new_cam)
                else:
                    await repo.update(cam_id, status="ONLINE", source=source_uri)
        except Exception as e:
            logger.warning(f"Note on pipeline/DB registration for mobile camera: {e}")

    return ConnectResponse(
        success=success,
        serial=device.serial,
        model=device.model,
        connection_mode=device.connection_mode.value,
        error_message=device.error_message,
    )


@router.post("/disconnect")
async def disconnect_device(payload: DisconnectRequest):
    """Disconnect a mobile phone camera."""
    ok = await asyncio.to_thread(mobile_manager.disconnect_device, payload.serial)
    try:
        from app.cv.pipeline import pipeline_manager
        from app.db.database import AsyncSessionLocal
        from app.db.repositories.camera_repo import CameraRepository

        # Stop matching pipeline
        for cam_id, p in list(pipeline_manager.pipelines.items()):
            if p.source_uri == f"mobile:{payload.serial}":
                await p.stop()
                async with AsyncSessionLocal() as db:
                    repo = CameraRepository(db)
                    await repo.update(cam_id, status="OFFLINE")
    except Exception as e:
        logger.warning(f"Note on mobile disconnect cleanup: {e}")

    return {"success": ok, "serial": payload.serial}


@router.get("/stream/{serial}")
async def stream_device(serial: str, fps: int = Query(default=15, ge=1, le=60)):
    """
    Live MJPEG preview stream from a connected mobile phone camera.
    Suitable for <img src="..."> in the dashboard.
    """
    source = mobile_manager.get_source(serial)
    if not source or not source.is_alive():
        raise HTTPException(
            status_code=404,
            detail=f"Device '{serial}' is not connected or not streaming.",
        )

    async def frame_generator():
        interval = 1.0 / fps
        while True:
            ok, frame, _ = source.read()
            if not ok or frame is None:
                break
            _, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (
                b"--frame\r\n"
                b"Content-Type: image/jpeg\r\n\r\n"
                + jpeg.tobytes()
                + b"\r\n"
            )
            await asyncio.sleep(interval)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/host-info")
async def get_host_info():
    """Return the local network IP so mobile devices on the same Wi-Fi / USB tether can connect."""
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    return {
        "local_ip": local_ip,
        "web_cam_url": f"http://{local_ip}:3001/mobile-cam",
        "api_url": f"http://{local_ip}:8001",
    }


class LaunchCameraRequest(BaseModel):
    serial: Optional[str] = None


class OpenBrowserCamRequest(BaseModel):
    serial: Optional[str] = None
    url: Optional[str] = None


@router.post("/launch-camera")
async def launch_camera_on_phone(payload: LaunchCameraRequest = LaunchCameraRequest()):
    """Send ADB intent to wake up phone screen and automatically launch the camera app."""
    ok = await asyncio.to_thread(mobile_manager.adb.launch_camera, payload.serial)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Failed to launch camera on phone. Ensure phone is connected via USB with USB Debugging enabled.",
        )
    return {"success": True, "message": "Camera app launched on phone."}


@router.post("/open-browser-cam")
async def open_browser_cam_on_phone(payload: OpenBrowserCamRequest = OpenBrowserCamRequest()):
    """Send ADB command to open the ONE EYE mobile camera broadcaster page in phone's browser."""
    import socket
    local_ip = "127.0.0.1"
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        pass

    target_url = payload.url or f"http://{local_ip}:3001/mobile-cam"
    ok = await asyncio.to_thread(mobile_manager.adb.open_url, target_url, payload.serial)
    if not ok:
        raise HTTPException(
            status_code=400,
            detail="Failed to open browser on phone. Ensure phone is connected with USB Debugging enabled.",
        )
    return {"success": True, "url": target_url}


@router.post("/direct-usb-stream")
async def start_direct_usb_stream(payload: OpenBrowserCamRequest = OpenBrowserCamRequest()):
    """
    Direct USB Web Stream Mode:
    1. Detects USB-connected mobile phone via ADB.
    2. Activates ADB reverse tunnels (tcp:3001 and tcp:8001).
    3. Launches http://localhost:3001/mobile-cam in phone's browser over the physical USB cable.
    4. Automatically registers and starts CAM_MOBILE in pipeline_manager.
    """
    from app.cv.pipeline import pipeline_manager
    from app.db.database import AsyncSessionLocal
    from app.db.repositories.camera_repo import CameraRepository
    from app.db.models import Camera

    camera_id = "CAM_MOBILE"
    source_uri = f"mobile_web:{camera_id}"
    
    # 1. Setup ADB reverse tunnels and launch browser on phone
    ok = await asyncio.to_thread(mobile_manager.adb.open_url, "http://localhost:3001/mobile-cam", payload.serial)
    
    # 2. Register camera pipeline
    pipeline_manager.register_camera(camera_id, source_uri)
    pipeline_manager.start_camera(camera_id)

    # 3. Ensure camera exists in DB
    try:
        async with AsyncSessionLocal() as db:
            repo = CameraRepository(db)
            existing = await repo.get_by_id(camera_id)
            if not existing:
                new_cam = Camera(
                    id=camera_id,
                    name="Mobile Live Camera (Direct USB Web Stream)",
                    source=source_uri,
                    source_type="mobile",
                    status="ONLINE",
                    resolution="1280x720",
                    fps=30.0,
                )
                await repo.create(new_cam)
            else:
                await repo.update(camera_id, status="ONLINE", source=source_uri)
    except Exception as e:
        logger.warning(f"Error registering mobile camera in DB: {e}")

    return {
        "success": True,
        "mode": "DIRECT_USB_WEB_STREAM",
        "camera_id": camera_id,
        "usb_reverse_active": True,
        "url": "http://localhost:3001/mobile-cam",
        "adb_available": mobile_manager.adb.available
    }


@router.websocket("/ws/stream/{camera_id}")
async def mobile_stream_ws(websocket: WebSocket, camera_id: str = "CAM_MOBILE"):
    """
    High-performance WebSocket frame ingest endpoint.
    Accepts raw binary JPEG frames sent from any mobile browser at /mobile-cam.
    """
    await websocket.accept()
    logger.info(f"Mobile web camera stream connected for camera {camera_id}")

    # Register into CCTV pipeline & database
    try:
        from app.cv.pipeline import pipeline_manager
        from app.db.database import AsyncSessionLocal
        from app.db.repositories.camera_repo import CameraRepository
        from app.db.models import Camera

        source_uri = f"mobile_web:{camera_id}"
        pipeline_manager.register_camera(camera_id, source_uri)
        pipeline_manager.start_camera(camera_id)

        async with AsyncSessionLocal() as db:
            repo = CameraRepository(db)
            existing = await repo.get_by_id(camera_id)
            if not existing:
                new_cam = Camera(
                    id=camera_id,
                    name="Mobile Live Camera (Web/USB)",
                    source=source_uri,
                    source_type="mobile",
                    status="ONLINE",
                    resolution="1280x720",
                    fps=30.0,
                )
                await repo.create(new_cam)
            else:
                await repo.update(camera_id, status="ONLINE", source=source_uri)
    except Exception as e:
        logger.warning(f"Error registering mobile web camera in DB: {e}")

    try:
        while True:
            data = await websocket.receive_bytes()
            # Decode JPEG in-memory
            nparr = np.frombuffer(data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if frame is not None:
                mobile_manager.update_web_frame(camera_id, frame)
                mobile_manager.update_web_frame("CAM_MOB_24151JEG", frame)
                mobile_manager.update_web_frame("CAM_MOBILE", frame)
                mobile_manager.update_web_frame("24151JEGR16946", frame)
                for dev_serial in list(mobile_manager.devices.keys()):
                    mobile_manager.update_web_frame(dev_serial, frame)
                    mobile_manager.update_web_frame(f"CAM_MOB_{dev_serial[:8].upper()}", frame)
    except WebSocketDisconnect:
        logger.info(f"Mobile web camera disconnected: {camera_id}")
    except Exception as e:
        logger.warning(f"Mobile stream error: {e}")


@router.post("/rtsp-connect")
async def connect_rtsp_camera(req: RTSPConnectRequest, db: AsyncSession = Depends(get_db)):
    """
    Connect any mobile phone or factory CCTV camera via standard RTSP / HTTP URL.
    Examples:
      - rtsp://192.168.1.105:8554/live  (Larix Broadcaster / RTSP Camera App)
      - http://192.168.1.105:8080/video (IP Webcam Android App)
    """
    repo = CameraRepository(db)
    cam = await repo.get_by_id(req.camera_id)
    if cam:
        await repo.update(req.camera_id, source=req.url, status="ONLINE", source_type="rtsp")
    else:
        cam = Camera(
            id=req.camera_id,
            name=req.name,
            source=req.url,
            source_type="rtsp",
            status="ONLINE",
            fps=30.0,
            resolution="1280x720",
            is_calibrated=True
        )
        await repo.create(cam)

    # Register and start pipeline with new RTSP source immediately
    pipeline_manager.register_camera(req.camera_id, req.url)
    pipeline_manager.start_camera(req.camera_id)
    logger.info(f"Connected RTSP camera '{req.camera_id}' to source: {req.url}")
    return {"status": "connected", "camera_id": req.camera_id, "url": req.url}

