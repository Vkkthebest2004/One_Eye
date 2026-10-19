import time
import logging
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from collections import deque
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PPEItem:
    item_type: str # "HELMET", "VEST", "GOGGLES", "GLASSES", "GLOVES", "NO_HELMET", "NO_VEST", "NO_GLASSES"
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
    has_glasses: bool = False
    glasses_confidence: float = 0.0
    associated_helmet_bbox: Optional[Tuple[float, float, float, float]] = None
    associated_vest_bbox: Optional[Tuple[float, float, float, float]] = None
    associated_glasses_bbox: Optional[Tuple[float, float, float, float]] = None
    requires_vlm_disambiguation: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "has_helmet": self.has_helmet,
            "has_vest": self.has_vest,
            "has_glasses": self.has_glasses,
            "helmet_confidence": round(self.helmet_confidence, 3),
            "vest_confidence": round(self.vest_confidence, 3),
            "glasses_confidence": round(self.glasses_confidence, 3),
            "is_violation": self.is_violation,
            "missing_items": self.missing_items,
            "persisted_seconds": round(self.persisted_seconds, 1),
            "requires_vlm_disambiguation": self.requires_vlm_disambiguation
        }


@dataclass
class PPEAssociationResult:
    matched_helmet: Optional[PPEItem] = None
    matched_no_helmet: Optional[PPEItem] = None
    matched_vest: Optional[PPEItem] = None
    matched_no_vest: Optional[PPEItem] = None
    matched_glasses: Optional[PPEItem] = None
    matched_no_glasses: Optional[PPEItem] = None

    def __iter__(self):
        # Backwards compatible unpacking for (matched_helmet, matched_vest)
        return iter((self.matched_helmet, self.matched_vest))


class WorkerPPESmoother:
    """
    Temporal Debouncing and Confidence Smoothing for a tracked worker.
    Eliminates single-frame detector dropouts, occlusions, and visual jitter.
    """
    def __init__(self, window_size: int = 6):
        self.window_size = window_size
        self.helmet_votes: deque = deque(maxlen=window_size)
        self.vest_votes: deque = deque(maxlen=window_size)
        self.glasses_votes: deque = deque(maxlen=window_size)
        self.helmet_conf: float = 0.5
        self.vest_conf: float = 0.5
        self.glasses_conf: float = 0.5
        self.last_updated: float = 0.0

    def update(
        self,
        raw_helmet: bool,
        raw_vest: bool,
        conf_h: float,
        conf_v: float,
        now: float,
        raw_glasses: bool = False,
        conf_g: float = 0.5
    ) -> Tuple[bool, bool, bool, float, float, float]:
        self.helmet_votes.append(raw_helmet)
        self.vest_votes.append(raw_vest)
        self.glasses_votes.append(raw_glasses)
        self.last_updated = now

        # Exponential moving average (EMA) for smooth, non-jumping confidence values
        if len(self.helmet_votes) == 1:
            self.helmet_conf = conf_h
            self.vest_conf = conf_v
            self.glasses_conf = conf_g
        else:
            alpha = 0.35
            self.helmet_conf = alpha * conf_h + (1.0 - alpha) * self.helmet_conf
            self.vest_conf = alpha * conf_v + (1.0 - alpha) * self.vest_conf
            self.glasses_conf = alpha * conf_g + (1.0 - alpha) * self.glasses_conf

        # Debounce logic: require consistent confirmation to prevent flickering
        h_positive = sum(1 for v in self.helmet_votes if v)
        v_positive = sum(1 for v in self.vest_votes if v)
        g_positive = sum(1 for v in self.glasses_votes if v)
        n = len(self.helmet_votes)

        # High-confidence direct override
        if conf_h >= 0.70:
            smoothed_helmet = raw_helmet
        else:
            smoothed_helmet = (h_positive / max(1, n)) >= 0.50

        if conf_v >= 0.70:
            smoothed_vest = raw_vest
        else:
            smoothed_vest = (v_positive / max(1, n)) >= 0.50

        if conf_g >= 0.70:
            smoothed_glasses = raw_glasses
        else:
            smoothed_glasses = (g_positive / max(1, n)) >= 0.50

        return smoothed_helmet, smoothed_vest, smoothed_glasses, self.helmet_conf, self.vest_conf, self.glasses_conf


