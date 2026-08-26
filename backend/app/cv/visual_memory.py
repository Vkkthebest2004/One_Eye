"""
ONE EYE — Visual Danger Memory & Real-Time Planar Homography Tracking Engine

Enables operators to snap a photo of any hazardous machine, workspace, or place.
The engine computes invariant 2D visual descriptors (ORB/AKAZE) on the keyframe,
and dynamically tracks & warps the danger perimeter using RANSAC Planar Homography
as the mobile phone camera moves, tilts, or re-enters the field of view.
"""

import os
import cv2
import time
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class TrackedVisualZone:
    zone_id: str
    camera_id: str
    name: str
    polygon_norm: List[List[float]] # Normalized [0, 1] points in live frame
    polygon_px: List[List[int]]     # Absolute pixel points in live frame
    reference_polygon_norm: List[List[float]] # Fallback reference coordinates
    severity: int
    is_visible: bool                # True if currently active
    match_confidence: float         # Inlier ratio / match quality (0.0 - 1.0)
    inlier_count: int


@dataclass
class VisualAnchor:
    zone_id: str
    camera_id: str
    name: str
    reference_polygon_norm: List[List[float]] # [0.0 - 1.0] in reference frame
    reference_polygon_px: List[List[int]]     # [x, y] in reference image
    keypoints: Any
    descriptors: Any
    ref_width: int
    ref_height: int
    severity: int
    snapshot_path: Optional[str] = None
    created_at: float = field(default_factory=time.time)


