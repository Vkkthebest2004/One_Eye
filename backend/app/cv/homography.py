import logging
from typing import List, Tuple, Optional, Dict, Any
import numpy as np
import cv2

logger = logging.getLogger(__name__)


class HomographyCalibrator:
    """
    Planar Camera Calibration & 3x3 Homography Transformation.
    Converts 2D camera pixel coordinates (x, y) into metric floor coordinates (X, Y) in meters.
    """
    def __init__(self, camera_id: str):
        self.camera_id = camera_id
        self.H_matrix: Optional[np.ndarray] = None
        self.H_inv: Optional[np.ndarray] = None
        self.image_points: List[Tuple[float, float]] = []
        self.world_points: List[Tuple[float, float]] = []
        self.is_calibrated: bool = False

    def calibrate(
        self,
        image_points: List[Tuple[float, float]],
        world_points: List[Tuple[float, float]]
    ) -> bool:
        """
        Compute 3x3 Homography Matrix from 4+ corresponding point pairs.
        image_points: [(x1, y1), (x2, y2), (x3, y3), (x4, y4)] in pixels
        world_points: [(X1, Y1), (X2, Y2), (X3, Y3), (X4, Y4)] in real-world meters
        """
        if len(image_points) < 4 or len(world_points) < 4 or len(image_points) != len(world_points):
            logger.error("Calibration requires at least 4 corresponding point pairs")
            return False

        try:
            pts_src = np.array(image_points, dtype=np.float32)
            pts_dst = np.array(world_points, dtype=np.float32)

            H, status = cv2.findHomography(pts_src, pts_dst, cv2.RANSAC, 5.0)
            if H is None:
                logger.error("Failed to compute homography matrix")
                return False

            self.H_matrix = H
            self.H_inv = np.linalg.inv(H)
            self.image_points = image_points
            self.world_points = world_points
            self.is_calibrated = True
            logger.info(f"[{self.camera_id}] Homography calibration successful")
            return True
        except Exception as e:
            logger.error(f"Error during calibration: {e}")
            return False

    def set_matrix(self, matrix_list: List[List[float]], image_pts=None, world_pts=None):
        try:
            H = np.array(matrix_list, dtype=np.float32)
            if H.shape == (3, 3):
                self.H_matrix = H
                self.H_inv = np.linalg.inv(H)
                self.is_calibrated = True
                if image_pts:
                    self.image_points = image_pts
                if world_pts:
                    self.world_points = world_pts
        except Exception as e:
            logger.error(f"Error setting homography matrix: {e}")

    def pixel_to_world(self, px: float, py: float) -> Tuple[Optional[float], Optional[float], str]:
        """
        Transform pixel point to real-world floor coordinate in meters.
        Returns: (X_m, Y_m, mode_string)
        """
        if not self.is_calibrated or self.H_matrix is None:
            # Explicitly return uncalibrated / pixel distance mode
            return None, None, "PIXEL_DISTANCE_MODE"

        try:
            vec = np.array([px, py, 1.0], dtype=np.float32)
            world_vec = np.dot(self.H_matrix, vec)
            if abs(world_vec[2]) < 1e-6:
                return None, None, "CALCULATION_ERROR"
            
            X = float(world_vec[0] / world_vec[2])
            Y = float(world_vec[1] / world_vec[2])
            return X, Y, "METRIC_MODE"
        except Exception as e:
            logger.error(f"Pixel to world transform error: {e}")
            return None, None, "CALCULATION_ERROR"

    def world_to_pixel(self, X: float, Y: float) -> Tuple[Optional[float], Optional[float]]:
        if not self.is_calibrated or self.H_inv is None:
            return None, None
        try:
            vec = np.array([X, Y, 1.0], dtype=np.float32)
            px_vec = np.dot(self.H_inv, vec)
            if abs(px_vec[2]) < 1e-6:
                return None, None
            px = float(px_vec[0] / px_vec[2])
            py = float(px_vec[1] / px_vec[2])
            return px, py
        except Exception:
            return None, None

    def compute_distance_m(
        self,
        ptA_px: Tuple[float, float],
        ptB_px: Tuple[float, float],
        pixel_scale_fallback: float = 0.02
    ) -> Tuple[float, str]:
        """
        Compute distance between two pixel coordinates.
        Returns (distance, mode: "METRIC_MODE" or "PIXEL_DISTANCE_MODE")
        """
        if self.is_calibrated:
            xA, yA, modeA = self.pixel_to_world(ptA_px[0], ptA_px[1])
            xB, yB, modeB = self.pixel_to_world(ptB_px[0], ptB_px[1])
            if xA is not None and xB is not None:
                dist_m = float(np.hypot(xA - xB, yA - yB))
                return round(dist_m, 2), "METRIC_MODE"

        # Uncalibrated fallback
        px_dist = float(np.hypot(ptA_px[0] - ptB_px[0], ptA_px[1] - ptB_px[1]))
        estimated_m = round(px_dist * pixel_scale_fallback, 2)
        return estimated_m, "PIXEL_DISTANCE_MODE"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "camera_id": self.camera_id,
            "is_calibrated": self.is_calibrated,
            "matrix": self.H_matrix.tolist() if self.H_matrix is not None else None,
            "image_points": self.image_points,
            "world_points": self.world_points
        }
