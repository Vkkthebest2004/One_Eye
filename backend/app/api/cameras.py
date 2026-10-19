from typing import List
import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException, status, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import Camera
from app.db.repositories.camera_repo import CameraRepository
from app.api.schemas import CameraCreate, CameraUpdate, CameraResponse
from app.cv.pipeline import pipeline_manager

router = APIRouter(prefix="/api/cameras", tags=["Cameras"])


@router.get("", response_model=List[CameraResponse])
async def list_cameras(db: AsyncSession = Depends(get_db)):
    repo = CameraRepository(db)
    return await repo.get_all()


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    repo = CameraRepository(db)
    cam = await repo.get_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    return cam


@router.post("", response_model=CameraResponse, status_code=status.HTTP_201_CREATED)
async def create_camera(payload: CameraCreate, db: AsyncSession = Depends(get_db)):
    repo = CameraRepository(db)
    existing = await repo.get_by_id(payload.id)
    if existing:
        raise HTTPException(status_code=400, detail="Camera with this ID already exists")

    camera = Camera(
        id=payload.id,
        name=payload.name,
        source=payload.source,
        source_type=payload.source_type,
        fps=payload.fps,
        resolution=payload.resolution,
        status="ONLINE"
    )
    created = await repo.create(camera)

    # Register with CV pipeline manager
    pipeline_manager.register_camera(created.id, created.source)
    pipeline_manager.start_camera(created.id)

    return created


@router.put("/{camera_id}", response_model=CameraResponse)
async def update_camera(camera_id: str, payload: CameraUpdate, db: AsyncSession = Depends(get_db)):
    repo = CameraRepository(db)
    updated = await repo.update(camera_id, **payload.model_dump(exclude_unset=True))
    if not updated:
        raise HTTPException(status_code=404, detail="Camera not found")
    if "source" in payload.model_dump(exclude_unset=True):
        pipeline_manager.register_camera(updated.id, updated.source)
    return updated


@router.post("/use-webcam")
async def switch_to_laptop_webcam(camera_id: str = "CAM_01", db: AsyncSession = Depends(get_db)):
    """Set the specified camera (defaults to CAM_01) to stream live from the laptop webcam (device index 0)."""
    repo = CameraRepository(db)
    cam = await repo.get_by_id(camera_id)
    if not cam:
        cam = Camera(
            id=camera_id,
            name="Sector A - Laptop Webcam (FaceTime HD)",
            source="0",
            source_type="webcam",
            status="ONLINE",
            fps=30.0,
            resolution="1280x720",
            is_calibrated=True
        )
        cam = await repo.create(cam)
    else:
        cam = await repo.update(
            camera_id,
            name="Sector A - Laptop Webcam (FaceTime HD)",
            source="0",
            source_type="webcam",
            status="ONLINE"
        )
    # Restart pipeline with device 0
    pipe = pipeline_manager.register_camera(cam.id, "0")
    pipe.start()
    return {
        "success": True,
        "camera_id": cam.id,
        "name": cam.name,
        "source": cam.source,
        "message": f"Camera '{cam.id}' is now live on Laptop Webcam (FaceTime HD Camera)"
    }


@router.post("/use-demo-video")
async def switch_to_demo_video(camera_id: str = "CAM_01", db: AsyncSession = Depends(get_db)):
    """Set the specified camera (defaults to CAM_01) back to demo video feed."""
    repo = CameraRepository(db)
    cam = await repo.update(
        camera_id,
        name="Sector A - Main Corridor",
        source="videos/demo/factory_safety.mp4",
        source_type="video",
        status="ONLINE"
    )
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")
    pipe = pipeline_manager.register_camera(cam.id, "videos/demo/factory_safety.mp4")
    pipe.start()
    return {
        "success": True,
        "camera_id": cam.id,
        "name": cam.name,
        "source": cam.source,
        "message": f"Camera '{cam.id}' switched to factory demo video"
    }


@router.post("/{camera_id}/stop")
async def stop_camera_feed(camera_id: str, db: AsyncSession = Depends(get_db)):
    """Stop camera pipeline, release hardware video capture, and set status to OFFLINE."""
    repo = CameraRepository(db)
    cam = await repo.get_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    await pipeline_manager.stop_camera(camera_id)
    updated = await repo.update(camera_id, status="OFFLINE")

    from app.alerts.dispatcher import dispatcher
    await dispatcher.broadcast_camera_status(camera_id, "OFFLINE", 0.0)

    return {
        "success": True,
        "camera_id": camera_id,
        "status": "OFFLINE",
        "message": f"Camera '{cam.name}' ({camera_id}) stopped and hardware capture released."
    }