class VisualMemoryEngine:
    """
    Visual Keyframe Memory & Planar Homography Tracking Engine.
    Locks safety hazard perimeters onto real-world objects and physical locations.
    """
    def __init__(self, storage_dir: str = "evidence/anchors"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # In-memory anchor registry: zone_id -> VisualAnchor
        self.anchors: Dict[str, VisualAnchor] = {}
        
        # Robust ORB Feature Extractor (1500 keypoints)
        self.orb = cv2.ORB_create(
            nfeatures=1500,
            scaleFactor=1.2,
            nlevels=8,
            edgeThreshold=15,
            firstLevel=0,
            WTA_K=2,
            scoreType=cv2.ORB_FAST_SCORE,
            patchSize=31,
            fastThreshold=15,
        )
        
        # Brute-Force Matcher with Hamming Distance
        self.bf_matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        
        # Cache of last known homographies for temporal smoothing
        self._last_homography: Dict[str, np.ndarray] = {}
        self._last_tracked: Dict[str, TrackedVisualZone] = {}

    def register_anchor(
        self,
        zone_id: str,
        camera_id: str,
        name: str,
        keyframe_bgr: np.ndarray,
        polygon_points_norm: List[List[float]],
        severity: int = 90,
    ) -> bool:
        """
        Extract visual descriptors from reference photo and persist anchor in memory & disk.
        """
        if keyframe_bgr is None or keyframe_bgr.size == 0 or len(polygon_points_norm) < 3:
            logger.warning(f"Failed to register visual anchor {zone_id}: invalid image or polygon")
            return False

        h, w = keyframe_bgr.shape[:2]
        gray = cv2.cvtColor(keyframe_bgr, cv2.COLOR_BGR2GRAY)
        
        # Extract features on reference image
        kp, des = self.orb.detectAndCompute(gray, None)
        if kp is None or des is None or len(kp) < 15:
            logger.warning(f"Could not extract sufficient visual features from keyframe for zone {zone_id} ({len(kp) if kp else 0} keypoints)")
            # Fallback: still register without features for screen-space coordinate tracking
            kp = []
            des = None

        # Compute pixel polygon coordinates on reference frame
        ref_px_poly = [
            [int(pt[0] * w), int(pt[1] * h)]
            for pt in polygon_points_norm
        ]

        # Save keyframe image to disk
        snapshot_filename = f"{zone_id}.jpg"
        snapshot_path = self.storage_dir / snapshot_filename
        try:
            cv2.imwrite(str(snapshot_path), keyframe_bgr, [cv2.IMWRITE_JPEG_QUALITY, 90])
        except Exception as e:
            logger.warning(f"Could not save keyframe snapshot to disk: {e}")

        anchor = VisualAnchor(
            zone_id=zone_id,
            camera_id=camera_id,
            name=name,
            reference_polygon_norm=polygon_points_norm,
            reference_polygon_px=ref_px_poly,
            keypoints=kp,
            descriptors=des,
            ref_width=w,
            ref_height=h,
            severity=severity,
            snapshot_path=str(snapshot_path),
        )

        self.anchors[zone_id] = anchor
        logger.info(f"🧠 Registered Visual Danger Anchor '{name}' (ID: {zone_id}) with {len(kp)} reference keypoints")
        return True

    def unregister_anchor(self, zone_id: str):
        if zone_id in self.anchors:
            del self.anchors[zone_id]
        if zone_id in self._last_homography:
            del self._last_homography[zone_id]
        if zone_id in self._last_tracked:
            del self._last_tracked[zone_id]
        logger.info(f"Unregistered visual anchor {zone_id}")

    def track_live_frame(self, live_frame_bgr: np.ndarray, camera_id: str) -> List[TrackedVisualZone]:
        """
        Track and project all registered visual anchors onto the live camera frame.
        Computes 3x3 RANSAC Planar Homography to project danger zones to the current camera viewpoint.
        """
        results: List[TrackedVisualZone] = []
        if live_frame_bgr is None or live_frame_bgr.size == 0:
            return results

        h_live, w_live = live_frame_bgr.shape[:2]
        
        # Find all anchors applicable to this camera channel or mobile aliases
        relevant_anchors = [
            a for a in self.anchors.values()
            if a.camera_id == camera_id
            or (camera_id.startswith("CAM_MOB") and a.camera_id.startswith("CAM_MOB"))
            or a.camera_id in ("CAM_MOBILE", "CAM_MOB_24151JEG")
        ]

        if not relevant_anchors:
            return results

        gray_live = cv2.cvtColor(live_frame_bgr, cv2.COLOR_BGR2GRAY)
        kp_live, des_live = self.orb.detectAndCompute(gray_live, None)

        if kp_live is None or des_live is None or len(kp_live) < 15:
            # Not enough live features; return last known states marked invisible
            for anchor in relevant_anchors:
                results.append(TrackedVisualZone(
                    zone_id=anchor.zone_id,
                    camera_id=camera_id,
                    name=anchor.name,
                    polygon_norm=anchor.reference_polygon_norm,
                    polygon_px=anchor.reference_polygon_px,
                    severity=anchor.severity,
                    is_visible=False,
                    match_confidence=0.0,
                    inlier_count=0
                ))
            return results

        for anchor in relevant_anchors:
            if anchor.descriptors is None or len(anchor.descriptors) < 10:
                # Screen-space fallback (fixed coordinate polygon)
                results.append(TrackedVisualZone(
                    zone_id=anchor.zone_id,
                    camera_id=camera_id,
                    name=anchor.name,
                    polygon_norm=anchor.reference_polygon_norm,
                    polygon_px=[[int(p[0]*w_live), int(p[1]*h_live)] for p in anchor.reference_polygon_norm],
                    severity=anchor.severity,
                    is_visible=True,
                    match_confidence=1.0,
                    inlier_count=100
                ))
                continue

            # Fast k-NN matching (k=2) for Lowe's ratio test
            try:
                matches = self.bf_matcher.knnMatch(anchor.descriptors, des_live, k=2)
            except Exception:
                continue

            good_matches = []
            for m_tuple in matches:
                if len(m_tuple) == 2:
                    m, n = m_tuple
                    if m.distance < 0.75 * n.distance:
                        good_matches.append(m)

            # Minimum inliers required to estimate a robust 3x3 homography matrix
            MIN_INLIERS = 8
            if len(good_matches) >= MIN_INLIERS:
                src_pts = np.float32([anchor.keypoints[m.queryIdx].pt for m in good_matches]).reshape(-1, 1, 2)
                dst_pts = np.float32([kp_live[m.trainIdx].pt for m in good_matches]).reshape(-1, 1, 2)

                H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 4.0)
                inliers = np.sum(mask) if mask is not None else 0

                if H is not None and inliers >= 8:
                    # Validate homography (check determinant and perspective distortion)
                    det = np.linalg.det(H[:2, :2])
                    if det > 0.08 and det < 12.0:
                        # Transform reference polygon points into live frame space
                        ref_pts = np.float32(anchor.reference_polygon_px).reshape(-1, 1, 2)
                        projected_pts = cv2.perspectiveTransform(ref_pts, H)
                        
                        # Geometric sanity checks on projected polygon
                        poly_int = np.int32(projected_pts)
                        if cv2.isContourConvex(poly_int):
                            area = cv2.contourArea(poly_int)
                            frame_area = float(w_live * h_live)
                            if 0.002 * frame_area <= area <= 0.95 * frame_area:
                                live_px = []
                                live_norm = []
                                for pt in projected_pts:
                                    px = float(pt[0][0])
                                    py = float(pt[0][1])
                                    live_px.append([int(px), int(py)])
                                    live_norm.append([
                                        round(px / w_live, 4),
                                        round(py / h_live, 4)
                                    ])

                                # Verify that polygon center is in or near frame
                                avg_x = sum(p[0] for p in live_norm) / len(live_norm)
                                avg_y = sum(p[1] for p in live_norm) / len(live_norm)
                                if -0.15 <= avg_x <= 1.15 and -0.15 <= avg_y <= 1.15:
                                    confidence = min(1.0, round(inliers / max(1, len(good_matches)), 2))
                                    tracked = TrackedVisualZone(
                                        zone_id=anchor.zone_id,
                                        camera_id=camera_id,
                                        name=anchor.name,
                                        polygon_norm=live_norm,
                                        polygon_px=live_px,
                                        reference_polygon_norm=anchor.reference_polygon_norm,
                                        severity=anchor.severity,
                                        is_visible=True,
                                        match_confidence=confidence,
                                        inlier_count=int(inliers)
                                    )
                                    self._last_tracked[anchor.zone_id] = tracked
                                    results.append(tracked)
                                    continue

            # Object is NOT in view (camera is pointed away or looking at another place)
            # is_visible=False ensures no permanent marker on screen and no false alarms
            results.append(TrackedVisualZone(
                zone_id=anchor.zone_id,
                camera_id=camera_id,
                name=anchor.name,
                polygon_norm=[],
                polygon_px=[],
                reference_polygon_norm=anchor.reference_polygon_norm,
                severity=anchor.severity,
                is_visible=False,
                match_confidence=round(len(good_matches) / 50.0, 2),
                inlier_count=len(good_matches)
            ))

        return results


# Global Visual Memory Engine Singleton
visual_memory_engine = VisualMemoryEngine()
