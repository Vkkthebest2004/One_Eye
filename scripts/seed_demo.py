import asyncio
import datetime
import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_path = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_path))

from app.db.database import init_db, AsyncSessionLocal
from app.db.models import Camera, Zone, Machine, SafetyEvent, AuditLog, AlertRecord


async def seed_database():
    print("Initializing database and seeding demo industrial data...")
    await init_db()

    async with AsyncSessionLocal() as db:
        # Check existing cameras
        from sqlalchemy import select
        existing_cams = (await db.execute(select(Camera))).scalars().all()
        if existing_cams:
            print(f"Database already contains {len(existing_cams)} cameras. Updating / ensuring seed data...")

        # 1. Seed Cameras
        cameras_data = [
            {
                "id": "CAM_01",
                "name": "Heavy Stamping & Press Bay",
                "source": "./videos/demo/factory_safety.mp4",
                "source_type": "video",
                "status": "ONLINE",
                "fps": 30.0,
                "resolution": "1280x720",
                "is_calibrated": True,
                "calibration_points": {
                    "image": [[200, 250], [580, 250], [640, 620], [150, 620]],
                    "world": [[0, 0], [6.0, 0], [6.0, 8.0], [0, 8.0]]
                }
            },
            {
                "id": "CAM_02",
                "name": "Robotic Welding Cell A",
                "source": "./videos/demo/factory_safety.mp4",
                "source_type": "video",
                "status": "ONLINE",
                "fps": 30.0,
                "resolution": "1280x720",
                "is_calibrated": False
            },
            {
                "id": "CAM_03",
                "name": "Chemical Storage & Flammables",
                "source": "./videos/demo/factory_safety.mp4",
                "source_type": "video",
                "status": "ONLINE",
                "fps": 30.0,
                "resolution": "1280x720",
                "is_calibrated": False
            },
            {
                "id": "CAM_04",
                "name": "Logistics Loading Dock 4",
                "source": "./videos/demo/factory_safety.mp4",
                "source_type": "video",
                "status": "ONLINE",
                "fps": 25.0,
                "resolution": "1280x720",
                "is_calibrated": False
            }
        ]

        for cdata in cameras_data:
            existing = await db.get(Camera, cdata["id"])
            if not existing:
                cam = Camera(**cdata)
                db.add(cam)

        await db.commit()

        # 2. Seed Zones
        zones_data = [
            {
                "id": "zone_press_01",
                "camera_id": "CAM_01",
                "name": "Hydraulic Press Danger Perimeter",
                "polygon": [[200, 250], [580, 250], [640, 620], [150, 620]],
                "severity": 85,
                "active": True
            },
            {
                "id": "zone_robot_arc",
                "camera_id": "CAM_02",
                "name": "Welding Arc Flash Hazard Zone",
                "polygon": [[350, 200], [700, 200], [750, 550], [300, 550]],
                "severity": 80,
                "active": True
            }
        ]

        for zdata in zones_data:
            existing = await db.get(Zone, zdata["id"])
            if not existing:
                z = Zone(**zdata)
                db.add(z)

        await db.commit()

        # 3. Seed Machines
        machines_data = [
            {
                "id": "press_mach_01",
                "camera_id": "CAM_01",
                "name": "Hydraulic Stamping Press #01",
                "geometry": [300, 280, 220, 200], # [x, y, w, h]
                "danger_radius_m": 1.5,
                "active": True
            },
            {
                "id": "robot_arm_02",
                "camera_id": "CAM_02",
                "name": "KUKA 6-Axis Welding Arm",
                "geometry": [450, 250, 180, 180],
                "danger_radius_m": 2.0,
                "active": True
            }
        ]

        for mdata in machines_data:
            existing = await db.get(Machine, mdata["id"])
            if not existing:
                m = Machine(**mdata)
                db.add(m)

        await db.commit()

        # 4. Seed Historical Events for Analytics Trends
        now = datetime.datetime.utcnow()
        historical_events = [
            {
                "id": "EVT-20260824-0001",
                "camera_id": "CAM_01",
                "worker_id": 7,
                "hazard_types": ["RESTRICTED_ZONE", "UNSAFE_PROXIMITY_CRITICAL", "NO_HELMET"],
                "primary_hazard": "UNSAFE_PROXIMITY_CRITICAL",
                "risk_score": 86,
                "severity": "CRITICAL",
                "confidence": 0.95,
                "started_at": now - datetime.timedelta(hours=28),
                "updated_at": now - datetime.timedelta(hours=28, minutes=-2),
                "acknowledged_at": now - datetime.timedelta(hours=28, minutes=-1),
                "resolved_at": now - datetime.timedelta(hours=28, minutes=-5),
                "status": "RESOLVED",
                "distance_m": 1.1,
                "exposure_seconds": 8.4,
                "description": "Worker #07 entered hydraulic press perimeter without helmet at 1.1m proximity.",
                "rule_triggered": "Rule [UNSAFE_PROXIMITY_CRITICAL] Base=85 + Prox=25 + Dur=16 + Syn=20 -> Score=86 (CRITICAL)",
                "recommended_action": "Emergency intervene: Halt active machinery and move worker back.",
                "is_demo": True
            },
            {
                "id": "EVT-20260824-0002",
                "camera_id": "CAM_02",
                "worker_id": 3,
                "hazard_types": ["NO_HELMET"],
                "primary_hazard": "NO_HELMET",
                "risk_score": 42,
                "severity": "MEDIUM",
                "confidence": 0.91,
                "started_at": now - datetime.timedelta(hours=20),
                "updated_at": now - datetime.timedelta(hours=20, minutes=-3),
                "acknowledged_at": now - datetime.timedelta(hours=20, minutes=-2),
                "resolved_at": now - datetime.timedelta(hours=20, minutes=-4),
                "status": "RESOLVED",
                "distance_m": None,
                "exposure_seconds": 4.1,
                "description": "Worker #03 observed without mandatory safety helmet in welding corridor.",
                "rule_triggered": "PPE Debounce Confirmed: Worker #03 Missing Safety Hardhat",
                "recommended_action": "Instruct worker to equip required safety hardhat immediately.",
                "is_demo": True
            },
            {
                "id": "EVT-20260825-0001",
                "camera_id": "CAM_03",
                "worker_id": 5,
                "hazard_types": ["RESTRICTED_ZONE"],
                "primary_hazard": "RESTRICTED_ZONE",
                "risk_score": 68,
                "severity": "HIGH",
                "confidence": 0.93,
                "started_at": now - datetime.timedelta(hours=4),
                "updated_at": now - datetime.timedelta(hours=4, minutes=-2),
                "acknowledged_at": now - datetime.timedelta(hours=4, minutes=-1),
                "resolved_at": None,
                "status": "ACKNOWLEDGED",
                "distance_m": 2.2,
                "exposure_seconds": 5.8,
                "description": "Worker #05 crossed into chemical storage containment apron.",
                "rule_triggered": "Restricted Zone Breach: Worker foot contact inside Chemical Apron",
                "recommended_action": "Direct worker to evacuate restricted danger perimeter immediately.",
                "is_demo": True
            },
            {
                "id": "EVT-20260825-0002",
                "camera_id": "CAM_01",
                "worker_id": 7,
                "hazard_types": ["RESTRICTED_ZONE", "UNSAFE_PROXIMITY_CRITICAL", "NO_HELMET"],
                "primary_hazard": "UNSAFE_PROXIMITY_CRITICAL",
                "risk_score": 86,
                "severity": "CRITICAL",
                "confidence": 0.96,
                "started_at": now - datetime.timedelta(minutes=12),
                "updated_at": now - datetime.timedelta(minutes=2),
                "acknowledged_at": None,
                "resolved_at": None,
                "status": "ALERTING",
                "distance_m": 1.1,
                "exposure_seconds": 8.4,
                "description": "Worker #07 inside Press Danger Zone at 1.1m machine distance without hardhat.",
                "rule_triggered": "Critical Compound Hazard: Missing Helmet + Zone Breach + 1.1m Machine Distance",
                "recommended_action": "Emergency intervene: Halt active machinery and move worker back.",
                "is_demo": True
            }
        ]

        for evdata in historical_events:
            existing = await db.get(SafetyEvent, evdata["id"])
            if not existing:
                ev = SafetyEvent(**evdata)
                db.add(ev)
                audit = AuditLog(
                    event_id=ev.id,
                    action="DETECTED",
                    actor="SYSTEM",
                    timestamp=ev.started_at,
                    metadata_json={"risk_score": ev.risk_score, "severity": ev.severity}
                )
                db.add(audit)

        await db.commit()
        print("Database seeded with sample cameras, zones, machines, and historical events successfully!")

if __name__ == "__main__":
    asyncio.run(seed_database())
