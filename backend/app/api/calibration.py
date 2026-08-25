from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.camera_repo import CameraRepository
from app.api.schemas import CalibrationRequest, CalibrationResponse
from app.cv.pipeline import pipeline_manager
from app.cv.homography import HomographyCalibrator

router = APIRouter(prefix="/api/calibration", tags=["Calibration"])


@router.post("/compute", response_model=CalibrationResponse)
async def compute_calibration(payload: CalibrationRequest, db: AsyncSession = Depends(get_db)):
    if len(payload.image_points) < 4 or len(payload.world_points) < 4:
        raise HTTPException(status_code=400, detail="At least 4 corresponding image and world points required")

    calibrator = HomographyCalibrator(camera_id=payload.camera_id)
    img_pts = [(p[0], p[1]) for p in payload.image_points]
    world_pts = [(p[0], p[1]) for p in payload.world_points]

    success = calibrator.calibrate(img_pts, world_pts)
    if not success or calibrator.H_matrix is None:
        raise HTTPException(status_code=400, detail="Homography matrix computation failed. Check point linearity.")

    matrix_list = calibrator.H_matrix.tolist()

    # Save to database
    repo = CameraRepository(db)
    await repo.update(
        payload.camera_id,
        calibration_matrix=matrix_list,
        calibration_points={"image": payload.image_points, "world": payload.world_points},
        is_calibrated=True
    )

    # Update runtime pipeline
    pipeline = pipeline_manager.get_pipeline(payload.camera_id)
    if pipeline:
        pipeline.homography.calibrate(img_pts, world_pts)

    return CalibrationResponse(
        camera_id=payload.camera_id,
        is_calibrated=True,
        matrix=matrix_list,
        message="Camera planar homography calibrated successfully."
    )