class PPEEngine:
    """
    Production-Grade PPE Compliance & Spatial Association Engine.
    
    Architecture:
    1. Spatial Association Layer:
       - Extracts expanded Head ROI (upper 38% with horizontal and overhead margins)
       - Extracts expanded Eye ROI (upper 8-35% with orbital margins)
       - Extracts expanded Body ROI (middle 18-75% with shoulder margins)
       - Matches detected PPE objects (helmets, vests, glasses/goggles, and negative classes)
    2. Facial Orbital Feature Analyzer:
       - Evaluates eyewear frame rims, nasal bridge horizontal gradients, and lens reflections
    3. Heuristic / Color Fallback:
       - Inspects HSV color distributions for bright hardhats and high-vis vests
    4. Temporal Debouncing & Confidence Smoothing:
       - Multi-frame rolling window per worker eliminates detection flicker and false alarms
    """
    def __init__(self, persistence_threshold_sec: float = 1.0):
        self.persistence_threshold_sec = persistence_threshold_sec
        # worker_id -> {'first_seen': float, 'last_seen': float, 'missing': list}
        self.violation_history: Dict[int, Dict[str, Any]] = {}
        # worker_id -> WorkerPPESmoother
        self.smoothers: Dict[int, WorkerPPESmoother] = {}

    @staticmethod
    def get_head_roi(person_bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Upper 38% of worker bounding box with margins for tall/tilted hardhats"""
        x1, y1, x2, y2 = person_bbox
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        return (x1 - 0.10 * w, y1 - 0.12 * h, x2 + 0.10 * w, y1 + 0.38 * h)

    @staticmethod
    def get_eye_roi(person_bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Eye / face protection region: upper 8% to 35% of worker bounding box"""
        x1, y1, x2, y2 = person_bbox
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        return (x1 - 0.05 * w, y1 + 0.06 * h, x2 + 0.05 * w, y1 + 0.35 * h)

    @staticmethod
    def get_body_roi(person_bbox: Tuple[float, float, float, float]) -> Tuple[float, float, float, float]:
        """Middle 18% to 75% of worker bounding box with shoulder margins"""
        x1, y1, x2, y2 = person_bbox
        w = max(1.0, x2 - x1)
        h = max(1.0, y2 - y1)
        return (x1 - 0.08 * w, y1 + 0.18 * h, x2 + 0.08 * w, y1 + 0.75 * h)

    @staticmethod
    def is_point_inside_roi(pt: Tuple[float, float], roi: Tuple[float, float, float, float]) -> bool:
        px, py = pt
        rx1, ry1, rx2, ry2 = roi
        return (rx1 <= px <= rx2) and (ry1 <= py <= ry2)

    @staticmethod
    def box_intersects_roi(
        box: Tuple[float, float, float, float],
        roi: Tuple[float, float, float, float],
        min_overlap: float = 0.20
    ) -> bool:
        bx1, by1, bx2, by2 = box
        rx1, ry1, rx2, ry2 = roi
        ix1, iy1 = max(bx1, rx1), max(by1, ry1)
        ix2, iy2 = min(bx2, rx2), min(by2, ry2)
        if ix2 > ix1 and iy2 > iy1:
            inter_area = (ix2 - ix1) * (iy2 - iy1)
            box_area = max(1.0, (bx2 - bx1) * (by2 - by1))
            return (inter_area / box_area) >= min_overlap
        return False

    @staticmethod
    def analyze_facial_glasses(frame: np.ndarray, person_bbox: Tuple[float, float, float, float]) -> Tuple[bool, float]:
        """
        Facial orbital & nasal bridge edge analyzer for glasses and safety goggles.
        Distinguishes eyewear (frame rims, lens contours, nasal bridge horizontal gradients, specular reflections)
        from bare facial skin.
        """
        x1, y1, x2, y2 = [int(v) for v in person_bbox]
        h, w = y2 - y1, x2 - x1
        if h < 40 or w < 30 or frame is None or frame.size == 0:
            return False, 0.50

        # Eye & upper nasal zone: 12% to 35% of worker bbox height, 18% to 82% of width
        ey1, ey2 = max(0, y1 + int(h * 0.12)), min(frame.shape[0], y1 + int(h * 0.35))
        ex1, ex2 = max(0, x1 + int(w * 0.18)), min(frame.shape[1], x1 + int(w * 0.82))
        if ey2 <= ey1 + 5 or ex2 <= ex1 + 10:
            return False, 0.50

        try:
            import cv2
            eye_crop = frame[ey1:ey2, ex1:ex2]
            gray = cv2.cvtColor(eye_crop, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else eye_crop

            # 1. Edge density in orbital region (frame rims, lenses, temple hinges)
            edges = cv2.Canny(gray, 40, 130)
            edge_ratio = np.count_nonzero(edges) / float(max(1, eye_crop.shape[0] * eye_crop.shape[1]))

            # 2. Nasal bridge horizontal edge (glasses bridge creates strong horizontal gradient)
            bw1, bw2 = int(eye_crop.shape[1] * 0.35), int(eye_crop.shape[1] * 0.65)
            bridge = gray[:, bw1:bw2]
            if bridge.size > 0:
                sobel_y = cv2.Sobel(bridge, cv2.CV_64F, 0, 1, ksize=3)
                bridge_grad = float(np.mean(np.abs(sobel_y)))
            else:
                bridge_grad = 0.0

            # 3. Specular reflection / lens glare highlights
            if len(eye_crop.shape) == 3:
                hsv = cv2.cvtColor(eye_crop, cv2.COLOR_BGR2HSV)
                glare_mask = cv2.inRange(hsv, np.array([0, 0, 230]), np.array([180, 50, 255]))
                glare_ratio = np.count_nonzero(glare_mask) / float(max(1, eye_crop.shape[0] * eye_crop.shape[1]))
            else:
                glare_ratio = 0.0

            has_glasses = (
                (edge_ratio > 0.045 and bridge_grad > 15.0) or
                (glare_ratio > 0.02 and edge_ratio > 0.035) or
                (edge_ratio > 0.075)
            )
            conf = min(0.92, float(0.52 + edge_ratio * 2.5 + (bridge_grad / 110.0)))
            return bool(has_glasses), conf
        except Exception:
            return False, 0.50

    def associate_ppe_detections(
        self,
        person_bbox: Tuple[float, float, float, float],
        detected_ppe_items: List[PPEItem]
    ) -> PPEAssociationResult:
        """
        Spatially associates detected helmets, vests, glasses/goggles to the worker's Head, Eye, and Body ROIs.
        """
        head_roi = self.get_head_roi(person_bbox)
        eye_roi = self.get_eye_roi(person_bbox)
        body_roi = self.get_body_roi(person_bbox)

        matched_helmet: Optional[PPEItem] = None
        matched_no_helmet: Optional[PPEItem] = None
        matched_vest: Optional[PPEItem] = None
        matched_no_vest: Optional[PPEItem] = None
        matched_glasses: Optional[PPEItem] = None
        matched_no_glasses: Optional[PPEItem] = None

        for item in detected_ppe_items:
            itype = item.item_type.upper()
            is_head_item = self.is_point_inside_roi(item.center, head_roi) or self.box_intersects_roi(item.bbox, head_roi, 0.20)
            is_eye_item = self.is_point_inside_roi(item.center, eye_roi) or self.box_intersects_roi(item.bbox, eye_roi, 0.15)
            is_body_item = self.is_point_inside_roi(item.center, body_roi) or self.box_intersects_roi(item.bbox, body_roi, 0.20)

            if itype in ("HELMET", "HARD_HAT", "HARDHAT", "PPE_HELMET"):
                if is_head_item:
                    if matched_helmet is None or item.confidence > matched_helmet.confidence:
                        matched_helmet = item
            elif itype in ("NO_HELMET", "NO_HARD_HAT", "NO_HARDHAT", "NO-HELMET", "NO-HARDHAT"):
                if is_head_item:
                    if matched_no_helmet is None or item.confidence > matched_no_helmet.confidence:
                        matched_no_helmet = item
            elif itype in ("VEST", "SAFETY_VEST", "PPE_VEST"):
                if is_body_item:
                    if matched_vest is None or item.confidence > matched_vest.confidence:
                        matched_vest = item
            elif itype in ("NO_VEST", "NO_SAFETY_VEST", "NO-VEST"):
                if is_body_item:
                    if matched_no_vest is None or item.confidence > matched_no_vest.confidence:
                        matched_no_vest = item
            elif itype in ("GLASSES", "GOGGLES", "GOGGLE", "SAFETY_GLASSES", "PPE_GLASSES"):
                if is_eye_item or is_head_item:
                    if matched_glasses is None or item.confidence > matched_glasses.confidence:
                        matched_glasses = item
            elif itype in ("NO_GLASSES", "NO_GOGGLES", "NO_GOGGLE", "NO-GOGGLE", "NO-GLASSES"):
                if is_eye_item or is_head_item:
                    if matched_no_glasses is None or item.confidence > matched_no_glasses.confidence:
                        matched_no_glasses = item

        return PPEAssociationResult(
            matched_helmet=matched_helmet,
            matched_no_helmet=matched_no_helmet,
            matched_vest=matched_vest,
            matched_no_vest=matched_no_vest,
            matched_glasses=matched_glasses,
            matched_no_glasses=matched_no_glasses
        )

    def analyze_worker(
        self,
        worker_id: int,
        person_bbox: Tuple[float, float, float, float],
        frame: Optional[np.ndarray] = None,
        detected_ppe_items: Optional[List[PPEItem]] = None,
        explicit_helmet: Optional[bool] = None,
        explicit_vest: Optional[bool] = None,
        explicit_glasses: Optional[bool] = None,
        require_glasses: bool = False,
        timestamp: Optional[float] = None
    ) -> PPEStatus:
        now = timestamp or time.time()
        detected_ppe_items = detected_ppe_items or []

        matched_helmet: Optional[PPEItem] = None
        matched_no_helmet: Optional[PPEItem] = None
        matched_vest: Optional[PPEItem] = None
        matched_no_vest: Optional[PPEItem] = None
        matched_glasses: Optional[PPEItem] = None
        matched_no_glasses: Optional[PPEItem] = None
        requires_vlm = False

        # 1. Spatial association with detected PPE objects
        if detected_ppe_items:
            res = self.associate_ppe_detections(person_bbox, detected_ppe_items)
            matched_helmet = res.matched_helmet
            matched_no_helmet = res.matched_no_helmet
            matched_vest = res.matched_vest
            matched_no_vest = res.matched_no_vest
            matched_glasses = res.matched_glasses
            matched_no_glasses = res.matched_no_glasses

        # 2. Raw Helmet Evaluation (OSHA Default: unequipped until proven compliant)
        if explicit_helmet is not None:
            raw_has_helmet = explicit_helmet
            raw_helmet_conf = 0.95
        elif matched_helmet is not None and matched_no_helmet is not None:
            if matched_helmet.confidence > (matched_no_helmet.confidence + 0.10):
                raw_has_helmet = True
                raw_helmet_conf = matched_helmet.confidence
            else:
                raw_has_helmet = False
                raw_helmet_conf = matched_no_helmet.confidence
        elif matched_helmet is not None:
            raw_has_helmet = True
            raw_helmet_conf = matched_helmet.confidence
        elif matched_no_helmet is not None:
            raw_has_helmet = False
            raw_helmet_conf = matched_no_helmet.confidence
        elif frame is not None and frame.size > 0:
            # Secondary check: High-saturation industrial safety yellow/orange hardhat check
            bx1, by1, bx2, by2 = [int(v) for v in person_bbox]
            h_img, w_img = frame.shape[:2]
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2, by2 = min(w_img, bx2), min(h_img, by2)
            head_h = int((by2 - by1) * 0.25)
            
            if head_h > 10 and bx2 > bx1:
                head_crop = frame[by1:by1 + head_h, bx1:bx2]
                try:
                    import cv2
                    hsv = cv2.cvtColor(head_crop, cv2.COLOR_BGR2HSV)
                    # Require strong industrial safety saturation (S >= 140) to never trigger on skin tone, walls, or hair
                    mask_yellow = cv2.inRange(hsv, np.array([20, 140, 130]), np.array([36, 255, 255]))
                    mask_orange = cv2.inRange(hsv, np.array([7, 160, 140]), np.array([18, 255, 255]))
                    total_px = float(head_crop.shape[0] * head_crop.shape[1])
                    ratio = (np.count_nonzero(mask_yellow) + np.count_nonzero(mask_orange)) / total_px
                    
                    if ratio >= 0.30:
                        raw_has_helmet = True
                        raw_helmet_conf = 0.65
                    else:
                        raw_has_helmet = False
                        raw_helmet_conf = 0.70
                except Exception:
                    raw_has_helmet = False
                    raw_helmet_conf = 0.60
            else:
                raw_has_helmet = False
                raw_helmet_conf = 0.60
        else:
            raw_has_helmet = False
            raw_helmet_conf = 0.60

        # 3. Raw Vest Evaluation
        if explicit_vest is not None:
            raw_has_vest = explicit_vest
            raw_vest_conf = 0.95
        elif matched_vest is not None and matched_no_vest is not None:
            if matched_vest.confidence > (matched_no_vest.confidence + 0.10):
                raw_has_vest = True
                raw_vest_conf = matched_vest.confidence
            else:
                raw_has_vest = False
                raw_vest_conf = matched_no_vest.confidence
        elif matched_vest is not None:
            raw_has_vest = True
            raw_vest_conf = matched_vest.confidence
        elif matched_no_vest is not None:
            raw_has_vest = False
            raw_vest_conf = matched_no_vest.confidence
        elif frame is not None and frame.size > 0:
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
                    # High-vis neon green/yellow and intense safety orange (strict high saturation)
                    mask_neon = cv2.inRange(hsv, np.array([30, 140, 130]), np.array([85, 255, 255]))
                    mask_orange = cv2.inRange(hsv, np.array([8, 160, 140]), np.array([18, 255, 255]))
                    total_px = float(body_crop.shape[0] * body_crop.shape[1])
                    ratio = (np.count_nonzero(mask_neon) + np.count_nonzero(mask_orange)) / total_px
                    
                    if ratio >= 0.32:
                        raw_has_vest = True
                        raw_vest_conf = 0.65
                    else:
                        raw_has_vest = False
                        raw_vest_conf = 0.70
                except Exception:
                    raw_has_vest = False
                    raw_vest_conf = 0.60
            else:
                raw_has_vest = False
                raw_vest_conf = 0.60
        else:
            raw_has_vest = False
            raw_vest_conf = 0.60

        # 4. Raw Glasses / Eye Protection Evaluation
        if explicit_glasses is not None:
            raw_has_glasses = explicit_glasses
            raw_glasses_conf = 0.95
        elif matched_glasses is not None and matched_no_glasses is not None:
            if matched_glasses.confidence > (matched_no_glasses.confidence + 0.10):
                raw_has_glasses = True
                raw_glasses_conf = matched_glasses.confidence
            else:
                raw_has_glasses = False
                raw_glasses_conf = matched_no_glasses.confidence
        elif matched_glasses is not None:
            raw_has_glasses = True
            raw_glasses_conf = matched_glasses.confidence
        elif matched_no_glasses is not None:
            raw_has_glasses = False
            raw_glasses_conf = matched_no_glasses.confidence
        elif frame is not None and frame.size > 0:
            has_g, g_conf = self.analyze_facial_glasses(frame, person_bbox)
            raw_has_glasses = has_g
            raw_glasses_conf = g_conf
        else:
            raw_has_glasses = False
            raw_glasses_conf = 0.60

        # 5. Temporal Debouncing and Confidence Smoothing
        if worker_id not in self.smoothers:
            self.smoothers[worker_id] = WorkerPPESmoother(window_size=6)
        
        has_helmet, has_vest, has_glasses, helmet_conf, vest_conf, glasses_conf = self.smoothers[worker_id].update(
            raw_helmet=raw_has_helmet,
            raw_vest=raw_has_vest,
            conf_h=raw_helmet_conf,
            conf_v=raw_vest_conf,
            now=now,
            raw_glasses=raw_has_glasses,
            conf_g=raw_glasses_conf
        )

        missing = []
        if not has_helmet:
            missing.append("HELMET")
        if not has_vest:
            missing.append("SAFETY_VEST")
        if require_glasses and not has_glasses:
            missing.append("SAFETY_GLASSES")

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
            has_glasses=has_glasses,
            helmet_confidence=helmet_conf,
            vest_confidence=vest_conf,
            glasses_confidence=glasses_conf,
            is_violation=confirmed_violation,
            missing_items=missing,
            persisted_seconds=round(persisted_time, 1),
            associated_helmet_bbox=matched_helmet.bbox if matched_helmet else None,
            associated_vest_bbox=matched_vest.bbox if matched_vest else None,
            associated_glasses_bbox=matched_glasses.bbox if matched_glasses else None,
            requires_vlm_disambiguation=requires_vlm
        )

    def cleanup_worker(self, worker_id: int):
        """Clean up state when a worker track is removed"""
        if worker_id in self.smoothers:
            del self.smoothers[worker_id]
        if worker_id in self.violation_history:
            del self.violation_history[worker_id]

    def cleanup_stale_workers(self, max_age_seconds: float = 60.0, current_time: Optional[float] = None):
        """Prune smoothers and violation history for workers not updated in max_age_seconds"""
        now = current_time or time.time()
        stale_smoothers = [
            wid for wid, sm in self.smoothers.items()
            if sm.last_updated and (now - sm.last_updated > max_age_seconds)
        ]
        for wid in stale_smoothers:
            self.smoothers.pop(wid, None)

        stale_violations = [
            wid for wid, v in self.violation_history.items()
            if now - v.get("last_seen", now) > max_age_seconds
        ]
        for wid in stale_violations:
            self.violation_history.pop(wid, None)