@router.post("/{camera_id}/start")
async def start_camera_feed(camera_id: str, db: AsyncSession = Depends(get_db)):
    """Start or resume camera pipeline, connect hardware video capture, and set status to ONLINE."""
    repo = CameraRepository(db)
    cam = await repo.get_by_id(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    pipe = pipeline_manager.get_pipeline(camera_id)
    if not pipe:
        pipe = pipeline_manager.register_camera(cam.id, cam.source)
    else:
        pipe.start()

    updated = await repo.update(camera_id, status="ONLINE")

    from app.alerts.dispatcher import dispatcher
    await dispatcher.broadcast_camera_status(camera_id, "ONLINE", 30.0)

    return {
        "success": True,
        "camera_id": camera_id,
        "status": "ONLINE",
        "message": f"Camera '{cam.name}' ({camera_id}) started and hardware connected."
    }


@router.post("/{camera_id}/toggle")
async def toggle_camera_feed(camera_id: str, db: AsyncSession = Depends(get_db)):
    """Toggle camera hardware state between active (ONLINE) and stopped (OFFLINE)."""
    pipe = pipeline_manager.get_pipeline(camera_id)
    is_running = pipe.is_running if pipe else False

    if is_running:
        return await stop_camera_feed(camera_id, db)
    else:
        return await start_camera_feed(camera_id, db)


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    repo = CameraRepository(db)
    deleted = await repo.delete(camera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Camera not found")
    await pipeline_manager.remove_camera(camera_id)
    return None


@router.get("/{camera_id}/stream")
async def get_camera_stream(camera_id: str, fps: int = 30):
    """High-speed live MJPEG video stream from camera pipeline (up to 60 FPS)."""
    import cv2
    import numpy as np
    import asyncio
    from fastapi.responses import StreamingResponse

    pipe = pipeline_manager.get_pipeline(camera_id)
    if not pipe:
        # If mobile camera or webcam, auto-register and start pipeline immediately
        if camera_id.startswith("CAM_MOB") or camera_id == "CAM_MOBILE":
            source_uri = f"mobile_web:{camera_id}"
            pipeline_manager.register_camera(camera_id, source_uri)
            pipeline_manager.start_camera(camera_id)
            pipe = pipeline_manager.get_pipeline(camera_id)
        elif camera_id == "CAM_WEBCAM" or camera_id.startswith("CAM_WEB"):
            pipeline_manager.register_camera(camera_id, "0")
            pipeline_manager.start_camera(camera_id)
            pipe = pipeline_manager.get_pipeline(camera_id)

    if not pipe:
        raise HTTPException(status_code=404, detail=f"Camera pipeline '{camera_id}' not found")

    target_fps = min(30, max(1, fps))
    interval = 1.0 / target_fps
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 65]

    # Pre-render standby banner for when camera is offline or connecting
    standby_img = np.zeros((360, 640, 3), dtype=np.uint8)
    standby_img[:] = (18, 24, 27)
    cv2.rectangle(standby_img, (20, 20), (620, 340), (38, 52, 60), 1)
    cv2.putText(standby_img, "ONE EYE // LIVE SURVEILLANCE FEED", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 1)
    cv2.putText(standby_img, f"CAMERA ID: {camera_id}", (40, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 180, 190), 1)
    cv2.putText(standby_img, "STATUS: AWAITING ACTIVE VIDEO STREAM", (40, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 180), 2)
    cv2.putText(standby_img, "Feed ready — connecting camera source...", (40, 225), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 160, 170), 1)
    _, standby_jpeg_raw = cv2.imencode(".jpg", standby_img, [cv2.IMWRITE_JPEG_QUALITY, 60])
    standby_bytes = standby_jpeg_raw.tobytes()

    # Pre-render stopped banner
    stopped_img = np.zeros((360, 640, 3), dtype=np.uint8)
    stopped_img[:] = (15, 18, 22)
    cv2.rectangle(stopped_img, (20, 20), (620, 340), (60, 40, 40), 1)
    cv2.putText(stopped_img, "ONE EYE // SURVEILLANCE FEED", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (180, 190, 200), 1)
    cv2.putText(stopped_img, f"CAMERA ID: {camera_id}", (40, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (120, 130, 140), 1)
    cv2.putText(stopped_img, "STATUS: CAMERA STOPPED (OFFLINE)", (40, 190), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 160, 255), 2)
    cv2.putText(stopped_img, "Hardware released — click 'Start Camera' to resume", (40, 225), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 150, 160), 1)
    _, stopped_jpeg_raw = cv2.imencode(".jpg", stopped_img, [cv2.IMWRITE_JPEG_QUALITY, 60])
    stopped_bytes = stopped_jpeg_raw.tobytes()

    async def frame_generator():
        last_frame_ref = None
        cached_bytes = standby_bytes
        try:
            while True:
                t0 = asyncio.get_event_loop().time()
                if not pipe or not pipe.is_running:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + stopped_bytes
                        + b"\r\n"
                    )
                    await asyncio.sleep(0.5)
                    continue

                frame = pipe.latest_frame
                if camera_id.startswith("CAM_MOB") or camera_id == "CAM_MOBILE":
                    from app.cv.usb_mobile import mobile_manager
                    web_res = (
                        mobile_manager.get_web_frame(camera_id)
                        or mobile_manager.get_web_frame("CAM_MOBILE")
                        or mobile_manager.get_web_frame("CAM_MOB_24151JEG")
                        or mobile_manager.get_web_frame("24151JEGR16946")
                    )
                    if web_res and web_res[0] is not None:
                        frame = web_res[0]
                        pipe.latest_frame = frame

                if frame is not None:
                    # Only re-encode when a new frame is received
                    if frame is not last_frame_ref:
                        last_frame_ref = frame
                        h_f, w_f = frame.shape[:2]
                        # Downscale for web dashboard to save 80% RAM churn
                        if w_f > 640:
                            scaled_frame = cv2.resize(frame, (640, int(h_f * 640.0 / w_f)), interpolation=cv2.INTER_LINEAR)
                        else:
                            scaled_frame = frame
                        ok, jpeg = cv2.imencode(".jpg", scaled_frame, encode_params)
                        if ok:
                            cached_bytes = jpeg.tobytes()
                    out_bytes = cached_bytes
                else:
                    out_bytes = standby_bytes

                if out_bytes:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + out_bytes
                        + b"\r\n"
                    )
                elapsed = asyncio.get_event_loop().time() - t0
                sleep_time = max(0.015, interval - elapsed)
                await asyncio.sleep(sleep_time)
        finally:
            last_frame_ref = None
            cached_bytes = None

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/{camera_id}/snapshot")
async def get_camera_snapshot(camera_id: str):
    """Return a crisp, real-time JPEG still frame snapshot from the active camera pipeline."""
    pipe = pipeline_manager.get_pipeline(camera_id)
    frame = pipe.latest_frame if pipe else None

    if camera_id.startswith("CAM_MOB") or camera_id == "CAM_MOBILE":
        from app.cv.usb_mobile import mobile_manager
        web_res = (
            mobile_manager.get_web_frame(camera_id)
            or mobile_manager.get_web_frame("CAM_MOBILE")
            or mobile_manager.get_web_frame("CAM_MOB_24151JEG")
            or mobile_manager.get_web_frame("24151JEGR16946")
        )
        if web_res and web_res[0] is not None:
            frame = web_res[0]

    if frame is None:
        standby_img = np.zeros((480, 640, 3), dtype=np.uint8)
        standby_img[:] = (18, 24, 27)
        cv2.rectangle(standby_img, (20, 20), (620, 460), (38, 52, 60), 1)
        cv2.putText(standby_img, "ONE EYE // LIVE SURVEILLANCE FEED", (40, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 220, 255), 1)
        cv2.putText(standby_img, f"CAMERA ID: {camera_id}", (40, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (160, 180, 190), 1)
        cv2.putText(standby_img, "STATUS: AWAITING ACTIVE VIDEO STREAM", (40, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 255, 180), 2)
        cv2.putText(standby_img, "Start mobile stream or check hardware connection", (40, 265), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (140, 160, 170), 1)
        frame = standby_img

    ok, jpeg = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to encode snapshot image")

    from fastapi import Response
    return Response(content=jpeg.tobytes(), media_type="image/jpeg")
