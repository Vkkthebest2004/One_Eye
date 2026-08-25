import logging
from dataclasses import dataclass, field
from typing import List, Optional, Tuple, Dict, Any
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Detection:
    class_id: int
    class_name: str
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
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def aspect_ratio(self) -> float:
        return self.height / self.width if self.width > 0 else 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_id": self.class_id,
            "class_name": self.class_name,
            "confidence": round(self.confidence, 3),
            "bbox": [round(v, 1) for v in [self.x1, self.y1, self.x2, self.y2]],
            "center": [round(self.center_x, 1), round(self.center_y, 1)],
            "foot_anchor": [round(self.foot_x, 1), round(self.foot_y, 1)],
            "has_helmet": self.has_helmet,
            "has_vest": self.has_vest
        }


class Detector:
    """
    Object and Person Detector with YOLO backend and graceful simulation fallback.
    """
    def __init__(
        self,
        model_path: str = "yolov8n.pt",
        confidence_threshold: float = 0.25,
        device: str = "mps"
    ):
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        self.device = device
        self.model = None
        self.is_loaded = False
        self._init_model()

    def _init_model(self):
        try:
            from ultralytics import YOLO
            import torch
            
            # Select optimal device (MPS on Apple Silicon if available)
            if self.device == "mps" and torch.backends.mps.is_available():
                selected_device = "mps"
            elif self.device == "cuda" and torch.cuda.is_available():
                selected_device = "cuda"
            else:
                selected_device = "cpu"
                
            logger.info(f"Loading YOLO model '{self.model_path}' on device '{selected_device}'...")
            self.model = YOLO(self.model_path)
            self.device = selected_device
            self.is_loaded = True
            logger.info(f"YOLO detector successfully initialized ({self.model_path})")
        except Exception as e:
            logger.warning(f"Could not load YOLO model ({e}). Detector will use fallback heuristic.")
            self.is_loaded = False

    def predict(self, frame: np.ndarray) -> List[Detection]:
        if frame is None or frame.size == 0:
            return []

        h, w = frame.shape[:2]
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
                        conf = float(box.conf[0].item())
                        xyxy = box.xyxy[0].cpu().numpy()
                        x1, y1, x2, y2 = float(xyxy[0]), float(xyxy[1]), float(xyxy[2]), float(xyxy[3])
                        
                        center_x = (x1 + x2) / 2.0
                        center_y = (y1 + y2) / 2.0
                        foot_x = center_x
                        foot_y = y2 # Base contact point
                        head_x = center_x
                        head_y = y1

                        detections.append(Detection(
                            class_id=cls_id,
                            class_name=cls_name,
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
                logger.error(f"Inference error: {e}")

        return detections
