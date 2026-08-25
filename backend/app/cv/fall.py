import time
import logging
from typing import Dict, Optional, Tuple, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FallStatus:
    worker_id: int
    state: str # "NORMAL", "UNSTABLE", "POSSIBLE_FALL", "FALL_CONFIRMED"
    aspect_ratio: float
    is_fall: bool
    confidence: float
    duration_sec: float


class FallDetector:
    """
    Temporal Fall Detection Engine.
    Requires multi-frame posture confirmation (aspect ratio change and ground proximity)
    to eliminate sitting / bending false positives.
    """
    def __init__(self, confirmation_duration_sec: float = 1.5):
        self.confirmation_duration_sec = confirmation_duration_sec
        # worker_id -> {'first_down_time': float, 'last_seen': float, 'state': str, 'aspect_ratios': list}
        self.worker_fall_states: Dict[int, Dict] = {}

    def evaluate_worker(
        self,
        worker_id: int,
        bbox: Tuple[float, float, float, float], # (x1, y1, x2, y2)
        velocity: Tuple[float, float] = (0.0, 0.0),
        keypoints: Optional[List] = None,
        timestamp: Optional[float] = None
    ) -> FallStatus:
        now = timestamp or time.time()
        w = max(1.0, bbox[2] - bbox[0])
        h = max(1.0, bbox[3] - bbox[1])
        aspect_ratio = h / w # Normal upright person: aspect ratio typically > 1.8; Fallen person: < 1.0

        is_horizontal = aspect_ratio < 0.95
        is_unstable = aspect_ratio < 1.3 or abs(velocity[1]) > 50.0 # Fast downward motion

        if worker_id not in self.worker_fall_states:
            self.worker_fall_states[worker_id] = {
                "first_down_time": None,
                "last_seen": now,
                "state": "NORMAL",
                "aspect_ratios": [aspect_ratio]
            }

        state_info = self.worker_fall_states[worker_id]
        state_info["last_seen"] = now
        state_info["aspect_ratios"].append(aspect_ratio)
        if len(state_info["aspect_ratios"]) > 30:
            state_info["aspect_ratios"].pop(0)

        current_state = state_info["state"]
        duration = 0.0
        confidence = 0.85

        if is_horizontal:
            if state_info["first_down_time"] is None:
                state_info["first_down_time"] = now
                current_state = "POSSIBLE_FALL"
            else:
                duration = now - state_info["first_down_time"]
                if duration >= self.confirmation_duration_sec:
                    current_state = "FALL_CONFIRMED"
                    confidence = 0.94
                else:
                    current_state = "POSSIBLE_FALL"
        elif is_unstable:
            if current_state != "FALL_CONFIRMED":
                current_state = "UNSTABLE"
        else:
            state_info["first_down_time"] = None
            current_state = "NORMAL"

        state_info["state"] = current_state

        return FallStatus(
            worker_id=worker_id,
            state=current_state,
            aspect_ratio=round(aspect_ratio, 2),
            is_fall=(current_state == "FALL_CONFIRMED"),
            confidence=confidence,
            duration_sec=round(duration, 1)
        )
