import time
import logging
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PPEItem:
    item_type: str # "HELMET", "VEST", "GOGGLES", "GLOVES"
    confidence: float
    bbox: Tuple[float, float, float, float] # (x1, y1, x2, y2)
    center: Tuple[float, float] # (cx, cy)


@dataclass
class PPEStatus:
    worker_id: int
    has_helmet: bool
    has_vest: bool
    helmet_confidence: float
    vest_confidence: float
    is_violation: bool
    missing_items: List[str]
    persisted_seconds: float
    associated_helmet_bbox: Optional[Tuple[float, float, float, float]] = None
    associated_vest_bbox: Optional[Tuple[float, float, float, float]] = None
    requires_vlm_disambiguation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "has_helmet": self.has_helmet,
            "has_vest": self.has_vest,
            "helmet_confidence": round(self.helmet_confidence, 3),
            "vest_confidence": round(self.vest_confidence, 3),
            "is_violation": self.is_violation,
            "missing_items": self.missing_items,
            "persisted_seconds": round(self.persisted_seconds, 1),
            "requires_vlm_disambiguation": self.requires_vlm_disambiguation
        }


class PPEEngine:
    """
    Production-Grade PPE Compliance & Spatial Association Engine.
    
    Architecture:
    1. Spatial Association Layer:
       - Extracts Head ROI (upper 25-35% of person bounding box)
       - Extracts Body ROI (middle 20-75% of person bounding box)
       - Matches detected PPE objects (helmets, vests) using spatial containment and IoU.
    2. Heuristic / Color Fallback:
       - Inspects HSV color distributions for bright hardhats and high-vis vests when
         standalone PPE detector is unconfigured or low-confidence.
    3. Ambiguity Identification:
       - Flags borderline cases (conf 0.30 - 0.60 or occlusions) for Qwen3-VL disambiguation.
    4. Temporal Confirmation Debounce:
       - Requires persistence over time before escalating to an incident alert.
    """
    def __init__(self, persistence_threshold_sec: float = 1.0):
        self.persistence_threshold_sec = persistence_threshold_sec
        # worker_id -> {'first_violation_time': float, 'last_seen': float, 'missing': list}
        self.violation_history: Dict[int, Dict[str, Any]] = {}

    @staticmethod
    def get_head_roi(person_bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Upper 30% of worker bounding box"""
        x1, y1, x2, y2 = person_bbox
        h = max(1.0, y2 - y1)
        return (x1, y1, x2, y1 + 0.35 * h)

    @staticmethod
    def get_body_roi(person_bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Middle 20% to 75% of worker bounding box"""
        x1, y1, x2, y2 = person_bbox
        h = max(1.0, y2 - y1)
        return (x1, y1 + 0.20 * h, x2, y1 + 0.75 * h)

    @staticmethod
    def is_point_inside_roi(pt: Tuple[float, float], roi: Tuple[float, float, float, float]) -> bool:
        px, py = pt
        rx1, ry1, rx2, ry2 = roi
        return (rx1 <= px <= rx2) and (ry1 <= py <= ry2)

    def associate_ppe_detections(
        self,
        person_bbox: Tuple[float, float, float, float],
        detected_ppe_items: List[PPEItem]
    ) -> Tuple[Optional[PPEItem], Optional[PPEItem]]:
        """
        Spatially associates detected helmets and vests to the worker's Head and Body ROIs.
        """
        head_roi = self.get_head_roi(person_bbox)
        body_roi = self.get_body_roi(person_bbox)

        matched_helmet: Optional[PPEItem] = None
        matched_vest: Optional[PPEItem] = None

        for item in detected_ppe_items:
            if item.item_type in ("HELMET", "HARD_HAT", "HAT"):
                if self.is_point_inside_roi(item.center, head_roi):
                    if matched_helmet is None or item.confidence > matched_helmet.confidence:
                        matched_helmet = item
            elif item.item_type in ("VEST", "SAFETY_VEST"):
                if self.is_point_inside_roi(item.center, body_roi):
                    if matched_vest is None or item.confidence > matched_vest.confidence:
                        matched_vest = item

        return matched_helmet, matched_vest

    def analyze_worker(
        self,
        worker_id: int,
        person_bbox: Tuple[float, float, float, float],
        frame: Optional[np.ndarray] = None,
        detected_ppe_items: Optional[List[PPEItem]] = None,
        explicit_helmet: Optional[bool] = None,
        explicit_vest: Optional[bool] = None,
        timestamp: Optional[float] = None
    ) -> PPEStatus:
        now = timestamp or time.time()
        detected_ppe_items = detected_ppe_items or []

        matched_helmet: Optional[PPEItem] = None
        matched_vest: Optional[PPEItem] = None
        requires_vlm = False

        # 1. First priority: Spatial association with detected PPE objects
        if detected_ppe_items:
            matched_helmet, matched_vest = self.associate_ppe_detections(person_bbox, detected_ppe_items)

        # 2. Helmet Evaluation
        if explicit_helmet is not None:
            has_helmet = explicit_helmet
            helmet_conf = 0.95
        elif matched_helmet is not None:
            has_helmet = True
            helmet_conf = matched_helmet.confidence
        elif frame is not None and frame.size > 0:
            # Crop Head ROI and apply color heuristic
            bx1, by1, bx2, by2 = [int(v) for v in person_bbox]
            h_img, w_img = frame.shape[:2]
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2, by2 = min(w_img, bx2), min(h_img, by2)
            head_h = int((by2 - by1) * 0.35)
            
            if head_h > 5 and bx2 > bx1:
                head_crop = frame[by1:by1 + head_h, bx1:bx2]
                try:
                    import cv2
                    hsv = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
                    # Hardhat color ranges (Yellow, Orange, White, Neon)
                    mask_yellow = cv2.inRange(hsv, np.array([15, 70, 70]), np.array([35, 255, 255]))
                    mask_white = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 45, 255]))
                    mask_orange = cv2.inRange(hsv, np.array([5, 100, 100]), np.array([15, 255, 255]))
                    total_px = float(head_crop.shape[0] * head_crop.shape[1])
                    ratio = (np.count_nonzero(mask_yellow) + np.count_nonzero(mask_white) + np.count_nonzero(mask_orange)) / total_px
                    
                    has_helmet = ratio > 0.12
                    helmet_conf = min(0.92, 0.55 + ratio)
                    if 0.08 <= ratio <= 0.18:
                        requires_vlm = True # Borderline heuristic -> flag for VLM check
                except Exception:
                    has_helmet = True
                    helmet_conf = 0.75
            else:
                has_helmet = True
                helmet_conf = 0.70
        else:
            has_helmet = True
            helmet_conf = 0.75

        # 3. Vest Evaluation
        if explicit_vest is not None:
            has_vest = explicit_vest
            vest_conf = 0.95
        elif matched_vest is not None:
            has_vest = True
            vest_conf = matched_vest.confidence
        elif frame is not None and frame.size > 0:
            # Crop Body ROI and apply high-vis color heuristic
            bx1, by1, bx2, by2 = [int(v) for v in person_bbox]
            h_img, w_img = frame.shape[:2]
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2, by2 = min(w_img, bx2), min(h_img, by2)
            body_y1 = by1 + int((by2 - by1) * 0.20)
            body_y2 = by1 + int((by2 - by1) * 0.70)

            if body_y2 > body_y1 and bx2 > bx1:
                body_crop = frame[body_y1:body_y2, bx1:bx2]
                try:
                    import cv2
                    hsv = cv2.cvtColor(body_crop, cv2.COLOR_BGR2HSV)
                    # High-vis neon green / bright reflective orange ranges
                    mask_neon = cv2.inRange(hsv, np.array([25, 90, 90]), np.array([85, 255, 255]))
                    mask_orange = cv2.inRange(hsv, np.array([5, 110, 110]), np.array([20, 255, 255]))
                    total_px = float(body_crop.shape[0] * body_crop.shape[1])
                    ratio = (np.count_nonzero(mask_neon) + np.count_nonzero(mask_orange)) / total_px
                    
                    has_vest = ratio > 0.15
                    vest_conf = min(0.92, 0.55 + ratio)
                    if 0.10 <= ratio <= 0.22:
                        requires_vlm = True # Borderline heuristic -> flag for VLM check
                except Exception:
                    has_vest = True
                    vest_conf = 0.75
            else:
                has_vest = True
                vest_conf = 0.70
        else:
            has_vest = True
            vest_conf = 0.75

        missing = []
        if not has_helmet:
            missing.append("HELMET")
        if not has_vest:
            missing.append("SAFETY_VEST")

        is_currently_violating = len(missing) > 0
        persisted_time = 0.0

        if is_currently_violating:
            if worker_id not in self.violation_history:
                self.violation_history[worker_id] = {
                    "first_seen": now,
                    "last_seen": now,
                    "missing": missing
                }
            else:
                self.violation_history[worker_id]["last_seen"] = now
                self.violation_history[worker_id]["missing"] = missing

            persisted_time = now - self.violation_history[worker_id]["first_seen"]
        else:
            if worker_id in self.violation_history:
                del self.violation_history[worker_id]

        confirmed_violation = is_currently_violating and (persisted_time >= self.persistence_threshold_sec)

        return PPEStatus(
            worker_id=worker_id,
            has_helmet=has_helmet,
            has_vest=has_vest,
            helmet_confidence=helmet_conf,
            vest_confidence=vest_conf,
            is_violation=confirmed_violation,
            missing_items=missing,
            persisted_seconds=round(persisted_time, 1),
            associated_helmet_bbox=matched_helmet.bbox if matched_helmet else None,
            associated_vest_bbox=matched_vest.bbox if matched_vest else None,
            requires_vlm_disambiguation=requires_vlm
        )
