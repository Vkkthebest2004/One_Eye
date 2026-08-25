from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
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
    return updated


@router.delete("/{camera_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_camera(camera_id: str, db: AsyncSession = Depends(get_db)):
    repo = CameraRepository(db)
    deleted = await repo.delete(camera_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Camera not found")
    return None


@router.get("/{camera_id}/stream")
async def get_camera_stream(camera_id: str, fps: int = 30):
    """High-speed live MJPEG video stream from camera pipeline (up to 60 FPS)."""
    import cv2
    import asyncio
    from fastapi.responses import StreamingResponse

    pipe = pipeline_manager.get_pipeline(camera_id)
    if not pipe:
        raise HTTPException(status_code=404, detail="Camera pipeline not found")

    target_fps = min(60, max(1, fps))
    interval = 1.0 / target_fps
    encode_params = [cv2.IMWRITE_JPEG_QUALITY, 70]

    async def frame_generator():
        last_frame_ref = None
        cached_jpeg = None
        while True:
            t0 = asyncio.get_event_loop().time()
            frame = pipe.latest_frame
            if frame is not None:
                # Fast path: only encode if new frame object arrived
                if frame is not last_frame_ref or cached_jpeg is None:
                    ok, jpeg = cv2.imencode(".jpg", frame, encode_params)
                    if ok:
                        cached_jpeg = jpeg.tobytes()
                        last_frame_ref = frame
                
                if cached_jpeg:
                    yield (
                        b"--frame\r\n"
                        b"Content-Type: image/jpeg\r\n\r\n"
                        + cached_jpeg
                        + b"\r\n"
                    )
            elapsed = asyncio.get_event_loop().time() - t0
            sleep_time = max(0.005, interval - elapsed)
            await asyncio.sleep(sleep_time)

    return StreamingResponse(
        frame_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )
