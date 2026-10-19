import pytest
import cv2
import numpy as np
from app.cv.detector import Detector, Detection
from app.cv.tracker import Track
from app.cv.ppe import PPEEngine, PPEItem, PPEStatus


def test_categorize_class_glasses_mappings():
    detector = Detector(model_path="yolov8n.pt", device="cpu")

    # Positive safety glasses / goggles mappings
    assert detector._categorize_class("goggles", 4) == "PPE_GLASSES"
    assert detector._categorize_class("goggle", 4) == "PPE_GLASSES"
    assert detector._categorize_class("safety_glasses", 4) == "PPE_GLASSES"
    assert detector._categorize_class("safety_goggles", 4) == "PPE_GLASSES"
    assert detector._categorize_class("glasses", 4) == "PPE_GLASSES"
    assert detector._categorize_class("eye_protection", 4) == "PPE_GLASSES"

    # Negative glasses mappings
    assert detector._categorize_class("no_goggle", 8) == "NO_GLASSES"
    assert detector._categorize_class("no_goggles", 8) == "NO_GLASSES"
    assert detector._categorize_class("no-goggle", 8) == "NO_GLASSES"
    assert detector._categorize_class("no-goggles", 8) == "NO_GLASSES"
    assert detector._categorize_class("no_glasses", 8) == "NO_GLASSES"
    assert detector._categorize_class("no-glasses", 8) == "NO_GLASSES"


def test_detection_eye_roi_property():
    d = Detection(
        class_id=0,
        class_name="person",
        category="PERSON",
        confidence=0.92,
        x1=100.0,
        y1=100.0,
        x2=200.0,
        y2=300.0,
        center_x=150.0,
        center_y=200.0,
        foot_x=150.0,
        foot_y=300.0
    )
    # bbox width=100, height=200
    # eye_roi: (x1, y1 + h*0.10, x2, y1 + h*0.32)
    assert d.eye_roi == (100.0, 120.0, 200.0, 164.0)


def test_facial_glasses_bare_face_negative():
    """Ensure a bare face with normal skin tone is not falsely flagged as wearing glasses."""
    engine = PPEEngine(persistence_threshold_sec=0.5)
    person_bbox = (100.0, 100.0, 300.0, 500.0)

    # Frame with smooth skin tone face
    frame = np.full((600, 600, 3), 160, dtype=np.uint8)
    # Paint face area with smooth skin tone (no high gradient frames)
    cv2.rectangle(frame, (120, 120), (280, 300), (140, 170, 210), -1)

    has_glasses, conf = engine.analyze_facial_glasses(frame, person_bbox)
    assert has_glasses == False
    assert conf >= 0.50


def test_facial_glasses_with_frames_positive():
    """Ensure a face with prominent glasses frames and bridge is recognized as wearing glasses."""
    engine = PPEEngine(persistence_threshold_sec=0.5)
    person_bbox = (100.0, 100.0, 300.0, 500.0)

    # Frame with face and high-contrast dark eyeglasses
    frame = np.full((600, 600, 3), 160, dtype=np.uint8)
    # Paint face area
    cv2.rectangle(frame, (120, 120), (280, 300), (140, 170, 210), -1)

    # Calculate eye region coordinates
    # Eye ROI: y1 = 100 + 400*0.12 = 148, y2 = 100 + 400*0.35 = 240
    # x1 = 100 + 200*0.10 = 120, x2 = 100 + 200*0.90 = 280
    # Draw left and right lens rims with dark borders
    cv2.rectangle(frame, (135, 170), (185, 210), (10, 10, 10), 3)
    cv2.rectangle(frame, (215, 170), (265, 210), (10, 10, 10), 3)
    # Draw dark bridge connecting the frames across the nasal region
    cv2.line(frame, (185, 185), (215, 185), (10, 10, 10), 4)

    has_glasses, conf = engine.analyze_facial_glasses(frame, person_bbox)
    assert has_glasses == True
    assert conf >= 0.70


def test_ppe_glasses_spatial_association():
    """Test associating detected goggles/safety glasses with a worker."""
    engine = PPEEngine(persistence_threshold_sec=0.5)
    person_bbox = (100.0, 100.0, 300.0, 500.0)

    goggles_item = PPEItem(
        item_type="GOGGLES",
        confidence=0.92,
        bbox=(150.0, 160.0, 250.0, 210.0),
        center=(200.0, 185.0)
    )

    res = engine.associate_ppe_detections(person_bbox, [goggles_item])
    assert res.matched_glasses is not None
    assert res.matched_glasses.confidence == 0.92

    status = engine.analyze_worker(
        worker_id=10,
        person_bbox=person_bbox,
        detected_ppe_items=[goggles_item],
        timestamp=1000.0
    )
    assert status.has_glasses is True
    assert status.glasses_confidence >= 0.80


def test_no_glasses_hazard_when_required():
    """Test that when require_glasses is enabled, missing glasses triggers violation after debounce."""
    engine = PPEEngine(persistence_threshold_sec=0.8)
    person_bbox = (100.0, 100.0, 300.0, 500.0)

    no_glasses_item = PPEItem(
        item_type="NO_GLASSES",
        confidence=0.85,
        bbox=(150.0, 160.0, 250.0, 210.0),
        center=(200.0, 185.0)
    )

    # Initial frame
    st1 = engine.analyze_worker(
        worker_id=11,
        person_bbox=person_bbox,
        detected_ppe_items=[no_glasses_item],
        explicit_helmet=True,
        explicit_vest=True,
        require_glasses=True,
        timestamp=1000.0
    )
    assert st1.has_glasses is False
    assert st1.is_violation is False # Debounce in progress

    # After persistence threshold
    st2 = engine.analyze_worker(
        worker_id=11,
        person_bbox=person_bbox,
        detected_ppe_items=[no_glasses_item],
        explicit_helmet=True,
        explicit_vest=True,
        require_glasses=True,
        timestamp=1001.0
    )
    assert st2.has_glasses is False
    assert st2.is_violation is True
    assert "SAFETY_GLASSES" in st2.missing_items


def test_tracked_target_glasses_serialization():
    """Test that Track accurately stores and serializes glasses state."""
    target = Track(
        track_id=42,
        class_name="person",
        category="PERSON",
        bbox=(100.0, 100.0, 300.0, 500.0),
        foot_anchor=(200.0, 500.0),
        center=(200.0, 300.0),
        confidence=0.95,
        first_seen=1000.0,
        last_seen=1000.0
    )
    target.has_glasses = True
    target.glasses_confidence = 0.88

    data = target.to_dict()
    assert data["has_glasses"] is True
    assert data["glasses_confidence"] == 0.88
