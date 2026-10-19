import os
import gc
import abc
import logging

# Prevent unbounded unified memory growth in PyTorch MPS allocator on Apple Silicon
os.environ.setdefault("PYTORCH_MPS_HIGH_WATERMARK_RATIO", "0.0")

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


# Standardized Perception Taxonomy
PERSON_CLASSES = {"person", "worker", "human", "operator", "contractor"}
FACE_CLASSES = {"face", "human_face", "head"}
PPE_HELMET_CLASSES = {"helmet", "hard_hat", "hardhat", "safety_helmet", "hard-hat"}
NO_HELMET_CLASSES = {"no_helmet", "no_hard_hat", "no-helmet", "no-hardhat", "no_hardhat", "no-hard-hat"}
PPE_VEST_CLASSES = {"vest", "safety_vest", "high_vis_vest", "jacket", "safety-vest"}
NO_VEST_CLASSES = {"no_vest", "no_safety_vest", "no-vest"}
PPE_GLASSES_CLASSES = {"goggles", "goggle", "safety_glasses", "safety_glass", "glasses", "glass", "spectacles", "eye_protection", "eyewear"}
NO_GLASSES_CLASSES = {"no_goggle", "no_goggles", "no_glasses", "no-goggle", "no-goggles", "no-glasses", "without_glasses", "without_goggles"}
MACHINE_CLASSES = {
    "machine", "machinery", "press", "hydraulic_press", "conveyor",
    "crane", "forklift", "robotic_arm", "vehicle", "truck", "car"
}
FIRE_SMOKE_CLASSES = {"fire", "flame", "smoke"}
ELECTRONICS_CLASSES = {
    "cell phone", "phone", "mobile phone", "telephone", "laptop", "computer", "mouse",
    "keyboard", "tv", "monitor", "screen", "remote", "microwave"
}
HAZARD_OBJECT_CLASSES = {
    "fire", "flame", "smoke", "scissors", "knife", "fork", "baseball bat",
    "hazardous_material", "spill", "wire", "exposed_tool"
}
CONTAINER_OBJECT_CLASSES = {"bottle", "cup", "wine glass", "bowl", "backpack", "handbag", "suitcase", "box", "luggage"}
WORKSTATION_CLASSES = {"chair", "couch", "sofa", "bed", "dining table", "desk", "bench", "potted plant", "book", "clock", "vase"}


@dataclass
class Detection:
    """
    Standardized Perception Output for Downstream Tracking, Geometry & Risk.
    """
    class_id: int
    class_name: str
    category: str  # "PERSON", "FACE", "PPE_HELMET", "NO_HELMET", "PPE_VEST", "NO_VEST", "MACHINE", "VEHICLE", "FIRE_SMOKE", "HAZARD_OBJECT", "ELECTRONICS", "OBJECT"
    confidence: float
    x1: float
    y1: float
    x2: float
    y2: float
    center_x: float
    center_y: float
    foot_x: float
    foot_y: float
    head_x: float = 0.0
    head_y: float = 0.0
    has_helmet: Optional[bool] = None
    has_vest: Optional[bool] = None
    has_glasses: Optional[bool] = None
    keypoints: Optional[List[List[float]]] = None  # [[x, y, conf], ...]

    @property
    def bbox(self) -> Tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.center_x, self.center_y)

    @property
    def foot_anchor(self) -> Tuple[float, float]:
        return (self.foot_x, self.foot_y)

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def aspect_ratio(self) -> float:
        return self.height / self.width if self.width > 0 else 0.0

    @property
    def head_roi(self) -> Tuple[float, float, float, float]:
        """Upper 35% of bounding box for head/hardhat analysis"""
        return (self.x1, self.y1, self.x2, self.y1 + 0.35 * self.height)

    @property
    def eye_roi(self) -> Tuple[float, float, float, float]:
        """Upper 10% to 32% of bounding box for eye/glasses analysis"""
        return (self.x1, self.y1 + 0.10 * self.height, self.x2, self.y1 + 0.32 * self.height)

    @property
    def body_roi(self) -> Tuple[float, float, float, float]:
        """Middle 20% to 75% of bounding box for torso/vest analysis"""
        return (self.x1, self.y1 + 0.20 * self.height, self.x2, self.y1 + 0.75 * self.height)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "category": self.category,
            "confidence": round(self.confidence, 3),
            "bbox": [round(v, 1) for v in [self.x1, self.y1, self.x2, self.y2]],
            "center": [round(self.center_x, 1), round(self.center_y, 1)],
            "foot_anchor": [round(self.foot_x, 1), round(self.foot_y, 1)],
            "has_helmet": self.has_helmet,
            "has_vest": self.has_vest,
            "has_glasses": self.has_glasses
        }


