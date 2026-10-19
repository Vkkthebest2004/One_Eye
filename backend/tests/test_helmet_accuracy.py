import pytest
import numpy as np
from app.cv.detector import Detector, Detection
from app.cv.ppe import PPEEngine, PPEItem, PPEStatus


def test_categorize_class_helmet_mappings():
    detector = Detector(model_path="yolov8n.pt", device="cpu")

    # Critical regression check: class_id 0 in PPE models must NOT be converted to PERSON
    assert detector._categorize_class("Hardhat", 0) == "PPE_HELMET"
    assert detector._categorize_class("helmet", 0) == "PPE_HELMET"
    assert detector._categorize_class("hardhat", 0) == "PPE_HELMET"
    assert detector._categorize_class("safety_helmet", 0) == "PPE_HELMET"

    # Negative helmet detections
    assert detector._categorize_class("NO-Hardhat", 1) == "NO_HELMET"
    assert detector._categorize_class("no_helmet", 7) == "NO_HELMET"
    assert detector._categorize_class("no-helmet", 7) == "NO_HELMET"
    assert detector._categorize_class("no_hardhat", 1) == "NO_HELMET"

    # Person mappings
    assert detector._categorize_class("person", 0) == "PERSON"
    assert detector._categorize_class("worker", 0) == "PERSON"

    # Ordinary hats (baseball caps/beanies) must NOT qualify as safety helmets
    assert detector._categorize_class("hat", 10) == "OBJECT"


def test_indoor_wall_does_not_falsely_trigger_helmet():
    """
    Ensure a person in front of a white wall or indoor lighting
    does not get falsely flagged as wearing a helmet.
    """
    engine = PPEEngine(persistence_threshold_sec=0.5)
    person_bbox = (100.0, 100.0, 300.0, 500.0)

    # Synthetic frame simulating light-colored indoor room (white/beige background + skin)
    frame = np.full((600, 600, 3), 220, dtype=np.uint8) # light gray / white wall

    status = engine.analyze_worker(
        worker_id=1,
        person_bbox=person_bbox,
        frame=frame,
        detected_ppe_items=[],
        timestamp=1000.0
    )

    # Must accurately report NO helmet
    assert status.has_helmet is False
    assert "HELMET" in status.missing_items


def test_no_hardhat_detection_triggers_violation():
    """
    When hardhat model explicitly detects NO-Hardhat, violation must be confirmed.
    """
    engine = PPEEngine(persistence_threshold_sec=1.0)
    person_bbox = (150.0, 100.0, 350.0, 500.0)

    no_helmet_item = PPEItem(
        item_type="NO_HELMET",
        confidence=0.78,
        bbox=(200.0, 120.0, 300.0, 220.0),
        center=(250.0, 170.0)
    )

    # Initial frame
    st1 = engine.analyze_worker(
        worker_id=2,
        person_bbox=person_bbox,
        detected_ppe_items=[no_helmet_item],
        timestamp=1000.0
    )
    assert st1.has_helmet is False
    assert st1.is_violation is False # waiting for persistence debounce

    # After 1.2s persistence
    st2 = engine.analyze_worker(
        worker_id=2,
        person_bbox=person_bbox,
        detected_ppe_items=[no_helmet_item],
        timestamp=1001.2
    )
    assert st2.has_helmet is False
    assert st2.is_violation is True
    assert "HELMET" in st2.missing_items


def test_positive_hardhat_detection_complies():
    engine = PPEEngine(persistence_threshold_sec=0.5)
    person_bbox = (150.0, 100.0, 350.0, 500.0)

    helmet_item = PPEItem(
        item_type="PPE_HELMET",
        confidence=0.88,
        bbox=(200.0, 100.0, 300.0, 180.0),
        center=(250.0, 140.0)
    )

    st = engine.analyze_worker(
        worker_id=3,
        person_bbox=person_bbox,
        detected_ppe_items=[helmet_item],
        timestamp=1000.0
    )
    assert st.has_helmet is True
    assert "HELMET" not in st.missing_items
