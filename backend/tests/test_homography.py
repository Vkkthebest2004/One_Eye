import pytest
from app.cv.homography import HomographyCalibrator


def test_homography_uncalibrated_mode():
    calibrator = HomographyCalibrator(camera_id="CAM_TEST")
    x, y, mode = calibrator.pixel_to_world(200.0, 300.0)
    assert mode == "PIXEL_DISTANCE_MODE"
    assert x is None
    assert y is None

    dist, mode = calibrator.compute_distance_m((100, 100), (200, 100))
    assert mode == "PIXEL_DISTANCE_MODE"
    assert dist > 0.0


def test_homography_calibrated_metric_transform():
    calibrator = HomographyCalibrator(camera_id="CAM_TEST")
    # Standard perspective box mapping to 10m x 8m rectangle
    img_points = [(100.0, 100.0), (500.0, 100.0), (600.0, 500.0), (50.0, 500.0)]
    world_points = [(0.0, 0.0), (10.0, 0.0), (10.0, 8.0), (0.0, 8.0)]

    success = calibrator.calibrate(img_points, world_points)
    assert success is True
    assert calibrator.is_calibrated is True

    # Test transformation of top-left corner
    X, Y, mode = calibrator.pixel_to_world(100.0, 100.0)
    assert mode == "METRIC_MODE"
    assert abs(X - 0.0) < 0.2
    assert abs(Y - 0.0) < 0.2

    # Test metric distance computation
    dist_m, mode = calibrator.compute_distance_m((100.0, 100.0), (500.0, 100.0))
    assert mode == "METRIC_MODE"
    assert abs(dist_m - 10.0) < 0.3
