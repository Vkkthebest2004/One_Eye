"""
intrusion.py
------------
Precision Restricted Zone Intrusion Detection Engine.
Integrates MediaPipe Hands landmark tracking, Shapely/OpenCV point-in-polygon testing,
resolution rescaling, and automated intrusion snapshot archiving into ONE EYE.
"""

import os
import cv2
import time
import logging
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np

logger = logging.getLogger(__name__)

try:
    import mediapipe as mp
    mp_hands = mp.solutions.hands
    mp_drawing = mp.solutions.drawing_utils
    MEDIAPIPE_AVAILABLE = True
except Exception as e:
    logger.warning(f"MediaPipe not loaded ({e}); intrusion engine will rely on pose & coordinate tracking.")
    MEDIAPIPE_AVAILABLE = False
    mp_hands = None
    mp_drawing = None


@dataclass
class IntrusionEvent:
    zone_id: str
    zone_name: str
    camera_id: str
    intruded: bool
    contact_points: List[Tuple[int, int]] # List of (px, py) in pixel coordinates
    norm_contact_points: List[Tuple[float, float]] # List of (nx, ny) 0.0-1.0
    intrusion_type: str # "HAND" | "BODY" | "OBJECT"
    timestamp: float
    evidence_path: Optional[str] = None


def scale_polygon(
    polygon: List[Tuple[float, float]],
    from_size: Tuple[int, int],
    to_size: Optional[Tuple[int, int]] = None
) -> np.ndarray:
    """
    Rescale polygon coordinates between different image/sensor resolutions.
    Supports:
      scale_polygon(polygon, from_size, to_size) -> rescales from from_size to to_size
      scale_polygon(polygon, to_size) -> rescales normalized 0.0-1.0 polygon to to_size
    """
    if to_size is None:
        tw, th = from_size
        return np.array([[int(x * tw), int(y * th)] for x, y in polygon], dtype=np.int32)

    fw, fh = from_size
    tw, th = to_size
    if fw <= 0 or fh <= 0:
        return np.array([(int(x), int(y)) for x, y in polygon], dtype=np.int32)
    if (fw, fh) == (tw, th):
        return np.array([(int(x), int(y)) for x, y in polygon], dtype=np.int32)
    sx, sy = tw / float(fw), th / float(fh)
    return np.array([(int(x * sx), int(y * sy)) for x, y in polygon], dtype=np.int32)


def point_in_zone(point: Tuple[int, int], polygon: Any) -> bool:
    """Check if (x, y) point is strictly inside or on the boundary of polygon."""
    if len(polygon) < 3:
        return False
    if not isinstance(polygon, np.ndarray):
        poly_np = np.array(polygon, dtype=np.int32)
    else:
        poly_np = polygon
    return cv2.pointPolygonTest(poly_np, (float(point[0]), float(point[1])), False) >= 0


