import abc
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


# Standardized Perception Taxonomy
PERSON_CLASSES = {"person", "worker", "human", "operator", "contractor"}
PPE_HELMET_CLASSES = {"helmet", "hard_hat", "hardhat", "safety_helmet", "hat"}
PPE_VEST_CLASSES = {"vest", "safety_vest", "high_vis_vest", "jacket"}
MACHINE_CLASSES = {
    "machine", "machinery", "press", "hydraulic_press", "conveyor",
    "crane", "forklift", "robotic_arm", "vehicle", "truck", "car"
}
FIRE_SMOKE_CLASSES = {"fire", "flame", "smoke"}


@dataclass
class Detection:
    """
    Standardized Perception Output for Downstream Tracking, Geometry & Risk.
    """
    class_id: int
    class_name: str
    category: str # "PERSON", "PPE_HELMET", "PPE_VEST", "MACHINE", "VEHICLE", "FIRE_SMOKE", "OTHER"
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
    keypoints: Optional[List[List[float]]] = None # [[x, y, conf], ...]

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
            "has_vest": self.has_vest
        }


class BaseDetector(abc.ABC):
    """
    Detector-Agnostic Abstract Perception Interface.
    Allows seamlessly hot-swapping YOLOv8, YOLO11, ONNX Runtime, or RT-DETR
    without modifying downstream tracking, geometry, or risk evaluation.
    """
    @abc.abstractmethod
    def predict(self, frame: np.ndarray) -> List[Detection]:
        pass


class Detector(BaseDetector):
    """
    Production YOLO Perception Detector with Apple Silicon Metal Performance Shaders (MPS),
    CUDA, and multi-category industrial classification.
    """
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.25,
        device: str = "mps",
        ppe_model_path: str = "",
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.ppe_model_path = ppe_model_path
        self.model = None
        self.ppe_model = None
        self.is_loaded = False
        self._init_model()

    def _categorize_class(self, class_name: str) -> str:
        name_lower = class_name.lower().replace("-", "_").replace(" ", "_")
        if name_lower in PERSON_CLASSES:
            return "PERSON"
        if name_lower in PPE_HELMET_CLASSES:
            return "PPE_HELMET"
        if name_lower in PPE_VEST_CLASSES:
            return "PPE_VEST"
        if name_lower in MACHINE_CLASSES:
            return "MACHINE"
        if name_lower in FIRE_SMOKE_CLASSES:
            return "FIRE_SMOKE"
        return "OTHER"

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
                
            logger.info(f"Initializing YOLO detector '{self.model_path}' on device '{selected_device}'...")
            self.model = YOLO(self.model_path)
            self.device = selected_device
            self.is_loaded = True
            
            if self.ppe_model_path:
                try:
                    logger.info(f"Loading specialized PPE detector '{self.ppe_model_path}'...")
                    self.ppe_model = YOLO(self.ppe_model_path)
                except Exception as exc:
                    logger.warning(f"Could not load custom PPE model ({exc}); using integrated perception.")
            
            logger.info(f"YOLO detector successfully online ({self.model_path})")
        except Exception as e:
            logger.warning(f"Could not load YOLO model ({e}). Detector will use fallback heuristic.")
            self.is_loaded = False

    def predict(self, frame: np.ndarray) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []

        detections: List[Detection] = []

        if self.is_loaded and self.model is not None:
            try:
                results = self.model(
                    frame,
                    conf=self.confidence_threshold,
                    device=self.device,
                    verbose=False
                )
                
                for r in results:
                    boxes = r.boxes
                    for box in boxes:
                        cls_id = int(box.cls[0].item())
                        cls_name = self.model.names.get(cls_id, f"class_{cls_id}")
                        category = self._categorize_class(cls_name)
                        conf = float(box.conf[0].item())
                        xyxy = box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                        
                        center_x = (x1 + x2) / 2.0
                        center_y = (y1 + y2) / 2.0
                        foot_x = center_x
                        foot_y = y2 # Base contact point on ground plane
                        head_x = center_x
                        head_y = y1

                        detections.append(Detection(
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
                        ))
                return detections
            except Exception as e:
                logger.error(f"Inference error in detector: {e}")
                return []

        # Fallback Heuristic when YOLO weights are missing / simulation
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
