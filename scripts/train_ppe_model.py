#!/usr/bin/env python3
"""
ONE EYE — Specialized Safety Equipment (Helmet & Vest) YOLOv8 Training Pipeline.
Fine-tunes YOLOv8n on the Ultralytics Construction-PPE dataset.
Saves the optimized model to models/ppe_yolov8n.pt for real-time edge inference.
"""

import os
import sys
import shutil
import logging
from pathlib import Path

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TrainPPE")

# Ensure repository root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

def train_ppe_model(
    epochs: int = 5,
    imgsz: int = 640,
    batch: int = 16,
    base_model: str = "yolov8n.pt"
):
    import torch
    from ultralytics import YOLO

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info(f"🚀 Initializing PPE training on device: {device.upper()}")

    data_yaml = PROJECT_ROOT / "datasets" / "construction-ppe" / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(f"data.yaml not found at {data_yaml}")

    # Load base pretrained model
    base_path = PROJECT_ROOT / base_model
    if not base_path.exists():
        base_path = Path(base_model)
    
    logger.info(f"Loading base weights: {base_path}")
    model = YOLO(str(base_path))

    # Output directory
    output_dir = PROJECT_ROOT / "runs" / "train" / "ppe_yolov8n"
    if output_dir.exists():
        shutil.rmtree(output_dir)

    logger.info(f"Starting training for {epochs} epochs (batch={batch}, imgsz={imgsz})...")
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=imgsz,
        batch=batch,
        device=device,
        workers=2,
        project=str(PROJECT_ROOT / "runs" / "train"),
        name="ppe_yolov8n",
        exist_ok=True,
        verbose=True,
        save=True,
        val=True,
        plots=True,
        # Optimal hyper-parameters for transfer learning
        lr0=0.01,
        lrf=0.01,
        momentum=0.937,
        weight_decay=0.0005,
        warmup_epochs=1.0,
        box=7.5,
        cls=0.5,
        dfl=1.5,
    )

    # Locate best weights
    best_weights = PROJECT_ROOT / "runs" / "train" / "ppe_yolov8n" / "weights" / "best.pt"
    if not best_weights.exists():
        best_weights = PROJECT_ROOT / "runs" / "train" / "ppe_yolov8n" / "weights" / "last.pt"

    target_dir = PROJECT_ROOT / "models"
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / "ppe_yolov8n.pt"

    if best_weights.exists():
        shutil.copy(best_weights, target_path)
        logger.info(f"✅ Best weights saved to: {target_path}")
    else:
        logger.warning(f"Could not locate trained weights at {best_weights}")

    # Validate model
    logger.info("Evaluating validation metrics on test split...")
    val_model = YOLO(str(target_path if target_path.exists() else base_path))
    val_metrics = val_model.val(data=str(data_yaml), device=device, verbose=False)

    print("\n" + "=" * 65)
    print("  🏆 TRAINING & VALIDATION SUMMARY: SAFETY EQUIPMENT (PPE)")
    print("=" * 65)
    print(f"Target Model: {target_path}")
    print(f"Device: {device.upper()}")
    print(f"Trained Epochs: {epochs}")
    print(f"mAP@50 (All Classes): {val_metrics.box.map50:.4f}")
    print(f"mAP@50-95 (All Classes): {val_metrics.box.map:.4f}")
    
    # Class-specific metrics
    names = val_metrics.names
    print("\n--- Per-Class Metrics ---")
    for i, cls_name in names.items():
        if i < len(val_metrics.box.p):
            p = val_metrics.box.p[i]
            r = val_metrics.box.r[i]
            map50 = val_metrics.box.ap50[i]
            if cls_name.lower() in ("helmet", "vest", "no_helmet", "person"):
                print(f" • {cls_name:<12}: Precision={p:.3f}, Recall={r:.3f}, mAP@50={map50:.3f}")

    print("=" * 65 + "\n")
    return target_path

if __name__ == "__main__":
    train_ppe_model(epochs=5, imgsz=640, batch=16)