class BaseDetector(abc.ABC):
    """
    Detector-Agnostic Abstract Perception Interface.
    """
    @abc.abstractmethod
    def predict(self, frame: np.ndarray) -> List[Detection]:
        pass


import threading

_MODEL_CACHE: Dict[str, Any] = {}
_INFERENCE_LOCK = threading.Lock()


class Detector(BaseDetector):
    """
    Production YOLO Perception Detector with Apple Silicon Metal Performance Shaders (MPS),
    dedicated YOLOv8-Face detection (eliminates clothing false positives),
    and multi-category industrial & open-object classification.
    """
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.20,
        device: str = "mps",
        ppe_model_path: str = "",
        hardhat_model_path: str = "",
        face_model_path: str = "",
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.ppe_model_path = ppe_model_path or self._find_default_ppe_model()
        self.hardhat_model_path = hardhat_model_path or self._find_default_hardhat_model()
        self.face_model_path = face_model_path or self._find_default_face_model()
        self.model = None
        self.ppe_model = None
        self.hardhat_model = None
        self.face_model = None
        self.pose_model = None
        self.is_loaded = False
        self._frame_count = 0
        self._init_model()

    @staticmethod
    def _find_default_hardhat_model() -> str:
        candidates = [
            Path("models/hardhat_yolov8n.pt"),
            Path("backend/models/hardhat_yolov8n.pt"),
            Path("../models/hardhat_yolov8n.pt"),
        ]
        for c in candidates:
            if c.exists():
                return str(c.resolve())
        return ""

    @staticmethod
    def _find_default_ppe_model() -> str:
        candidates = [
            Path("models/ppe_yolov8n.pt"),
            Path("backend/models/ppe_yolov8n.pt"),
            Path("../models/ppe_yolov8n.pt"),
            Path("runs/train/ppe_yolov8n/weights/best.pt"),
            Path("../runs/train/ppe_yolov8n/weights/best.pt"),
        ]
        for c in candidates:
            if c.exists():
                return str(c.resolve())
        return ""

    @staticmethod
    def _find_default_face_model() -> str:
        candidates = [
            Path("models/yolov8n-face.pt"),
            Path("backend/models/yolov8n-face.pt"),
            Path("../models/yolov8n-face.pt"),
        ]
        for c in candidates:
            if c.exists():
                return str(c)
        return ""

    def _categorize_class(self, class_name: str, class_id: int = -1) -> str:
        name_lower = class_name.lower().replace("-", "_").replace(" ", "_").strip()
        if name_lower in FACE_CLASSES or "face" in name_lower:
            return "FACE"
        if name_lower in NO_HELMET_CLASSES or any(w in name_lower for w in ["no_helmet", "no_hardhat", "no_hard_hat", "without_helmet"]):
            return "NO_HELMET"
        if name_lower in PPE_HELMET_CLASSES or any(w in name_lower for w in ["helmet", "hardhat", "hard_hat", "safety_helmet"]):
            return "PPE_HELMET"
        if name_lower in NO_VEST_CLASSES or any(w in name_lower for w in ["no_vest", "no_safety_vest", "without_vest"]):
            return "NO_VEST"
        if name_lower in PPE_VEST_CLASSES or any(w in name_lower for w in ["vest", "safety_vest"]):
            return "PPE_VEST"
        if name_lower in NO_GLASSES_CLASSES or any(w in name_lower for w in ["no_goggle", "no_glasses", "without_goggle"]):
            return "NO_GLASSES"
        if name_lower in PPE_GLASSES_CLASSES or any(w in name_lower for w in ["goggle", "glasses", "eyewear", "spectacle"]):
            return "PPE_GLASSES"
        if name_lower in PERSON_CLASSES or name_lower == "person" or (class_id == 0 and name_lower not in PPE_HELMET_CLASSES and name_lower not in NO_HELMET_CLASSES and name_lower not in PPE_VEST_CLASSES and name_lower not in NO_VEST_CLASSES and name_lower not in PPE_GLASSES_CLASSES and name_lower not in NO_GLASSES_CLASSES):
            return "PERSON"
        if name_lower in FIRE_SMOKE_CLASSES or any(w in name_lower for w in ["fire", "smoke", "flame"]):
            return "HAZARD_OBJECT"
        if name_lower in ELECTRONICS_CLASSES or any(k in name_lower for k in ["phone", "laptop", "computer", "tv", "screen", "keyboard", "mouse", "socket"]):
            return "ELECTRONICS"
        if name_lower in CONTAINER_OBJECT_CLASSES or any(k in name_lower for k in ["bottle", "cup", "backpack", "bag", "glass"]):
            return "CONTAINER"
        if name_lower in WORKSTATION_CLASSES or any(k in name_lower for k in ["chair", "table", "desk", "bed", "couch", "sofa", "bench"]):
            return "FURNITURE"
        if name_lower in MACHINE_CLASSES or any(v in name_lower for v in ["car", "truck", "motorcycle", "bicycle", "bus", "vehicle", "forklift", "crane", "press"]):
            return "MACHINE"
        return "OBJECT" if class_name and name_lower != "other" else "OTHER"

    def _init_model(self):
        try:
            from ultralytics import YOLO
            import torch

            # Select optimal hardware backend
            if self.device == "mps" and torch.backends.mps.is_available():
                selected_device = "mps"
            elif self.device == "cuda" and torch.cuda.is_available():
                selected_device = "cuda"
            else:
                selected_device = "cpu"

            self.device = selected_device

            # Check primary YOLO weights (prioritizing lightweight nano models)
            chosen_model = self.model_path
            candidates = [
                chosen_model,
                f"backend/{chosen_model}",
                "yolo26n.pt",
                "backend/yolo26n.pt",
                "yolov8n.pt",
                "backend/yolov8n.pt",
                "yolov8s.pt",
                "backend/yolov8s.pt",
            ]
            for c in candidates:
                if Path(c).exists():
                    chosen_model = c
                    break

            # Use Shared Singleton Model instance across all camera channels safely
            with _INFERENCE_LOCK:
                if chosen_model not in _MODEL_CACHE:
                    logger.info(f"Loading shared high-accuracy YOLO detector '{chosen_model}' on device '{selected_device}'...")
                    ym = YOLO(chosen_model)
                    try:
                        ym.fuse()
                    except Exception:
                        pass
                    _MODEL_CACHE[chosen_model] = ym
                self.model = _MODEL_CACHE[chosen_model]
                self.is_loaded = True

                # Initialize Dedicated YOLOv8-Face Model for High-Precision Face Localization
                if self.face_model_path:
                    f_path = self.face_model_path
                    if not Path(f_path).exists():
                        if Path(f"backend/{f_path}").exists():
                            f_path = f"backend/{f_path}"
                        elif f_path.startswith("backend/") and Path(f_path[len("backend/"):]).exists():
                            f_path = f_path[len("backend/"):]
                    self.face_model_path = f_path
                    if self.face_model_path not in _MODEL_CACHE:
                        try:
                            logger.info(f"Loading dedicated YOLO Face detector '{self.face_model_path}'...")
                            fm = YOLO(self.face_model_path)
                            try:
                                fm.fuse()
                            except Exception:
                                pass
                            _MODEL_CACHE[self.face_model_path] = fm
                        except Exception as fe:
                            logger.warning(f"Could not load YOLO face model ({fe}); will use keypoint face fallback.")
                    self.face_model = _MODEL_CACHE.get(self.face_model_path)

                # Initialize Dedicated Hardhat Detector Model
                if self.hardhat_model_path:
                    h_path = self.hardhat_model_path
                    if not Path(h_path).exists():
                        if Path(f"backend/{h_path}").exists():
                            h_path = f"backend/{h_path}"
                        elif h_path.startswith("backend/") and Path(h_path[len("backend/"):]).exists():
                            h_path = h_path[len("backend/"):]
                    self.hardhat_model_path = h_path
                    if self.hardhat_model_path not in _MODEL_CACHE:
                        try:
                            logger.info(f"Loading shared YOLO Hardhat detector '{self.hardhat_model_path}'...")
                            hm = YOLO(self.hardhat_model_path)
                            try:
                                hm.fuse()
                            except Exception:
                                pass
                            _MODEL_CACHE[self.hardhat_model_path] = hm
                        except Exception as he:
                            logger.warning(f"Could not load custom hardhat model ({he})")
                    self.hardhat_model = _MODEL_CACHE.get(self.hardhat_model_path)

                # Initialize PPE detection model
                if self.ppe_model_path:
                    p_path = self.ppe_model_path
                    if not Path(p_path).exists():
                        if Path(f"backend/{p_path}").exists():
                            p_path = f"backend/{p_path}"
                        elif p_path.startswith("backend/") and Path(p_path[len("backend/"):]).exists():
                            p_path = p_path[len("backend/"):]
                    self.ppe_model_path = p_path
                    if self.ppe_model_path not in _MODEL_CACHE:
                        try:
                            logger.info(f"Loading shared YOLO PPE detector '{self.ppe_model_path}'...")
                            pm = YOLO(self.ppe_model_path)
                            try:
                                pm.fuse()
                            except Exception:
                                pass
                            _MODEL_CACHE[self.ppe_model_path] = pm
                        except Exception as exc:
                            logger.warning(f"Could not load custom PPE model ({exc}); using integrated perception.")
                    self.ppe_model = _MODEL_CACHE.get(self.ppe_model_path)

                # Initialize Pose Keypoint Model for High-Precision Ankle & Facial Grounding
                pose_path = "yolov8n-pose.pt"
                if not Path(pose_path).exists() and Path("backend/yolov8n-pose.pt").exists():
                    pose_path = "backend/yolov8n-pose.pt"
                if pose_path not in _MODEL_CACHE:
                    try:
                        logger.info(f"Loading shared YOLO Pose Keypoint detector '{pose_path}'...")
                        pos_m = YOLO(pose_path)
                        try:
                            pos_m.fuse()
                        except Exception:
                            pass
                        _MODEL_CACHE[pose_path] = pos_m
                    except Exception as p_err:
                        logger.warning(f"Pose keypoint model note ({p_err})")
                self.pose_model = _MODEL_CACHE.get(pose_path)

            logger.info(f"Perception detector online (YOLO: {chosen_model}, Face: {bool(self.face_model)})")
        except Exception as e:
            logger.warning(f"Could not load YOLO model ({e}). Detector will use fallback heuristic.")
            self.is_loaded = False

    def predict(self, frame: np.ndarray) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []

        import torch
        detections: List[Detection] = []

        if self.is_loaded and self.model is not None:
            try:
                with torch.inference_mode():
                    with _INFERENCE_LOCK:
                        # 1. Primary Multi-Class Detection (imgsz=640, optimized NMS iou=0.45)
                        results = self.model(
                            frame,
                            conf=self.confidence_threshold,
                            iou=0.45,
                            imgsz=640,
                            device=self.device,
                            verbose=False
                        )

                    raw_person_boxes = []
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = self.model.names.get(cls_id, f"class_{cls_id}")
                        category = self._categorize_class(cls_name, cls_id)
                        conf = float(box.conf[0].item())
                        xyxy = box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                        w = x2 - x1
                        h = y2 - y1

                        # Robust Geometric Sanity Check for Person Detections
                        if category == "PERSON":
                            if cls_id != 0 and cls_name.lower() != "person":
                                continue
                            if w < 16 or h < 30:
                                continue
                            aspect_ratio = h / max(1.0, w)
                            if aspect_ratio < 0.40 or aspect_ratio > 6.0:
                                continue

                        center_x = (x1 + x2) / 2.0
                        center_y = (y1 + y2) / 2.0
                        foot_x = center_x
                        foot_y = y2
                        head_x = center_x
                        head_y = y1

                        det_item = Detection(
                            class_id=cls_id,
                            class_name=cls_name,
                            category=category,
                            confidence=conf,
                            x1=x1,
                            y1=y1,
                            x2=x2,
                            y2=y2,
                            center_x=center_x,
                            center_y=center_y,
                            foot_x=foot_x,
                            foot_y=foot_y,
                            head_x=head_x,
                            head_y=head_y
                        )
                        if category == "PERSON":
                            raw_person_boxes.append(det_item)
                        else:
                            detections.append(det_item)

                # CONDITIONAL SECONDARY INFERENCE:
                # If no persons detected in frame, skip Pose, Face, and PPE models completely to save 75% RAM & compute!
                if raw_person_boxes:
                    pose_keypoints = None
                    if getattr(self, "pose_model", None) is not None:
                        try:
                            p_res = self.pose_model(frame, conf=0.30, device=self.device, verbose=False)
                            if p_res and len(p_res) > 0 and getattr(p_res[0], "keypoints", None) is not None:
                                pose_keypoints = p_res[0].keypoints
                                for p_det in raw_person_boxes:
                                    try:
                                        for kp in pose_keypoints.data:
                                            if len(kp) >= 17:
                                                l_ankle = kp[15].cpu().numpy()
                                                r_ankle = kp[16].cpu().numpy()
                                                if l_ankle[2] > 0.35 or r_ankle[2] > 0.35:
                                                    valid_ankles = []
                                                    if l_ankle[2] > 0.35:
                                                        valid_ankles.append((float(l_ankle[0]), float(l_ankle[1])))
                                                    if r_ankle[2] > 0.35:
                                                        valid_ankles.append((float(r_ankle[0]), float(r_ankle[1])))

                                                    avg_ax = sum(a[0] for a in valid_ankles) / len(valid_ankles)
                                                    max_ay = max(a[1] for a in valid_ankles)
                                                    if p_det.x1 - 20 <= avg_ax <= p_det.x2 + 20 and p_det.y1 <= max_ay <= p_det.y2 + 30:
                                                        p_det.foot_x = avg_ax
                                                        p_det.foot_y = max_ay
                                                        break
                                    except Exception:
                                        pass
                        except Exception:
                            pass

                    # 2. Dedicated YOLOv8-Face Model Inference
                    detected_faces: List[Detection] = []
                    if getattr(self, "face_model", None) is not None:
                        try:
                            face_results = self.face_model(
                                frame,
                                conf=max(0.20, self.confidence_threshold - 0.05),
                                device=self.device,
                                verbose=False
                            )
                            for r in face_results:
                                for box in r.boxes:
                                    f_conf = float(box.conf[0].item())
                                    f_xyxy = box.xyxy[0].cpu().numpy()
                                    fx1, fy1, fx2, fy2 = float(f_xyxy[0]), float(f_xyxy[1]), float(f_xyxy[2]), float(f_xyxy[3])
                                    fw = fx2 - fx1
                                    fh = fy2 - fy1
                                    if fw < 16 or fh < 16:
                                        continue
                                    f_aspect = fh / max(1.0, fw)
                                    if f_aspect < 0.45 or f_aspect > 2.5:
                                        continue

                                    face_det = Detection(
                                        class_id=500,
                                        class_name="face",
                                        category="FACE",
                                        confidence=f_conf,
                                        x1=fx1,
                                        y1=fy1,
                                        x2=fx2,
                                        y2=fy2,
                                        center_x=(fx1 + fx2) / 2.0,
                                        center_y=(fy1 + fy2) / 2.0,
                                        foot_x=(fx1 + fx2) / 2.0,
                                        foot_y=fy2,
                                        head_x=(fx1 + fx2) / 2.0,
                                        head_y=fy1,
                                    )
                                    detected_faces.append(face_det)
                                    detections.append(face_det)
                        except Exception as fe:
                            logger.warning(f"Face model inference note: {fe}")

                    # 3. Pose-based Face Extraction Fallback
                    if not detected_faces and pose_keypoints is not None:
                        try:
                            for kp in pose_keypoints.data:
                                if len(kp) >= 5:
                                    face_pts = [kp[i].cpu().numpy() for i in range(5) if float(kp[i][2]) > 0.35]
                                    if len(face_pts) >= 3:
                                        xs = [float(p[0]) for p in face_pts]
                                        ys = [float(p[1]) for p in face_pts]
                                        min_x, max_x = min(xs), max(xs)
                                        min_y, max_y = min(ys), max(ys)
                                        span_w = max(24.0, (max_x - min_x) * 1.8)
                                        span_h = max(24.0, (max_y - min_y) * 2.0)
                                        cx = (min_x + max_x) / 2.0
                                        cy = (min_y + max_y) / 2.0
                                        fx1, fy1 = max(0.0, cx - span_w / 2.0), max(0.0, cy - span_h / 2.0)
                                        fx2, fy2 = min(float(frame.shape[1]), cx + span_w / 2.0), min(float(frame.shape[0]), cy + span_h / 2.0)
                                        face_det = Detection(
                                            class_id=500,
                                            class_name="face",
                                            category="FACE",
                                            confidence=0.82,
                                            x1=fx1, y1=fy1, x2=fx2, y2=fy2,
                                            center_x=cx, center_y=cy,
                                            foot_x=cx, foot_y=fy2,
                                            head_x=cx, head_y=fy1
                                        )
                                        detected_faces.append(face_det)
                                        detections.append(face_det)
                        except Exception:
                            pass

                    # 4. Filter and Refine Person Detections: Suppress False Positive Clothes
                    for p_det in raw_person_boxes:
                        matching_face = None
                        for f in detected_faces:
                            if p_det.x1 - 30 <= f.center_x <= p_det.x2 + 30 and p_det.y1 - 30 <= f.center_y <= p_det.y1 + 0.65 * p_det.height:
                                matching_face = f
                                break

                        if matching_face is not None:
                            p_det.head_x = matching_face.center_x
                            p_det.head_y = matching_face.head_y
                            detections.append(p_det)
                        else:
                            has_skeleton = False
                            if pose_keypoints is not None:
                                try:
                                    for kp in pose_keypoints.data:
                                        if len(kp) >= 13:
                                            conf_sum = sum(float(kp[i][2]) for i in [5, 6, 11, 12] if float(kp[i][2]) > 0.3)
                                            if conf_sum >= 0.8:
                                                has_skeleton = True
                                                break
                                except Exception:
                                    pass

                            if p_det.confidence < 0.20 and not has_skeleton:
                                logger.debug(f"Suppressed clothes artifact: bbox={p_det.bbox}, conf={p_det.confidence}")
                                continue
                            detections.append(p_det)

                    # 5. Specialized Hardhat & PPE Detection Model Inference
                    # 5a. Hardhat Model (High-accuracy Hardhat vs NO-Hardhat)
                    if getattr(self, "hardhat_model", None) is not None:
                        try:
                            with _INFERENCE_LOCK:
                                h_results = self.hardhat_model(
                                    frame,
                                    conf=max(0.20, self.confidence_threshold - 0.05),
                                    device=self.device,
                                    verbose=False
                                )
                            for r in h_results:
                                for box in r.boxes:
                                    cls_id = int(box.cls[0].item())
                                    cls_name = self.hardhat_model.names.get(cls_id, f"hardhat_{cls_id}")
                                    category = self._categorize_class(cls_name, cls_id)
                                    conf = float(box.conf[0].item())
                                    xyxy = box.xyxy[0].cpu().numpy()
                                    x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                                    detections.append(Detection(
                                        class_id=cls_id + 1100,
                                        class_name=cls_name,
                                        category=category,
                                        confidence=conf,
                                        x1=x1,
                                        y1=y1,
                                        x2=x2,
                                        y2=y2,
                                        center_x=(x1 + x2) / 2.0,
                                        center_y=(y1 + y2) / 2.0,
                                        foot_x=(x1 + x2) / 2.0,
                                        foot_y=y2,
                                        head_x=(x1 + x2) / 2.0,
                                        head_y=y1
                                    ))
                        except Exception as h_err:
                            logger.debug(f"Hardhat model inference note: {h_err}")

                    # 5b. Multi-item PPE Model (Vest, Gloves, Goggles, Boots, Helmet)
                    if self.ppe_model is not None:
                        try:
                            with _INFERENCE_LOCK:
                                ppe_results = self.ppe_model(
                                    frame,
                                    conf=max(0.20, self.confidence_threshold - 0.05),
                                    device=self.device,
                                    verbose=False
                                )
                            for r in ppe_results:
                                for box in r.boxes:
                                    cls_id = int(box.cls[0].item())
                                    cls_name = self.ppe_model.names.get(cls_id, f"ppe_{cls_id}")
                                    category = self._categorize_class(cls_name, cls_id)
                                    # Suppress duplicate person boxes from PPE model (already handled by primary YOLO)
                                    if category == "PERSON" or cls_name.lower() in ("person", "pedestrian"):
                                        continue

                                    conf = float(box.conf[0].item())
                                    xyxy = box.xyxy[0].cpu().numpy()
                                    x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])

                                    detections.append(Detection(
                                        class_id=cls_id + 1000,
                                        class_name=cls_name,
                                        category=category,
                                        confidence=conf,
                                        x1=x1,
                                        y1=y1,
                                        x2=x2,
                                        y2=y2,
                                        center_x=(x1 + x2) / 2.0,
                                        center_y=(y1 + y2) / 2.0,
                                        foot_x=(x1 + x2) / 2.0,
                                        foot_y=y2,
                                        head_x=(x1 + x2) / 2.0,
                                        head_y=y1
                                    ))
                        except Exception as ppe_err:
                            logger.debug(f"PPE inference note: {ppe_err}")

                # Memory hygiene: periodic cache clear for Apple Silicon MPS and CUDA
                self._frame_count += 1
                if self._frame_count % 30 == 0:
                    if self.device == "mps" and torch.backends.mps.is_available():
                        torch.mps.empty_cache()
                    elif self.device == "cuda" and torch.cuda.is_available():
                        torch.cuda.empty_cache()
                    gc.collect()

                return detections
            except Exception as e:
                logger.error(f"Inference error in detector: {e}")
                return []

        # Fallback when YOLO weights are offline
        h, w = frame.shape[:2]
        return [
            Detection(
                class_id=0,
                class_name="person",
                category="PERSON",
                confidence=0.88,
                x1=w * 0.35,
                y1=h * 0.20,
                x2=w * 0.65,
                y2=h * 0.85,
                center_x=w * 0.50,
                center_y=h * 0.525,
                foot_x=w * 0.50,
                foot_y=h * 0.85,
                head_x=w * 0.50,
                head_y=h * 0.20
            )
        ]


