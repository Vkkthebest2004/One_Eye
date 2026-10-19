import logging
from sqlalchemy import select
from app.db.database import AsyncSessionLocal
from app.db.models import Camera, Zone, Machine

logger = logging.getLogger(__name__)


async def seed_initial_data():
    """Seed default industrial CCTV and Mobile phone surveillance channels."""
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Camera))
        existing_cams = res.scalars().all()
        existing_ids = {c.id for c in existing_cams}

        default_cameras = [
            Camera(
                id="CAM_WEBCAM",
                name="Laptop Built-in Webcam (FaceTime HD)",
                source="0",
                source_type="webcam",
                status="ONLINE",
                fps=30.0,
                resolution="1280x720",
                is_calibrated=True,
                calibration_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                calibration_points={"image": [[100, 100], [500, 100], [500, 400], [100, 400]], "world": [[0, 0], [4, 0], [4, 3], [0, 3]]},
            ),
        ]

        # Purge any legacy demo or mobile cameras
        from sqlalchemy import delete
        await db.execute(delete(Camera).where(Camera.id.in_(["CAM_01", "CAM_02", "CAM_03", "CAM_04", "CAM_MOBILE", "CAM_MOB_24151JEG"])))

        for cam in default_cameras:
            if cam.id not in existing_ids:
                db.add(cam)
                logger.info(f"Seeded camera: {cam.id} ({cam.name})")

        # Seed default restricted zone on laptop webcam
        res_z = await db.execute(select(Zone))
        existing_zones = {z.id for z in res_z.scalars().all()}

        default_zones = [
            Zone(
                id="ZONE_WEBCAM_DANGER",
                camera_id="CAM_WEBCAM",
                name="Marked Danger Perimeter",
                polygon=[[0.72, 0.08], [0.98, 0.08], [0.98, 0.45], [0.72, 0.45]],
                severity=85,
                active=True,
            ),
        ]

        # Purge legacy zones
        await db.execute(delete(Zone).where(Zone.camera_id != "CAM_WEBCAM"))
        await db.execute(delete(Machine).where(Machine.camera_id != "CAM_WEBCAM"))

        for z in default_zones:
            if z.id not in existing_zones:
                db.add(z)
                logger.info(f"Seeded zone: {z.id} ({z.name})")

        await db.commit()
        logger.info("Database seeding complete: Laptop Webcam ONLY.")
