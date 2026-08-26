import time
import logging
from typing import List, Optional, Tuple, Dict, Any
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FireSmokeResult:
    hazard_type: str # "FIRE" or "SMOKE"
    confidence: float
    bbox: Tuple[float, float, float, float] # (x1, y1, x2, y2)
    area_pixels: float
    is_critical: bool = True


class FireSmokeDetector:
    """
    Fire & Smoke Hazard Detection Provider.
    Supports dedicated model inferences or robust visual energy/color heuristics.
    """
    def __init__(self, min_area_ratio: float = 0.12):
        self.min_area_ratio = min_area_ratio

    def detect(self, frame: np.ndarray) -> List[FireSmokeResult]:
        if frame is None or frame.size == 0:
            return []

        results: List[FireSmokeResult] = []
        h, w = frame.shape[:2]
        total_pixels = h * w

        try:
            import cv2
            # Fire detection heuristic: Strict HSV + YCrCb color range (high brightness, high saturation)
            hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
            
            # Fire mask (strictly concentrated red-orange flame cores)
            lower_fire = np.array([0, 180, 240])
            upper_fire = np.array([25, 255, 255])
            fire_mask = cv2.inRange(hsv, lower_fire, upper_fire)

            # Find flame contours
            contours, _ = cv2.findContours(fire_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if (area / total_pixels) >= self.min_area_ratio:
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    conf = min(0.96, 0.85 + (area / total_pixels) * 2.0)
                    results.append(FireSmokeResult(
                        hazard_type="FIRE",
                        confidence=round(conf, 2),
                        bbox=(float(x), float(y), float(x + cw), float(y + ch)),
                        area_pixels=float(area),
                        is_critical=True
                    ))

            # Smoke mask (gray, low saturation, moderate value)
            lower_smoke = np.array([0, 0, 100])
            upper_smoke = np.array([180, 40, 210])
            smoke_mask = cv2.inRange(hsv, lower_smoke, upper_smoke)
            
            smoke_contours, _ = cv2.findContours(smoke_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in smoke_contours:
                area = cv2.contourArea(cnt)
                if (area / total_pixels) >= (self.min_area_ratio * 3.0):
                    x, y, cw, ch = cv2.boundingRect(cnt)
                    results.append(FireSmokeResult(
                        hazard_type="SMOKE",
                        confidence=0.88,
                        bbox=(float(x), float(y), float(x + cw), float(y + ch)),
                        area_pixels=float(area),
                        is_critical=True
                    ))

        except Exception as e:
            logger.error(f"Fire/Smoke detection error: {e}")

        return results