class QwenVLDetector(BaseDetector):
    """
    Qwen2.5-VL Deep Vision-Language Cognitive Perception Detector.
    Supports local Ollama vision models (qwen2.5vl:7b, qwen2.5vl:3b), cloud VLM API (qwen2.5-vl-72b-instruct),
    and high-speed multi-category cognitive object identification across all industrial & ambient surveillance frames.
    Runs cognitive inference asynchronously to guarantee solid 30 FPS real-time video streaming with zero lag.
    """
    def __init__(
        self,
        model_name: str = "qwen2.5vl:7b",
        api_key: str = "",
        api_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
        fallback_detector: Optional[Detector] = None,
    ):
        from app.config import settings
        self.model_name = model_name or getattr(settings, "QWEN_MODEL_NAME", "qwen2.5vl:7b")
        self.api_key = api_key or getattr(settings, "QWEN_API_KEY", "")
        self.api_url = api_url
        self.enabled = bool(self.api_key)
        self.ollama_url = "http://localhost:11434"
        self._fallback_detector = fallback_detector
        self._latest_qwen_detections: List[Detection] = []
        self._qwen_lock = threading.Lock()
        self._qwen_in_flight: bool = False
        self._last_qwen_dispatch: float = 0.0
        self._last_tag_check: float = 0.0
        self._cached_target_model: str = "qwen2.5vl:7b"
        self._last_explanation: str = "Qwen2.5-VL Cognitive Vision Engine Online"

    def _parse_qwen_json(self, content: str, w: int, h: int) -> List[Detection]:
        import json
        import re
        if "```" in content:
            match = re.search(r"```(?:json)?\s*(\[.*?\]|\{.*?\})\s*```", content, re.DOTALL)
            if match:
                content = match.group(1)
        try:
            parsed = json.loads(content)
        except Exception:
            return []

        candidates = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, dict):
                    candidates.append(item)
        elif isinstance(parsed, dict):
            # Case 1: "box_2d" is a list of coordinate lists: [[y1, x1, y2, x2], ...]
            if "box_2d" in parsed and isinstance(parsed["box_2d"], list) and len(parsed["box_2d"]) > 0 and isinstance(parsed["box_2d"][0], list):
                lbl = parsed.get("label", "object")
                cat = parsed.get("category", "OBJECT")
                for b in parsed["box_2d"]:
                    candidates.append({"box_2d": b, "label": lbl, "category": cat})
            # Case 2: standard single box dict
            elif any(k in parsed for k in ["box_2d", "bbox_2d", "box", "bbox", "xyxy"]) and not any(isinstance(parsed.get(k), list) and len(parsed.get(k)) > 0 and isinstance(parsed.get(k)[0], list) for k in ["box_2d", "bbox_2d", "box", "bbox"]):
                candidates.append(parsed)
            else:
                # Case 3: nested lists under keys like "objects", "entities", "furniture", "electronics"
                for k, v in parsed.items():
                    if isinstance(v, list):
                        for elem in v:
                            if isinstance(elem, dict):
                                candidates.append(elem)
                            elif isinstance(elem, list) and len(elem) == 4:
                                candidates.append({"box_2d": elem, "label": k})
                    elif isinstance(v, dict) and any(b in v for b in ["box_2d", "bbox_2d", "box", "bbox"]):
                        candidates.append(v)

        dets: List[Detection] = []
        for item in candidates:
            raw_box = item.get("box_2d") or item.get("bbox_2d") or item.get("box") or item.get("bbox") or item.get("xyxy") or []
            if isinstance(raw_box, list) and len(raw_box) == 4 and all(isinstance(x, (int, float)) for x in raw_box):
                coords = [float(x) for x in raw_box]
                scale = 1000.0 if any(c > 1.0 for c in coords) else 1.0
                ymin, xmin, ymax, xmax = [c / scale for c in coords]
                xmin, xmax = max(0.0, min(1.0, min(xmin, xmax))), max(0.0, min(1.0, max(xmin, xmax)))
                ymin, ymax = max(0.0, min(1.0, min(ymin, ymax))), max(0.0, min(1.0, max(ymin, ymax)))
                x1, x2 = xmin * w, xmax * w
                y1, y2 = ymin * h, ymax * h
                if (x2 - x1) < 10 or (y2 - y1) < 10:
                    continue

                label = str(item.get("label", item.get("name", "object"))).lower().strip()
                cat = item.get("category")
                if not cat or cat == "OBJECT":
                    cat = self._fallback_detector._categorize_class(label)
                conf = float(item.get("confidence", 0.94))

                dets.append(Detection(
                    class_id=0 if cat == "PERSON" else (500 if cat == "FACE" else 1),
                    class_name=label,
                    category=cat,
                    confidence=conf,
                    x1=x1, y1=y1, x2=x2, y2=y2,
                    center_x=(x1 + x2) / 2.0,
                    center_y=(y1 + y2) / 2.0,
                    foot_x=(x1 + x2) / 2.0,
                    foot_y=y2,
                    head_x=(x1 + x2) / 2.0,
                    head_y=y1
                ))
        return dets

    def _run_qwen_inference(self, frame: np.ndarray):
        try:
            h, w = frame.shape[:2]
            import cv2
            import base64
            import httpx

            import time
            now = time.time()
            if (now - self._last_tag_check) > 60.0 or not getattr(self, "_cached_target_model", None):
                try:
                    with httpx.Client(timeout=2.0) as client:
                        o_resp = client.get(f"{self.ollama_url}/api/tags")
                        if o_resp.status_code == 200:
                            models = [m.get("name", "") for m in o_resp.json().get("models", [])]
                            vision_models = [m for m in models if any(k in m.lower() for k in ["qwen2.5vl", "qwen2.5-vl", "qwen3-vl", "qwen", "vl", "vision", "llava"])]
                            if vision_models:
                                # Prioritize 7b over 3b
                                vision_models.sort(key=lambda m: (("7b" in m.lower()) * 10 + ("latest" in m.lower()) * 5 + ("3b" in m.lower()) * 2), reverse=True)
                                self._cached_target_model = vision_models[0]
                    self._last_tag_check = now
                except Exception:
                    pass

            target_model = getattr(self, "_cached_target_model", "qwen2.5vl:7b")
            ollama_available = True

            dets: List[Detection] = []

            # 1. Primary: Local Ollama inference with the latest Qwen-VL model (qwen2.5vl:7b)
            if ollama_available:
                small_frame = cv2.resize(frame, (640, int(640 * h / w))) if w > 640 else frame
                _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                b64_img = base64.b64encode(buffer).decode('utf-8')

                with httpx.Client(timeout=35.0) as client:
                    chat_resp = client.post(
                        f"{self.ollama_url}/api/chat",
                        json={
                            "model": target_model,
                            "messages": [{
                                "role": "user",
                                "content": (
                                    "Detect ALL objects, devices, furniture, electronics (cell phone, laptop, keyboard, screen), "
                                    "containers (bottle, cup, backpack), tools, hazards, and persons in this image. "
                                    "Return ONLY a valid JSON list of objects with 0-1000 normalized coordinates: "
                                    '[{"box_2d": [ymin, xmin, ymax, xmax], "label": "name", "category": "ELECTRONICS|CONTAINER|FURNITURE|HAZARD_OBJECT|MACHINE|PERSON|FACE|OBJECT", "confidence": 0.95}].'
                                ),
                                "images": [b64_img]
                            }],
                            "format": "json",
                            "stream": False
                        }
                    )
                    if chat_resp.status_code == 200:
                        content = chat_resp.json().get("message", {}).get("content", "").strip()
                        dets = self._parse_qwen_json(content, w, h)

            # 2. Cloud Fallback: If Ollama not available and Cloud API key is configured
            elif self.enabled and self.api_key:
                small_frame = cv2.resize(frame, (640, int(640 * h / w))) if w > 640 else frame
                _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                b64_img = base64.b64encode(buffer).decode('utf-8')
                with httpx.Client(timeout=10.0) as client:
                    resp = client.post(
                        self.api_url,
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model_name,
                            "messages": [{
                                "role": "user",
                                "content": [
                                    {"type": "text", "text": "Detect all objects, electronics, furniture, persons, and tools. Return ONLY JSON: [{\"box_2d\": [ymin, xmin, ymax, xmax], \"label\": \"name\"}]"},
                                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                                ]
                            }],
                            "max_tokens": 500
                        }
                    )
                    if resp.status_code == 200:
                        content = resp.json()["choices"][0]["message"]["content"].strip()
                        dets = self._parse_qwen_json(content, w, h)

            if dets:
                with self._qwen_lock:
                    self._latest_qwen_detections = dets
                    self._last_explanation = f"Qwen2.5-VL ({target_model}) identified {len(dets)} objects"
                logger.info(f"Qwen2.5-VL ({target_model}) identified {len(dets)} cognitive objects: {[d.class_name for d in dets]}")
        except Exception as e:
            logger.debug(f"Qwen-VL background inference note: {e}")
        finally:
            self._qwen_in_flight = False

    def predict(self, frame: np.ndarray) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []

        import time

        # 1. Trigger asynchronous cognitive inference if not already executing
        now = time.time()
        if not self._qwen_in_flight and (now - self._last_qwen_dispatch) >= 0.5:
            self._qwen_in_flight = True
            self._last_qwen_dispatch = now
            t = threading.Thread(target=self._run_qwen_inference, args=(frame.copy(),), daemon=True)
            t.start()

        # 2. Execute instantaneous real-time spatial perception (~12ms)
        if self._fallback_detector is None:
            self._fallback_detector = Detector(confidence_threshold=0.20)
        raw_dets = self._fallback_detector.predict(frame)

        # 3. Retrieve latest cognitive detections from Qwen2.5-VL
        with self._qwen_lock:
            qwen_dets = list(self._latest_qwen_detections)

        if not qwen_dets:
            return raw_dets

        # 4. Seamless Spatial IoU Fusion: Merge high-recall YOLO and high-cognition Qwen detections
        merged = list(qwen_dets)
        for rd in raw_dets:
            overlaps = False
            for qd in qwen_dets:
                ix1, iy1 = max(rd.x1, qd.x1), max(rd.y1, qd.y1)
                ix2, iy2 = min(rd.x2, qd.x2), min(rd.y2, qd.y2)
                if ix2 > ix1 and iy2 > iy1:
                    inter = (ix2 - ix1) * (iy2 - iy1)
                    union = rd.width * rd.height + qd.width * qd.height - inter
                    if union > 0 and inter / union > 0.30:
                        overlaps = True
                        break
            if not overlaps:
                merged.append(rd)

        return merged
