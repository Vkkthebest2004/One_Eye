import pytest
from app.cv.proximity import ProximityEngine, MachineDefinition
from app.cv.homography import HomographyCalibrator


def test_proximity_engine_evaluation():
    engine = ProximityEngine()
    machine = MachineDefinition(
        id="press_01",
        name="Hydraulic Press",
        camera_id="CAM_01",
        bbox=(200.0, 200.0, 400.0, 400.0),
        center=(300.0, 300.0),
        danger_radius_m=1.5,
        critical_radius_m=0.8,
        warning_radius_m=2.5
    )
    engine.register_machine(machine)

    calibrator = HomographyCalibrator("CAM_01")
    calibrator.calibrate(
        [(0.0, 0.0), (1000.0, 0.0), (1000.0, 1000.0), (0.0, 1000.0)],
        [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    )

    # Worker very close (Critical)
    res_crit = engine.evaluate_worker(
        worker_id=7,
        foot_anchor=(300.0, 430.0), # ~0.3m away in world
        camera_id="CAM_01",
        calibrator=calibrator
    )
    assert len(res_crit) == 1
    assert res_crit[0].proximity_level in ("CRITICAL", "DANGER")
    assert res_crit[0].is_unsafe is True

    # Worker far away (Safe)
    res_safe = engine.evaluate_worker(
        worker_id=7,
        foot_anchor=(900.0, 900.0),
        camera_id="CAM_01",
        calibrator=calibrator
    )
    assert len(res_safe) == 1
    assert res_safe[0].proximity_level == "SAFE"
    assert res_safe[0].is_unsafe is False
