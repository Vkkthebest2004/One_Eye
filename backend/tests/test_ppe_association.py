import pytest
from app.cv.ppe import PPEEngine, PPEItem, PPEStatus
from app.cv.fall import FallDetector, FallStatus


def test_ppe_spatial_roi_association():
    ppe_engine = PPEEngine(persistence_threshold_sec=0.5)

    # Worker #17 at [100, 100, 200, 300] (width=100, height=200)
    # Head ROI: [100, 100, 200, 170]
    # Body ROI: [100, 140, 200, 250]
    person_bbox = (100.0, 100.0, 200.0, 300.0)

    helmet_item = PPEItem(
        item_type="HELMET",
        confidence=0.94,
        bbox=(120.0, 105.0, 180.0, 145.0),
        center=(150.0, 125.0) # Inside Head ROI
    )

    vest_item = PPEItem(
        item_type="VEST",
        confidence=0.91,
        bbox=(110.0, 150.0, 190.0, 230.0),
        center=(150.0, 190.0) # Inside Body ROI
    )

    matched_helmet, matched_vest = ppe_engine.associate_ppe_detections(
        person_bbox=person_bbox,
        detected_ppe_items=[helmet_item, vest_item]
    )

    assert matched_helmet is not None
    assert matched_helmet.confidence == 0.94
    assert matched_vest is not None
    assert matched_vest.confidence == 0.91

    # Evaluate full worker compliance
    status = ppe_engine.analyze_worker(
        worker_id=17,
        person_bbox=person_bbox,
        detected_ppe_items=[helmet_item, vest_item],
        timestamp=1000.0
    )

    assert status.has_helmet is True
    assert status.has_vest is True
    assert status.is_violation is False
    assert len(status.missing_items) == 0


def test_ppe_spatial_roi_missing_items():
    ppe_engine = PPEEngine(persistence_threshold_sec=1.0)
    person_bbox = (100.0, 100.0, 200.0, 300.0)

    # Distant helmet belonging to someone else
    distant_helmet = PPEItem(
        item_type="HELMET",
        confidence=0.89,
        bbox=(400.0, 400.0, 450.0, 440.0),
        center=(425.0, 420.0) # Far outside worker's Head ROI
    )

    # Initial frame without PPE
    status1 = ppe_engine.analyze_worker(
        worker_id=18,
        person_bbox=person_bbox,
        detected_ppe_items=[distant_helmet],
        explicit_helmet=False,
        explicit_vest=False,
        timestamp=1000.0
    )

    assert status1.has_helmet is False
    assert status1.has_vest is False
    assert status1.is_violation is False # Not yet debounced

    # After 1.5 seconds of persistent violation
    status2 = ppe_engine.analyze_worker(
        worker_id=18,
        person_bbox=person_bbox,
        detected_ppe_items=[distant_helmet],
        explicit_helmet=False,
        explicit_vest=False,
        timestamp=1001.5
    )

    assert status2.is_violation is True # Debounced confirmed violation
    assert "HELMET" in status2.missing_items
    assert "SAFETY_VEST" in status2.missing_items


def test_fall_temporal_progression():
    detector = FallDetector(confirmation_duration_sec=1.5)

    # 1. Standing worker (h=200, w=80 -> aspect ratio 2.5)
    standing_bbox = (100.0, 100.0, 180.0, 300.0)
    status_standing = detector.evaluate_worker(
        worker_id=20,
        bbox=standing_bbox,
        timestamp=1000.0
    )
    assert status_standing.state == "STANDING"
    assert status_standing.is_fall is False

    # 2. Falling transition
    falling_bbox = (100.0, 200.0, 200.0, 300.0)
    status_falling = detector.evaluate_worker(
        worker_id=20,
        bbox=falling_bbox,
        velocity=(0.0, 55.0), # Downward velocity spike
        timestamp=1000.5
    )
    assert status_falling.state == "FALLING"
    assert status_falling.is_fall is False

    # 3. Horizontal on floor (h=50, w=200 -> aspect ratio 0.25)
    fallen_bbox = (100.0, 250.0, 300.0, 300.0)
    status_fallen_initial = detector.evaluate_worker(
        worker_id=20,
        bbox=fallen_bbox,
        timestamp=1001.0
    )
    assert status_fallen_initial.state == "FALLEN"
    assert status_fallen_initial.is_fall is False # Needs 1.5s confirmation

    # 4. Remains horizontal on floor > 1.5s
    status_fall_confirmed = detector.evaluate_worker(
        worker_id=20,
        bbox=fallen_bbox,
        timestamp=1002.8
    )
    assert status_fall_confirmed.state == "FALL_CONFIRMED"
    assert status_fall_confirmed.is_fall is True
