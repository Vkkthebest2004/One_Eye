import time
import math
import logging
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class FallStatus:
    worker_id: int
    state: str # "STANDING", "FALLING", "FALLEN", "FALL_CONFIRMED"
    aspect_ratio: float
    is_fall: bool
    confidence: float
    duration_sec: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "state": self.state,
            "aspect_ratio": round(self.aspect_ratio, 2),
            "is_fall": self.is_fall,
            "confidence": round(self.confidence, 3),
            "duration_sec": round(self.duration_sec, 1)
        }


class FallDetector:
    """
    Temporal Pose & Fall Confirmation Engine.
    
    Progression:
    1. STANDING: Normal upright human posture (aspect ratio h/w > 1.4 or vertical torso).
    2. FALLING: Rapid downward velocity or sudden posture transition.
    3. FALLEN: Horizontal orientation on ground plane (aspect ratio < 0.7 or horizontal spine).
    4. FALL_CONFIRMED: Remains horizontal on floor for >= confirmation_duration_sec.
       Eliminates sitting, stooping, bending, or camera tilt false positives using
       torso vector angle validation whenever pose keypoints are present.
    """
    def __init__(self, confirmation_duration_sec: float = 3.5):
        self.confirmation_duration_sec = confirmation_duration_sec
        # worker_id -> {'first_down_time': float, 'last_seen': float, 'state': str, 'aspect_ratios': list}
        self.worker_fall_states: Dict[int, Dict[str, Any]] = {}

    def evaluate_worker(
        self,
        worker_id: int,
        bbox: Tuple[float, float, float, float], # (x1, y1, x2, y2)
        velocity: Tuple[float, float] = (0.0, 0.0),
        keypoints: Optional[List[List[float]]] = None,
        timestamp: Optional[float] = None
    ) -> FallStatus:
        now = timestamp or time.time()
        w = max(1.0, bbox[2] - bbox[0])
        h = max(1.0, bbox[3] - bbox[1])
        aspect_ratio = h / w # Upright person: h/w > 1.5; Fallen person: h/w < 0.9

        # Keypoint-based posture verification (using COCO 17 keypoints from YOLOv8-pose)
        has_valid_pose = False
        torso_angle_deg = None
        is_crouching_or_sitting = False

        if keypoints and len(keypoints) >= 13:
            ls, rs = keypoints[5], keypoints[6]
            lh, rh = keypoints[11], keypoints[12]
            s_conf = min(ls[2], rs[2]) if len(ls) > 2 and len(rs) > 2 else 1.0
            h_conf = min(lh[2], rh[2]) if len(lh) > 2 and len(rh) > 2 else 1.0

            if s_conf > 0.25 and h_conf > 0.25:
                mid_shoulder_x = (ls[0] + rs[0]) / 2.0
                mid_shoulder_y = (ls[1] + rs[1]) / 2.0
                mid_hip_x = (lh[0] + rh[0]) / 2.0
                mid_hip_y = (lh[1] + rh[1]) / 2.0

                dx = mid_hip_x - mid_shoulder_x
                dy = mid_hip_y - mid_shoulder_y
                # 90 deg = vertical spine, 0 deg = horizontal spine
                torso_angle_deg = math.degrees(math.atan2(abs(dy), max(1e-3, abs(dx))))
                has_valid_pose = True

                # Torso angle > 40 degrees signifies an upright, crouching, stooping, or sitting worker
                if torso_angle_deg > 40.0:
                    is_crouching_or_sitting = True

        if has_valid_pose:
            if is_crouching_or_sitting:
                is_horizontal = False
            elif torso_angle_deg < 28.0:
                is_horizontal = True
            else:
                is_horizontal = aspect_ratio < 0.90
        else:
            is_horizontal = aspect_ratio < 0.92

        is_falling_motion = (aspect_ratio < 1.25) and (velocity[1] > 35.0) and not is_crouching_or_sitting

        if worker_id not in self.worker_fall_states:
            self.worker_fall_states[worker_id] = {
                "first_down_time": None,
                "last_seen": now,
                "state": "STANDING",
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
                current_state = "FALLEN"
            else:
                duration = now - state_info["first_down_time"]
                if duration >= self.confirmation_duration_sec:
                    current_state = "FALL_CONFIRMED"
                    confidence = 0.98 if has_valid_pose else 0.95
                else:
                    current_state = "FALLEN"
        elif is_falling_motion:
            if current_state not in ("FALLEN", "FALL_CONFIRMED"):
                current_state = "FALLING"
        elif aspect_ratio > 1.35 or (has_valid_pose and torso_angle_deg > 50.0):
            state_info["first_down_time"] = None
            current_state = "STANDING"

        state_info["state"] = current_state

        return FallStatus(
            worker_id=worker_id,
            state=current_state,
            aspect_ratio=round(aspect_ratio, 2),
            is_fall=(current_state == "FALL_CONFIRMED"),
            confidence=confidence,
            duration_sec=round(duration, 1)
        )

    def cleanup_worker(self, worker_id: int):
        """Clean up state when a worker track is removed"""
        self.worker_fall_states.pop(worker_id, None)

    def cleanup_stale_workers(self, max_age_seconds: float = 60.0, current_time: Optional[float] = None):
        """Prune worker states not seen for max_age_seconds to prevent memory growth"""
        now = current_time or time.time()
        stale_ids = [
            wid for wid, s in self.worker_fall_states.items()
            if now - s.get("last_seen", now) > max_age_seconds
        ]
        for wid in stale_ids:
            self.worker_fall_states.pop(wid, None)

