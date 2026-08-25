import pytest
from app.cv.exposure import ExposureTracker


def test_exposure_accumulation_and_escalation():
    tracker = ExposureTracker(
        inactivity_timeout_sec=2.0,
        escalation_intervals=(2.0, 5.0, 8.0)
    )

    # Frame 0: Hazard starts
    rec0 = tracker.update_exposure("CAM_01", 7, "RESTRICTED_ZONE", True, timestamp=100.0)
    assert rec0.is_active is True
    assert rec0.duration_seconds == 0.0
    assert rec0.escalation_level == 0

    # Frame 1: 3 seconds later (>= 2s -> escalation level 1)
    rec1 = tracker.update_exposure("CAM_01", 7, "RESTRICTED_ZONE", True, timestamp=103.0)
    assert rec1.is_active is True
    assert rec1.duration_seconds == 3.0
    assert rec1.escalation_level == 1

    # Frame 2: 9 seconds later (>= 8s -> escalation level 3)
    rec2 = tracker.update_exposure("CAM_01", 7, "RESTRICTED_ZONE", True, timestamp=109.0)
    assert rec2.is_active is True
    assert rec2.duration_seconds == 9.0
    assert rec2.escalation_level == 3

    # Frame 3: Worker exits hazard
    rec3 = tracker.update_exposure("CAM_01", 7, "RESTRICTED_ZONE", False, timestamp=112.0)
    assert rec3.is_active is False
