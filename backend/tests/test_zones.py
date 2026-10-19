import pytest
from app.cv.zones import ZoneEngine, ZoneDefinition


def test_zone_point_in_polygon():
    engine = ZoneEngine()
    zone = ZoneDefinition(
        id="zone_01",
        name="Test Danger Zone",
        camera_id="CAM_01",
        polygon_points=[(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)],
        severity=80
    )
    engine.register_zone(zone)

    # Point clearly inside
    assert zone.contains_point(200.0, 200.0) is True

    # Point clearly outside
    assert zone.contains_point(50.0, 50.0) is False
    assert zone.contains_point(350.0, 200.0) is False


def test_zone_foot_anchor_state_transitions():
    engine = ZoneEngine()
    zone = ZoneDefinition(
        id="zone_press",
        name="Press Machine Danger Zone",
        camera_id="CAM_01",
        polygon_points=[(100.0, 100.0), (400.0, 100.0), (400.0, 400.0), (100.0, 400.0)],
        severity=85
    )
    engine.register_zone(zone)

    # Step 1: Worker enters
    events_t0 = engine.evaluate_worker(
        worker_id=7,
        foot_x=250.0,
        foot_y=250.0,
        timestamp=100.0,
        camera_id="CAM_01"
    )
    assert len(events_t0) == 1
    assert events_t0[0].state == "ENTERED"
    assert events_t0[0].worker_id == 7

    # Step 2: Worker remains inside
    events_t1 = engine.evaluate_worker(
        worker_id=7,
        foot_x=260.0,
        foot_y=270.0,
        timestamp=104.5,
        camera_id="CAM_01"
    )
    assert len(events_t1) == 1
    assert events_t1[0].state == "INSIDE"
    assert events_t1[0].inside_duration_sec == 4.5

    # Step 3: Worker exits zone
    events_t2 = engine.evaluate_worker(
        worker_id=7,
        foot_x=50.0,
        foot_y=50.0,
        timestamp=108.0,
        camera_id="CAM_01"
    )
    assert len(events_t2) == 1
    assert events_t2[0].state == "EXITED"
    assert events_t2[0].inside_duration_sec == 8.0


def test_zone_load_from_config():
    engine = ZoneEngine()
    config = {
        "image": "reference.jpg",
        "image_size": [1920, 1080],
        "polygon": [[192, 108], [960, 108], [960, 540], [192, 540]],
    }
    zone = engine.load_from_config(config, camera_id="CAM_01", zone_name="CNC Restricted")
    assert zone is not None
    assert zone.name == "CNC Restricted"
    assert zone.camera_id == "CAM_01"
    # Check normalization
    assert len(zone.polygon_points) == 4
    assert pytest.approx(zone.polygon_points[0][0], 0.01) == 0.1
    assert pytest.approx(zone.polygon_points[0][1], 0.01) == 0.1
    assert pytest.approx(zone.polygon_points[1][0], 0.01) == 0.5
    assert pytest.approx(zone.polygon_points[2][1], 0.01) == 0.5


def test_intrusion_polygon_scaling_and_point_test():
    import numpy as np
    from app.cv.intrusion import scale_polygon, point_in_zone

    # Normalized polygon
    poly = [(0.2, 0.2), (0.8, 0.2), (0.8, 0.8), (0.2, 0.8)]
    scaled = scale_polygon(poly, (1000, 1000))
    assert scaled.shape == (4, 2)
    assert scaled[0][0] == 200
    assert scaled[0][1] == 200

    # Inside
    assert point_in_zone((500, 500), scaled) is True
    # Outside
    assert point_in_zone((100, 100), scaled) is False
    assert point_in_zone((900, 500), scaled) is False
