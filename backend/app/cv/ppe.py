import time
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass
import numpy as np


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


class PPEEngine:
    """
    PPE Compliance & Verification Engine.
    Detects hardhat/helmet and safety vest status with temporal confirmation debounce.
    """
    def __init__(self, persistence_threshold_sec: float = 1.0):
        self.persistence_threshold_sec = persistence_threshold_sec
        # worker_id -> {'first_violation_time': float, 'last_seen': float, 'missing': list}
        self.violation_history: Dict[int, Dict] = {}

    def analyze_worker(
        self,
        worker_id: int,
        head_crop: Optional[np.ndarray],
        torso_crop: Optional[np.ndarray],
        explicit_helmet: Optional[bool] = None,
        explicit_vest: Optional[bool] = None,
        timestamp: Optional[float] = None
    ) -> PPEStatus:
        now = timestamp or time.time()
        
        # Determine helmet status
        if explicit_helmet is not None:
            has_helmet = explicit_helmet
            helmet_conf = 0.92
        elif head_crop is not None and head_crop.size > 0:
            # Color/brightness heuristic for hardhats (yellow, white, orange bright hue)
            hsv = None
            try:
                import cv2
                hsv = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
                # Hardhat color ranges (yellow/orange/white)
                mask1 = cv2.inRange(hsv, np.array([15, 80, 80]), np.array([35, 255, 255]))
                mask2 = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 40, 255]))
                ratio = (np.count_nonzero(mask1) + np.count_nonzero(mask2)) / float(head_crop.shape[0] * head_crop.shape[1])
                has_helmet = ratio > 0.15
                helmet_conf = min(0.95, 0.60 + ratio)
            except Exception:
                has_helmet = True
                helmet_conf = 0.80
        else:
            has_helmet = True
            helmet_conf = 0.75

        # Determine vest status
        if explicit_vest is not None:
            has_vest = explicit_vest
            vest_conf = 0.90
        elif torso_crop is not None and torso_crop.size > 0:
            try:
                import cv2
                hsv = cv2.cvtColor(torso_crop, cv2.COLOR_BGR2HSV)
                # High-vis vest ranges (neon green / bright orange)
                mask = cv2.inRange(hsv, np.array([25, 100, 100]), np.array([85, 255, 255]))
                ratio = np.count_nonzero(mask) / float(torso_crop.shape[0] * torso_crop.shape[1])
                has_vest = ratio > 0.18
                vest_conf = min(0.95, 0.60 + ratio)
            except Exception:
                has_vest = True
                vest_conf = 0.80
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
            persisted_seconds=round(persisted_time, 1)
        )
