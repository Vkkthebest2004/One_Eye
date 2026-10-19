import pytest
import numpy as np
import time
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.db.database import init_db
from app.cv.retrospective import RollingSequenceBuffer, SequenceReconstructor, RetrospectiveEngine
from app.cv.pipeline import pipeline_manager


def test_rolling_sequence_buffer_and_keyframes():
    buffer = RollingSequenceBuffer(camera_id="TEST_CAM", max_seconds=60.0, sample_fps=10.0)
    fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Push 15 frames over 1.5 simulated seconds
    t0 = time.time() - 20.0
    for i in range(15):
        buffer.append(
            frame=fake_frame,
            tracks=[{
                "track_id": 1,
                "is_worker": True,
                "current_risk_score": 10 + i * 4,
                "has_helmet": True,
                "has_vest": True,
                "has_glasses": True if i < 10 else False,
                "distance_to_machine": 2.0 - (i * 0.1),
                "current_zone_id": "ZONE_DANGER" if i >= 12 else None,
                "is_fallen": False
            }],
            detections=[{"category": "PERSON", "confidence": 0.9}],
            active_hazards=["NO_GLASSES"] if i >= 10 else [],
            max_risk=10 + i * 4
        )
        time.sleep(0.01) # brief tick

    snapshots = buffer.get_snapshots(60.0)
    assert len(snapshots) > 0

    keyframes = buffer.extract_critical_keyframes(seconds=60.0, count=4)
    assert len(keyframes) > 0
    assert all(isinstance(k[1], np.ndarray) for k in keyframes)


def test_sequence_reconstructor_event_timeline():
    buffer = RollingSequenceBuffer(camera_id="TEST_CAM", max_seconds=60.0, sample_fps=10.0)
    fake_frame = np.zeros((360, 640, 3), dtype=np.uint8)

    # 1. First frame: empty
    buffer.append(fake_frame, tracks=[], detections=[], active_hazards=[], max_risk=0)
    time.sleep(0.02)

    # 2. Worker arrives and approaches machine
    buffer.append(
        fake_frame,
        tracks=[{
            "track_id": 1,
            "is_worker": True,
            "current_risk_score": 25,
            "has_helmet": True,
            "has_vest": True,
            "has_glasses": True,
            "distance_to_machine": 1.1,
            "current_zone_id": None,
            "is_fallen": False
        }],
        detections=[{"category": "PERSON", "confidence": 0.9}],
        active_hazards=[],
        max_risk=25
    )
    time.sleep(0.02)

    # 3. Restricted zone entry & hazard
    buffer.append(
        fake_frame,
        tracks=[{
            "track_id": 1,
            "is_worker": True,
            "current_risk_score": 85,
            "has_helmet": True,
            "has_vest": True,
            "has_glasses": False,
            "distance_to_machine": 0.8,
            "current_zone_id": "ZONE_CRITICAL",
            "is_fallen": False
        }],
        detections=[{"category": "PERSON", "confidence": 0.9}],
        active_hazards=["NO_GLASSES", "DANGER_ZONE_REACHED"],
        max_risk=85
    )

    snapshots = buffer.get_snapshots(60.0)
    timeline = SequenceReconstructor.reconstruct(snapshots)

    assert len(timeline) >= 2
    labels = [t["label"] for t in timeline]
    assert any("Arrival" in l or "Checkpoint" in l for l in labels)
    assert all("timestamp_str" in t for t in timeline)
    assert all("description" in t for t in timeline)


@pytest.mark.asyncio
async def test_retrospective_engine_report_generation():
    engine = RetrospectiveEngine()
    buffer = RollingSequenceBuffer(camera_id="CAM_TEST_RETRO", max_seconds=60.0, sample_fps=10.0)
    fake_frame = np.zeros((360, 640, 3), dtype=np.uint8)

    # Seed simulated sequence
    buffer.append(
        fake_frame,
        tracks=[{
            "track_id": 1,
            "is_worker": True,
            "current_risk_score": 75,
            "has_helmet": True,
            "has_vest": False,
            "has_glasses": True,
            "distance_to_machine": 1.2,
            "current_zone_id": "ZONE_DANGER",
            "is_fallen": False
        }],
        detections=[{"category": "PERSON", "confidence": 0.9}],
        active_hazards=["NO_VEST", "DANGER_ZONE_REACHED"],
        max_risk=75
    )

    report = await engine.analyze_sequence(
        camera_id="CAM_TEST_RETRO",
        buffer=buffer,
        domain="EQUIPMENT_OPERATION",
        custom_goal="Analyze loading and machine restart",
        seconds=60.0
    )

    assert "what_happened" in report
    assert "what_went_wrong" in report
    assert "possible_explanation" in report
    assert "recommended_next_steps" in report
    assert isinstance(report["recommended_next_steps"], list)
    assert len(report["recommended_next_steps"]) > 0
    assert "evidence_timeline" in report


@pytest.mark.asyncio
async def test_retrospective_api_endpoints():
    await init_db()
    # Register test camera pipeline
    cam_id = "CAM_RETRO_API"
    pipe = pipeline_manager.register_camera(cam_id, "0")

    # Feed at least one frame into sequence_buffer
    fake_frame = np.zeros((360, 640, 3), dtype=np.uint8)
    pipe.sequence_buffer.append(
        fake_frame,
        tracks=[{"track_id": 2, "is_worker": True, "current_risk_score": 40}],
        detections=[],
        active_hazards=[],
        max_risk=40
    )

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Timeline endpoint
        tl_res = await ac.get(f"/api/retrospective/{cam_id}/timeline?seconds=60")
        assert tl_res.status_code == 200
        tl_data = tl_res.json()
        assert "timeline" in tl_data
        assert tl_data["camera_id"] == cam_id

        # 2. Analyze endpoint
        analyze_res = await ac.post(
            f"/api/retrospective/{cam_id}/analyze",
            json={
                "domain": "INDUSTRIAL_SOP",
                "custom_goal": "Check PPE compliance before machine approach",
                "seconds": 60.0
            }
        )
        assert analyze_res.status_code == 200
        an_data = analyze_res.json()
        assert "what_happened" in an_data
        assert "what_went_wrong" in an_data
        assert "possible_explanation" in an_data
        assert "recommended_next_steps" in an_data
        assert "evidence_timeline" in an_data
        report_id = an_data["id"]

        # 3. Retrieve reports list
        reports_res = await ac.get("/api/retrospective/reports")
        assert reports_res.status_code == 200
        assert reports_res.json()["total"] >= 1

        # 4. Retrieve single report by ID
        single_res = await ac.get(f"/api/retrospective/reports/{report_id}")
        assert single_res.status_code == 200
        assert single_res.json()["id"] == report_id
