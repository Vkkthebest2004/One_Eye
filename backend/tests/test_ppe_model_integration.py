import pytest
import numpy as np
from app.cv.detector import Detector, Detection
from app.cv.ppe import PPEEngine, PPEItem


def test_detector_with_ppe_model_initialization():
    detector = Detector(
        model_path="yolov8n.pt",
        ppe_model_path="models/ppe_yolov8n.pt",
        device="cpu"
    )
    assert detector.is_loaded is True
    assert detector.ppe_model is not None


def test_ppe_engine_explicit_negative_detection():
    engine = PPEEngine()
    person_bbox = (100, 100, 200, 400) # Head ROI is (100, 100, 200, 205)

    # Detected 'no_helmet' inside head ROI
    no_helmet_item = PPEItem(
        item_type="NO_HELMET",
        confidence=0.91,
        bbox=(120, 110, 180, 160),
        center=(150, 135)
    )

    status = engine.analyze_worker(
        worker_id=1,
        person_bbox=person_bbox,
        detected_ppe_items=[no_helmet_item]
    )

    assert status.has_helmet is False
    assert status.helmet_confidence == 0.91
    assert "HELMET" in status.missing_items
    assert len(status.missing_items) > 0


def test_ppe_engine_positive_helmet_detection():
    engine = PPEEngine()
    person_bbox = (100, 100, 200, 400)

    helmet_item = PPEItem(
        item_type="PPE_HELMET",
        confidence=0.94,
        bbox=(120, 105, 180, 155),
        center=(150, 130)
    )

    status = engine.analyze_worker(
        worker_id=2,
        person_bbox=person_bbox,
        detected_ppe_items=[helmet_item]
    )

    assert status.has_helmet is True
    assert status.helmet_confidence == 0.94