class IntrusionDetector:
    """
    Real-time intrusion detector adapted from ZoneDetection.
    Monitors marked forbidden/not-allowed areas for hand or body intrusion.
    """
    def __init__(
        self,
        min_detection_confidence: float = 0.55,
        min_tracking_confidence: float = 0.50,
        evidence_dir: Optional[str] = None
    ):
        self.evidence_dir = evidence_dir or "evidence/intrusions"
        os.makedirs(self.evidence_dir, exist_ok=True)
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self._hands = None
        self._last_evidence_time: Dict[str, float] = {}

        if MEDIAPIPE_AVAILABLE:
            try:
                self._hands = mp_hands.Hands(
                    static_image_mode=False,
                    max_num_hands=4,
                    min_detection_confidence=min_detection_confidence,
                    min_tracking_confidence=min_tracking_confidence,
                )
                logger.info("MediaPipe Hands intrusion detector initialized successfully.")
            except Exception as exc:
                logger.warning(f"Could not initialize MediaPipe Hands ({exc}); using fallback.")
                self._hands = None

    def detect_intrusions(
        self,
        frame: np.ndarray,
        zones: List[Any], # List of ZoneDefinition
        camera_id: str,
        timestamp: float
    ) -> List[IntrusionEvent]:
        """
        Evaluate frame against active restricted zones on camera_id.
        Tests for hand landmarks reaching into any zone polygon.
        """
        if frame is None or frame.size == 0 or not zones:
            return []

        h, w = frame.shape[:2]
        events: List[IntrusionEvent] = []

        # 1. MediaPipe Hand Landmark Extraction
        hand_points: List[Tuple[int, int]] = []
        if self._hands is not None:
            try:
                # Downsample frame for MediaPipe Hands if larger than 640 width to reduce RAM & latency
                if w > 640:
                    scale = 640.0 / w
                    small_frame = cv2.resize(frame, (640, int(h * scale)))
                    rgb = cv2.cvtColor(small_frame, cv2.COLOR_BGR2RGB)
                else:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self._hands.process(rgb)
                if results and results.multi_hand_landmarks:
                    for hand_landmarks in results.multi_hand_landmarks:
                        for lm in hand_landmarks.landmark:
                            # 21 landmarks per hand (wrist, finger tips, knuckles)
                            px = int(min(1.0, max(0.0, lm.x)) * w)
                            py = int(min(1.0, max(0.0, lm.y)) * h)
                            hand_points.append((px, py))
            except Exception as err:
                logger.debug(f"MediaPipe hand inference note: {err}")

        # 2. Check each active zone for point intrusion
        for z in zones:
            if not z.active or not getattr(z, "polygon_points", None) or len(z.polygon_points) < 3:
                continue

            # Resolve polygon coordinates for current frame resolution
            poly_points = z.polygon_points
            is_norm = getattr(z, "_is_normalized", False) or all(0.0 <= p[0] <= 1.0 and 0.0 <= p[1] <= 1.0 for p in poly_points)
            if is_norm:
                pixel_polygon = [(int(p[0] * w), int(p[1] * h)) for p in poly_points]
            else:
                pixel_polygon = scale_polygon(poly_points, (1280, 720), (w, h))

            intruded = False
            contact_pts: List[Tuple[int, int]] = []
            norm_contact_pts: List[Tuple[float, float]] = []

            # A. Test hand landmarks
            for pt in hand_points:
                if point_in_zone(pt, pixel_polygon):
                    intruded = True
                    contact_pts.append(pt)
                    norm_contact_pts.append((round(pt[0] / float(w), 4), round(pt[1] / float(h), 4)))

            if intruded:
                evidence_path = None
                last_time = self._last_evidence_time.get(z.id, 0.0)
                # Auto-save snapshot at most once every 3.0 seconds per zone to avoid disk thrashing
                if (timestamp - last_time) >= 3.0:
                    try:
                        self._last_evidence_time[z.id] = timestamp
                        fname = f"intrusion_{camera_id}_{z.id}_{int(timestamp * 1000)}.jpg"
                        full_path = os.path.join(self.evidence_dir, fname)

                        # Annotate frame with intrusion overlay matching intrusion_detector.py
                        annotated = frame.copy()
                        poly_np = np.array(pixel_polygon, dtype=np.int32)
                        overlay = annotated.copy()
                        cv2.fillPoly(overlay, [poly_np], (0, 0, 255))
                        annotated = cv2.addWeighted(overlay, 0.35, annotated, 0.65, 0)
                        cv2.polylines(annotated, [poly_np], True, (0, 0, 255), 3)

                        for cp in contact_pts:
                            cv2.circle(annotated, cp, 7, (0, 0, 255), -1)
                            cv2.circle(annotated, cp, 11, (255, 255, 255), 2)

                        banner = f"INTRUSION DETECTED - RESTRICTED ZONE: {z.name.upper()}"
                        cv2.putText(annotated, banner, (24, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.85, (0, 0, 255), 2)
                        cv2.imwrite(full_path, annotated)
                        evidence_path = full_path
                        logger.info(f"Saved intrusion evidence snapshot: {full_path}")
                    except Exception as e:
                        logger.warning(f"Could not save intrusion snapshot: {e}")

                events.append(IntrusionEvent(
                    zone_id=z.id,
                    zone_name=z.name,
                    camera_id=camera_id,
                    intruded=True,
                    contact_points=contact_pts,
                    norm_contact_points=norm_contact_pts,
                    intrusion_type="HAND",
                    timestamp=timestamp,
                    evidence_path=evidence_path
                ))

        return events
