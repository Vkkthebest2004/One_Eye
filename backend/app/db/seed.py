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
                id="CAM_01",
                name="Sector A - Main Corridor",
                source="videos/demo/corridor.mp4",
                source_type="video",
                status="ONLINE",
                fps=30.0,
                resolution="1280x720",
                is_calibrated=True,
                calibration_matrix=[[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]],
                calibration_points={"image": [[100, 100], [500, 100], [500, 400], [100, 400]], "world": [[0, 0], [4, 0], [4, 3], [0, 3]]},
            ),
            Camera(
                id="CAM_02",
                name="Sector B - Robotic Assembly",
                source="videos/demo/assembly.mp4",
                source_type="video",
                status="ONLINE",
                fps=30.0,
                resolution="1280x720",
                is_calibrated=True,
            ),
            Camera(
                id="CAM_03",
                name="Sector C - Heavy Machinery Press",
                source="videos/demo/machinery.mp4",
                source_type="video",
                status="ONLINE",
                fps=30.0,
                resolution="1280x720",
                is_calibrated=True,
            ),
            Camera(
                id="CAM_04",
                name="Sector D - Logistics Loading Dock",
                source="videos/demo/loading_dock.mp4",
                source_type="video",
                status="ONLINE",
                fps=30.0,
                resolution="1280x720",
                is_calibrated=True,
            ),
            Camera(
                id="CAM_MOBILE",
                name="Google Pixel 6a (Mobile Camera)",
                source="mobile_web:CAM_MOBILE",
                source_type="mobile",
                status="ONLINE",
                fps=30.0,
                resolution="1280x720",
                is_calibrated=True,
            ),
        ]

        for cam in default_cameras:
            if cam.id not in existing_ids:
                db.add(cam)
                logger.info(f"Seeded camera: {cam.id} ({cam.name})")

        # Seed default restricted zones
        res_z = await db.execute(select(Zone))
        existing_zones = {z.id for z in res_z.scalars().all()}

        default_zones = [
            Zone(
                id="ZONE_01_DANGER",
                camera_id="CAM_01",
                name="High-Voltage Forklift Path",
                polygon=[[0.2, 0.45], [0.8, 0.45], [0.85, 0.95], [0.15, 0.95]],
                severity=90,
                active=True,
            ),
            Zone(
                id="ZONE_02_ROBOT",
                camera_id="CAM_02",
                name="Robotic Arm Sweep Perimeter",
                polygon=[[0.3, 0.3], [0.75, 0.3], [0.75, 0.8], [0.3, 0.8]],
                severity=95,
                active=True,
            ),
            Zone(
                id="ZONE_03_PRESS",
                camera_id="CAM_03",
                name="Hydraulic Press Danger Perimeter",
                polygon=[[0.25, 0.35], [0.75, 0.35], [0.75, 0.9], [0.25, 0.9]],
                severity=100,
                active=True,
            ),
            Zone(
                id="ZONE_04_DOCK",
                camera_id="CAM_04",
                name="Dock Vehicle Loading Bay",
                polygon=[[0.15, 0.5], [0.85, 0.5], [0.9, 0.98], [0.1, 0.98]],
                severity=85,
                active=True,
            ),
        ]

        for z in default_zones:
            if z.id not in existing_zones:
                db.add(z)
                logger.info(f"Seeded zone: {z.id} ({z.name})")

        # Ensure legacy mobile demo perimeters are removed
        from sqlalchemy import delete
        await db.execute(delete(Zone).where(Zone.id.in_(["ZONE_MOB_RESTRICTED", "ZONE_MOB_PIXEL"])))

        await db.commit()
        logger.info("Database seeding complete.")
