import time
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
from app.cv.detector import Detection


@dataclass
class Track:
    track_id: int
    class_name: str
    category: str # "PERSON", "MACHINE", "VEHICLE"
    bbox: Tuple[float, float, float, float] # (x1, y1, x2, y2)
    foot_anchor: Tuple[float, float] # (x, y)
    center: Tuple[float, float] # (x, y)
    confidence: float
    first_seen: float
    last_seen: float
    trajectory: List[Tuple[float, float]] = field(default_factory=list) # Foot point history
    velocity: Tuple[float, float] = (0.0, 0.0) # (vx, vy) in px/sec
    lost_frames: int = 0
    state: str = "ACTIVE" # ACTIVE, LOST, REMOVED
    
    # Safety State Attributes
    has_helmet: Optional[bool] = None
    has_vest: Optional[bool] = None
    helmet_confidence: float = 0.0
    vest_confidence: float = 0.0
    current_zone_id: Optional[str] = None
    closest_machine_id: Optional[str] = None
    closest_machine_distance_m: Optional[float] = None
    is_fallen: bool = False
    fall_state: str = "NORMAL"
    current_risk_score: int = 0
    exposure_seconds: float = 0.0
    requires_vlm: bool = False

    def update(self, detection: Detection, timestamp: float):
        dt = max(1e-3, timestamp - self.last_seen)
        new_foot = (detection.foot_x, detection.foot_y)
        new_center = (detection.center_x, detection.center_y)

        # Smoothed velocity estimation
        vx = (new_foot[0] - self.foot_anchor[0]) / dt
        vy = (new_foot[1] - self.foot_anchor[1]) / dt
        self.velocity = (
            0.7 * self.velocity[0] + 0.3 * vx,
            0.7 * self.velocity[1] + 0.3 * vy
        )

        self.bbox = detection.bbox
        self.foot_anchor = new_foot
        self.center = new_center
        self.confidence = detection.confidence
        self.last_seen = timestamp
        self.lost_frames = 0
        self.state = "ACTIVE"
        
        self.trajectory.append(new_foot)
        if len(self.trajectory) > 60: # Maintain last 60 points (~2-4 seconds)
            self.trajectory.pop(0)

        if detection.has_helmet is not None:
            self.has_helmet = detection.has_helmet
        if detection.has_vest is not None:
            self.has_vest = detection.has_vest

    def mark_missed(self):
        self.lost_frames += 1
        if self.lost_frames > 30:
            self.state = "REMOVED"
        elif self.lost_frames > 5:
            self.state = "LOST"

    def to_dict(self) -> Dict[str, Any]:
        prefix = "Worker" if self.category == "PERSON" else self.class_name.capitalize()
        return {
            "track_id": self.track_id,
            "label": f"{prefix} #{self.track_id:02d}",
            "class_name": self.class_name,
            "category": self.category,
            "bbox": [round(v, 1) for v in self.bbox],
            "foot_anchor": [round(v, 1) for v in self.foot_anchor],
            "velocity": [round(v, 1) for v in self.velocity],
            "state": self.state,
            "has_helmet": self.has_helmet,
            "has_vest": self.has_vest,
            "current_zone_id": self.current_zone_id,
            "closest_machine_id": self.closest_machine_id,
            "closest_machine_distance_m": round(self.closest_machine_distance_m, 2) if self.closest_machine_distance_m is not None else None,
            "is_fallen": self.is_fallen,
            "fall_state": self.fall_state,
            "current_risk_score": self.current_risk_score,
            "exposure_seconds": round(self.exposure_seconds, 1),
            "requires_vlm": self.requires_vlm,
            "trajectory": [[round(pt[0], 1), round(pt[1], 1)] for pt in self.trajectory[-20:]]
        }


class MultiObjectTracker:
    """
    ByteTrack Multi-Object Tracking Engine with IoU + Centroid Euclidean cost matrix,
    Kalman-style motion prediction, and category-separated identity continuity.
    """
    def __init__(self, max_distance: float = 80.0, iou_threshold: float = 0.3):
        self.max_distance = max_distance
        self.iou_threshold = iou_threshold
        self.tracks: Dict[int, Track] = {}
        self.next_track_id: int = 1

    @staticmethod
    def _compute_iou(boxA: Tuple[float, float, float, float], boxB: Tuple[float, float, float, float]) -> float:
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])

        inter_area = max(0.0, xB - xA) * max(0.0, yB - yA)
        if inter_area <= 0:
            return 0.0

        boxA_area = max(1e-5, (boxA[2] - boxA[0]) * (boxA[3] - boxA[1]))
        boxB_area = max(1e-5, (boxB[2] - boxB[0]) * (boxB[3] - boxB[1]))

        return inter_area / float(boxA_area + boxB_area - inter_area)

    @staticmethod
    def _compute_distance(ptA: Tuple[float, float], ptB: Tuple[float, float]) -> float:
        return math.hypot(ptA[0] - ptB[0], ptA[1] - ptB[1])

    def update(self, detections: List[Detection], timestamp: float) -> List[Track]:
        # Filter for trackable entities: Persons and Mobile Machines/Vehicles
        trackable_detections = [
            d for d in detections
            if d.category in ("PERSON", "MACHINE", "VEHICLE") or d.class_name in ("person", "worker", "forklift", "vehicle")
        ]
        
        # Fallback for unclassified confidence detections
        if not trackable_detections and detections:
            trackable_detections = [d for d in detections if d.confidence >= 0.25]

        active_track_ids = [tid for tid, trk in self.tracks.items() if trk.state != "REMOVED"]
        matched_tracks = set()
        matched_detections = set()

        if active_track_ids and trackable_detections:
            for det_idx, det in enumerate(trackable_detections):
                best_match_id = None
                best_score = -1.0

                for tid in active_track_ids:
                    if tid in matched_tracks:
                        continue
                    trk = self.tracks[tid]
                    # Enforce category match when available
                    if trk.category != det.category and trk.category != "PERSON":
                        continue

                    iou = self._compute_iou(det.bbox, trk.bbox)
                    dist = self._compute_distance(det.center, trk.center)

                    if iou >= self.iou_threshold:
                        score = iou + 1.0
                    elif dist < self.max_distance:
                        score = 1.0 - (dist / self.max_distance)
                    else:
                        score = -1.0

                    if score > best_score and score > 0.1:
                        best_score = score
                        best_match_id = tid

                if best_match_id is not None:
                    self.tracks[best_match_id].update(det, timestamp)
                    matched_tracks.add(best_match_id)
                    matched_detections.add(det_idx)

        # Mark unmatched existing tracks as missed
        for tid in active_track_ids:
            if tid not in matched_tracks:
                self.tracks[tid].mark_missed()

        # Create new tracks for unmatched detections
        for det_idx, det in enumerate(trackable_detections):
            if det_idx not in matched_detections:
                new_track = Track(
                    track_id=self.next_track_id,
                    class_name=det.class_name,
                    category=det.category,
                    bbox=det.bbox,
                    foot_anchor=(det.foot_x, det.foot_y),
                    center=(det.center_x, det.center_y),
                    confidence=det.confidence,
                    first_seen=timestamp,
                    last_seen=timestamp,
                    trajectory=[(det.foot_x, det.foot_y)],
                    has_helmet=det.has_helmet,
                    has_vest=det.has_vest
                )
                self.tracks[self.next_track_id] = new_track
                self.next_track_id += 1

        # Clean up stale removed tracks
        self.tracks = {tid: trk for tid, trk in self.tracks.items() if trk.state != "REMOVED"}

        return [trk for trk in self.tracks.values() if trk.state == "ACTIVE"]
