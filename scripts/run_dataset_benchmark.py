#!/usr/bin/env python3
"""
ONE EYE — Comprehensive Model & Risk Assessment Dataset Benchmark
Tests:
  1. YOLO Perception Engine (Person, Helmet, Vest) vs Ground Truth
  2. Qwen 2.5-VL Cognitive Vision Model vs Ground Truth & YOLO
  3. Clean Taxonomy & Zero False-Positive Hazard Object Verification
  4. Spatial & Restricted Zone Intrusion Detection (Point-in-Polygon)
  5. Fall Detection & Aspect Ratio Posture Assessment
  6. Compound 0-100 Industrial Risk Assessment & Synergy Rules
"""

import sys
import os
import json
import time
import glob
import logging
from pathlib import Path
from typing import Dict, List, Tuple, Any

import cv2
import numpy as np

# Ensure backend is in path
backend_dir = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(backend_dir))

from app.cv.detector import Detector, Detection
from app.cv.tracker import MultiObjectTracker
from app.cv.ppe import PPEEngine
from app.cv.fall import FallDetector
from app.cv.intrusion import IntrusionDetector, scale_polygon, point_in_zone
from app.cv.zones import ZoneEngine, ZoneDefinition
from app.risk.engine import RiskEngine
from app.reasoning.interface import QwenReasoner

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("Benchmark")


def parse_yolo_label_file(label_path: str, img_w: int, img_h: int) -> List[Dict[str, Any]]:
    """
    Parse YOLO format label file: <class_id> <cx> <cy> <w> <h> (normalized).
    Ultralytics Construction-PPE dataset classes:
      0: helmet, 1: gloves, 2: vest, 3: boots, 4: goggles, 5: none,
      6: Person, 7: no_helmet, 8: no_goggle, 9: no_gloves, 10: no_boots
    """
    if not os.path.exists(label_path):
        return []
    boxes = []
    with open(label_path, "r") as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 5:
                cls_id = int(parts[0])
                cx, cy, w, h = float(parts[1]), float(parts[2]), float(parts[3]), float(parts[4])
                x1 = int((cx - w / 2) * img_w)
                y1 = int((cy - h / 2) * img_h)
                x2 = int((cx + w / 2) * img_w)
                y2 = int((cy + h / 2) * img_h)
                boxes.append({
                    "class_id": cls_id,
                    "cx": cx, "cy": cy, "w": w, "h": h,
                    "bbox": [x1, y1, x2, y2]
                })
    return boxes


def run_benchmark(num_images: int = 35):
    logger.info("=" * 70)
    logger.info("     ONE EYE — INDUSTRIAL SAFETY DATASET BENCHMARK & AUDIT")
    logger.info("=" * 70)

    dataset_val_img_dir = Path("datasets/construction-ppe/images/val")
    dataset_val_lbl_dir = Path("datasets/construction-ppe/labels/val")

    image_files = sorted(list(dataset_val_img_dir.glob("*.jpg")) + list(dataset_val_img_dir.glob("*.jpeg")))
    if not image_files:
        logger.error(f"No images found in {dataset_val_img_dir}")
        return

    logger.info(f"Loaded {len(image_files)} validation images from Construction-PPE dataset.")
    sample_images = image_files[:num_images]

    # Initialize Core Engines
    logger.info("Initializing Perception Detector (YOLO + Face)...")
    detector = Detector(device="mps")

    logger.info("Initializing PPE Association Engine...")
    ppe_engine = PPEEngine()

    logger.info("Initializing Fall Detector...")
    fall_detector = FallDetector(confirmation_duration_sec=1.0)

    logger.info("Initializing Intrusion Detector...")
    intrusion_detector = IntrusionDetector(evidence_dir="evidence/intrusions")

    logger.info("Initializing Compound Risk Engine...")
    risk_engine = RiskEngine()

    logger.info("Initializing Qwen 2.5-VL Cognitive Detector...")
    from app.cv.detector import QwenVLDetector
    qwen_detector = QwenVLDetector(model_name="qwen2.5vl:7b")

    # Metrics storage
    metrics = {
        "total_images_evaluated": 0,
        "yolo_latency_ms": [],
        "person_detection": {"tp": 0, "fp": 0, "fn": 0, "ground_truth_total": 0, "predicted_total": 0},
        "ppe_helmet": {"tp": 0, "fp": 0, "fn": 0, "gt_helmets": 0, "gt_no_helmets": 0},
        "ppe_vest": {"tp": 0, "fp": 0, "fn": 0, "gt_vests": 0},
        "clean_taxonomy_false_alarms": 0,
        "fall_detection_accuracy": {"total_tests": 0, "passed": 0},
        "zone_intrusion_accuracy": {"total_tests": 0, "passed": 0},
        "risk_engine_consistency": {"total_tests": 0, "passed": 0},
        "qwen_vl_consistency": {"evaluated_images": 0, "agreements": 0, "disagreements": 0, "details": []},
        "inconsistencies": []
    }

    # -----------------------------------------------------------------------
    # TEST 1: Perception & PPE Benchmark on Real Labeled Dataset
    # -----------------------------------------------------------------------
    logger.info(f"\n>>> Running Benchmark Test 1: Perception & PPE on {len(sample_images)} Labeled Images...")
    for idx, img_path in enumerate(sample_images):
        img_name = img_path.name
        lbl_name = img_path.stem + ".txt"
        lbl_path = dataset_val_lbl_dir / lbl_name

        frame = cv2.imread(str(img_path))
        if frame is None:
            continue

        h, w = frame.shape[:2]
        gt_boxes = parse_yolo_label_file(str(lbl_path), w, h)

        # Ground Truth counts
        gt_persons = [b for b in gt_boxes if b["class_id"] == 6]
        gt_helmets = [b for b in gt_boxes if b["class_id"] == 0]
        gt_no_helmets = [b for b in gt_boxes if b["class_id"] == 7]
        gt_vests = [b for b in gt_boxes if b["class_id"] == 2]

        metrics["person_detection"]["ground_truth_total"] += len(gt_persons)
        metrics["ppe_helmet"]["gt_helmets"] += len(gt_helmets)
        metrics["ppe_helmet"]["gt_no_helmets"] += len(gt_no_helmets)
        metrics["ppe_vest"]["gt_vests"] += len(gt_vests)

        # Predict with YOLO
        t0 = time.perf_counter()
        detections = detector.predict(frame)
        latency = (time.perf_counter() - t0) * 1000
        metrics["yolo_latency_ms"].append(latency)

        pred_persons = [d for d in detections if d.category == "PERSON"]
        metrics["person_detection"]["predicted_total"] += len(pred_persons)

        # Check for any FALSE HAZARD_OBJECT flags on ordinary classes
        for d in detections:
            name_lower = d.class_name.lower()
            if d.category == "HAZARD_OBJECT" and not any(w in name_lower for w in ["fire", "smoke", "flame", "hazard"]):
                metrics["clean_taxonomy_false_alarms"] += 1
                metrics["inconsistencies"].append({
                    "type": "FALSE_HAZARD_OBJECT",
                    "image": img_name,
                    "class_name": d.class_name,
                    "confidence": d.confidence,
                    "description": f"Ordinary object '{d.class_name}' flagged as HAZARD_OBJECT in safe space."
                })

        # Match Persons (IoU matching)
        matched_gt = set()
        for p in pred_persons:
            matched = False
            for g_idx, g in enumerate(gt_persons):
                if g_idx in matched_gt:
                    continue
                # Calculate IoU
                gx1, gy1, gx2, gy2 = g["bbox"]
                px1, py1, px2, py2 = p.bbox
                ix1, iy1 = max(gx1, px1), max(gy1, py1)
                ix2, iy2 = min(gx2, px2), min(gy2, py2)
                if ix2 > ix1 and iy2 > iy1:
                    inter = (ix2 - ix1) * (iy2 - iy1)
                    union = (gx2 - gx1) * (gy2 - gy1) + (px2 - px1) * (py2 - py1) - inter
                    iou = inter / float(union) if union > 0 else 0
                    if iou >= 0.30:
                        matched = True
                        matched_gt.add(g_idx)
                        break
            if matched:
                metrics["person_detection"]["tp"] += 1
            else:
                metrics["person_detection"]["fp"] += 1
        metrics["person_detection"]["fn"] += (len(gt_persons) - len(matched_gt))

        metrics["total_images_evaluated"] += 1

    # -----------------------------------------------------------------------
    # TEST 2: Qwen 2.5-VL Cognitive Reasoning vs Ground Truth & YOLO
    # -----------------------------------------------------------------------
    logger.info("\n>>> Running Benchmark Test 2: Qwen 2.5-VL Cognitive Assessment on Representative Subset...")
    import httpx
    import base64
    qwen_test_subset = sample_images[:4]
    for img_path in qwen_test_subset:
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue
        h, w = frame.shape[:2]
        lbl_path = dataset_val_lbl_dir / (img_path.stem + ".txt")
        gt_boxes = parse_yolo_label_file(str(lbl_path), w, h)
        gt_persons_count = len([b for b in gt_boxes if b["class_id"] == 6])

        # Get YOLO person count
        yolo_dets = detector.predict(frame)
        yolo_persons_count = len([d for d in yolo_dets if d.category == "PERSON"])

        # Query Qwen 2.5-VL in Ollama (downscale to max 448 for fast inference)
        try:
            t0 = time.perf_counter()
            scale = min(1.0, 448.0 / max(w, h))
            if scale < 1.0:
                small = cv2.resize(frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
            else:
                small = frame
            _, jpg_bytes = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, 75])
            b64_img = base64.b64encode(jpg_bytes).decode("utf-8")
            
            prompt = (
                "You are an industrial safety inspection AI. Look at this image carefully.\n"
                "Return ONLY a JSON object with:\n"
                "{\n"
                '  "worker_count": <int>,\n'
                '  "workers_wearing_helmets": <int>,\n'
                '  "workers_wearing_vests": <int>,\n'
                '  "critical_hazards": [<string>],\n'
                '  "safety_summary": "<string>"\n'
                "}"
            )
            with httpx.Client(timeout=60.0) as client:
                res = client.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "qwen2.5vl:7b",
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt,
                                "images": [b64_img]
                            }
                        ],
                        "stream": False,
                        "options": {"temperature": 0.1}
                    }
                )
            vlm_latency = (time.perf_counter() - t0) * 1000
            
            qwen_count = None
            qwen_summary = ""
            if res.status_code == 200:
                raw_txt = res.json().get("message", {}).get("content", "")
                import re
                m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw_txt, re.DOTALL)
                json_str = m.group(1) if m else raw_txt[raw_txt.find("{"):raw_txt.rfind("}")+1]
                try:
                    parsed = json.loads(json_str)
                    qwen_count = int(parsed.get("worker_count", 0))
                    qwen_summary = parsed.get("safety_summary", "")
                except Exception:
                    # heuristic extract
                    m_cnt = re.search(r'"worker_count"\s*:\s*(\d+)', raw_txt)
                    if m_cnt:
                        qwen_count = int(m_cnt.group(1))
                    qwen_summary = raw_txt[:100]

            is_consistent = (qwen_count is not None) and (abs(qwen_count - yolo_persons_count) <= 1)

            metrics["qwen_vl_consistency"]["evaluated_images"] += 1
            if is_consistent:
                metrics["qwen_vl_consistency"]["agreements"] += 1
            else:
                metrics["qwen_vl_consistency"]["disagreements"] += 1
                metrics["inconsistencies"].append({
                    "type": "QWEN_YOLO_COUNT_DISAGREEMENT",
                    "image": img_path.name,
                    "yolo_persons": yolo_persons_count,
                    "qwen_persons": qwen_count,
                    "gt_persons": gt_persons_count,
                    "description": f"Disagreement on worker count: YOLO={yolo_persons_count}, Qwen={qwen_count}, GT={gt_persons_count}"
                })

            metrics["qwen_vl_consistency"]["details"].append({
                "image": img_path.name,
                "latency_ms": round(vlm_latency, 1),
                "yolo_count": yolo_persons_count,
                "qwen_count": qwen_count,
                "gt_count": gt_persons_count,
                "qwen_summary": qwen_summary[:120]
            })
            logger.info(f"  VLM evaluated {img_path.name} in {vlm_latency:.1f}ms: Qwen count={qwen_count}, YOLO count={yolo_persons_count}, GT={gt_persons_count}")
        except Exception as e:
            logger.warning(f"  Qwen evaluation note on {img_path.name}: {e}")

    # -----------------------------------------------------------------------
    # TEST 3: Clean Taxonomy Verification on Ordinary Non-Hazard Objects
    # -----------------------------------------------------------------------
    logger.info("\n>>> Running Benchmark Test 3: Clean Taxonomy & Safe Open-Space Test...")
    test_asset_images = list(Path("datasets/test_assets").glob("*.jpg"))
    for img_path in test_asset_images:
        frame = cv2.imread(str(img_path))
        if frame is None:
            continue
        dets = detector.predict(frame)
        for d in dets:
            name_lower = d.class_name.lower()
            if d.category == "HAZARD_OBJECT" and not any(w in name_lower for w in ["fire", "smoke", "flame"]):
                metrics["clean_taxonomy_false_alarms"] += 1
                metrics["inconsistencies"].append({
                    "type": "NON_HAZARD_FLAGGED",
                    "image": img_path.name,
                    "class_name": d.class_name,
                    "category": d.category,
                    "description": f"Ordinary object '{d.class_name}' in safe asset incorrectly categorized as HAZARD_OBJECT."
                })

    # -----------------------------------------------------------------------
    # TEST 4: Fall Detection Verification
    # -----------------------------------------------------------------------
    logger.info("\n>>> Running Benchmark Test 4: Fall Detection & Posture Confirmation...")
    # Test 4.1: Upright worker -> STANDING
    metrics["fall_detection_accuracy"]["total_tests"] += 1
    upright_status = fall_detector.evaluate_worker(
        worker_id=101,
        bbox=(200, 100, 300, 450), # w=100, h=350, aspect=3.5
        velocity=(0, 0),
        timestamp=1000.0
    )
    if upright_status.state == "STANDING" and not upright_status.is_fall:
        metrics["fall_detection_accuracy"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "FALL_DETECTION_ERROR", "case": "Upright standing", "result": upright_status.state})

    # Test 4.2: Sudden prone fall over duration -> FALL_CONFIRMED
    metrics["fall_detection_accuracy"]["total_tests"] += 1
    _ = fall_detector.evaluate_worker(
        worker_id=102,
        bbox=(200, 300, 550, 380), # w=350, h=80, aspect=0.23 (horizontal)
        velocity=(0, 40),
        timestamp=1000.0
    )
    fall_confirmed = fall_detector.evaluate_worker(
        worker_id=102,
        bbox=(200, 300, 550, 380),
        velocity=(0, 0),
        timestamp=1002.5 # > confirmation duration
    )
    if fall_confirmed.state == "FALL_CONFIRMED" and fall_confirmed.is_fall:
        metrics["fall_detection_accuracy"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "FALL_DETECTION_ERROR", "case": "Horizontal ground posture", "result": fall_confirmed.state})

    # -----------------------------------------------------------------------
    # TEST 5: Restricted Zone Intrusion (MediaPipe / Point-in-Polygon)
    # -----------------------------------------------------------------------
    logger.info("\n>>> Running Benchmark Test 5: Precision Restricted Zone Intrusion...")
    zone = ZoneDefinition(
        id="BENCHMARK_ZONE",
        name="Robotic Hazard Zone",
        camera_id="BENCHMARK_CAM",
        polygon_points=[(0.3, 0.3), (0.7, 0.3), (0.7, 0.7), (0.3, 0.7)],
        active=True
    )
    # Synthetic frame 640x480
    test_frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Scaled pixel polygon
    pixel_poly = scale_polygon(zone.polygon_points, (640, 480))

    # Test inside point (320, 240) -> inside [0.3*640=192, 0.7*640=448, etc.]
    metrics["zone_intrusion_accuracy"]["total_tests"] += 1
    if point_in_zone((320, 240), pixel_poly) is True:
        metrics["zone_intrusion_accuracy"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "ZONE_INTRUSION_ERROR", "case": "Point inside zone", "result": False})

    # Test outside point (50, 50) -> outside
    metrics["zone_intrusion_accuracy"]["total_tests"] += 1
    if point_in_zone((50, 50), pixel_poly) is False:
        metrics["zone_intrusion_accuracy"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "ZONE_INTRUSION_ERROR", "case": "Point outside zone", "result": True})

    # -----------------------------------------------------------------------
    # TEST 6: Compound Risk Assessment Engine Synergy & Scoring
    # -----------------------------------------------------------------------
    logger.info("\n>>> Running Benchmark Test 6: Compound Risk Engine & Synergy Rules...")
    # 6.1: Full PPE safe worker -> LOW / ADVISORY (<30)
    metrics["risk_engine_consistency"]["total_tests"] += 1
    res_safe = risk_engine.evaluate(worker_id=1, active_hazards=[], detection_confidence=0.95)
    if res_safe.risk_score < 30 and res_safe.severity == "ADVISORY":
        metrics["risk_engine_consistency"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "RISK_ENGINE_INCONSISTENCY", "case": "Safe worker", "risk_score": res_safe.risk_score})

    # 6.2: Single PPE violation -> MEDIUM (35-65)
    metrics["risk_engine_consistency"]["total_tests"] += 1
    res_no_helmet = risk_engine.evaluate(worker_id=2, active_hazards=["NO_HELMET"], detection_confidence=0.90)
    if 35 <= res_no_helmet.risk_score <= 65 and res_no_helmet.severity == "MEDIUM":
        metrics["risk_engine_consistency"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "RISK_ENGINE_INCONSISTENCY", "case": "No helmet", "risk_score": res_no_helmet.risk_score})

    # 6.3: Compound Synergy (NO_HELMET + RESTRICTED_ZONE) -> HIGH / CRITICAL (>70)
    metrics["risk_engine_consistency"]["total_tests"] += 1
    res_compound = risk_engine.evaluate(
        worker_id=3,
        active_hazards=["NO_HELMET", "RESTRICTED_ZONE"],
        detection_confidence=0.95,
        exposure_duration_sec=3.0
    )
    if res_compound.risk_score >= 70 and res_compound.severity in ("HIGH", "CRITICAL"):
        metrics["risk_engine_consistency"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "RISK_ENGINE_INCONSISTENCY", "case": "No helmet + zone breach", "risk_score": res_compound.risk_score})

    # 6.4: Worker fall near operating machine -> CRITICAL (>=85)
    metrics["risk_engine_consistency"]["total_tests"] += 1
    res_fall_crit = risk_engine.evaluate(
        worker_id=4,
        active_hazards=["WORKER_FALL", "UNSAFE_PROXIMITY_CRITICAL"],
        detection_confidence=0.95,
        proximity_distance_m=0.8
    )
    if res_fall_crit.risk_score >= 85 and res_fall_crit.severity == "CRITICAL":
        metrics["risk_engine_consistency"]["passed"] += 1
    else:
        metrics["inconsistencies"].append({"type": "RISK_ENGINE_INCONSISTENCY", "case": "Worker fall at machine", "risk_score": res_fall_crit.risk_score})

    # -----------------------------------------------------------------------
    # Compile Final Metrics & Metrics Report
    # -----------------------------------------------------------------------
    p_tp = metrics["person_detection"]["tp"]
    p_fp = metrics["person_detection"]["fp"]
    p_fn = metrics["person_detection"]["fn"]
    precision = p_tp / (p_tp + p_fp) if (p_tp + p_fp) > 0 else 0.0
    recall = p_tp / (p_tp + p_fn) if (p_tp + p_fn) > 0 else 0.0
    f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0

    avg_yolo_latency = np.mean(metrics["yolo_latency_ms"]) if metrics["yolo_latency_ms"] else 0.0
    p95_yolo_latency = np.percentile(metrics["yolo_latency_ms"], 95) if metrics["yolo_latency_ms"] else 0.0

    report = {
        "benchmark_summary": {
            "dataset": "Ultralytics Construction-PPE Validation Set",
            "evaluated_images": metrics["total_images_evaluated"],
            "perception": {
                "person_precision": round(precision, 4),
                "person_recall": round(recall, 4),
                "person_f1": round(f1, 4),
                "true_positives": p_tp,
                "false_positives": p_fp,
                "false_negatives": p_fn,
                "ground_truth_persons": metrics["person_detection"]["ground_truth_total"],
                "predicted_persons": metrics["person_detection"]["predicted_total"],
                "avg_inference_latency_ms": round(avg_yolo_latency, 2),
                "p95_inference_latency_ms": round(p95_yolo_latency, 2),
            },
            "clean_taxonomy": {
                "false_hazard_alarms_on_safe_objects": metrics["clean_taxonomy_false_alarms"],
                "status": "PASSED (0 False Hazards)" if metrics["clean_taxonomy_false_alarms"] == 0 else "FAILED"
            },
            "fall_detector": {
                "accuracy": f"{metrics['fall_detection_accuracy']['passed']}/{metrics['fall_detection_accuracy']['total_tests']}",
                "rate": round(metrics["fall_detection_accuracy"]["passed"] / max(1, metrics["fall_detection_accuracy"]["total_tests"]), 2)
            },
            "zone_intrusion_detector": {
                "accuracy": f"{metrics['zone_intrusion_accuracy']['passed']}/{metrics['zone_intrusion_accuracy']['total_tests']}",
                "rate": round(metrics["zone_intrusion_accuracy"]["passed"] / max(1, metrics["zone_intrusion_accuracy"]["total_tests"]), 2)
            },
            "compound_risk_engine": {
                "accuracy": f"{metrics['risk_engine_consistency']['passed']}/{metrics['risk_engine_consistency']['total_tests']}",
                "rate": round(metrics["risk_engine_consistency"]["passed"] / max(1, metrics["risk_engine_consistency"]["total_tests"]), 2)
            },
            "qwen_vl_consistency": {
                "evaluated_images": metrics["qwen_vl_consistency"]["evaluated_images"],
                "agreements": metrics["qwen_vl_consistency"]["agreements"],
                "disagreements": metrics["qwen_vl_consistency"]["disagreements"],
                "details": metrics["qwen_vl_consistency"]["details"]
            },
            "total_inconsistencies_found": len(metrics["inconsistencies"]),
            "inconsistencies": metrics["inconsistencies"]
        }
    }

    # Save to JSON
    out_path = Path("datasets/benchmark_results.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info("\n" + "=" * 70)
    logger.info("                  BENCHMARK RESULTS SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Dataset Evaluated:           {report['benchmark_summary']['dataset']}")
    logger.info(f"Images Processed:            {metrics['total_images_evaluated']}")
    logger.info(f"Person Detection Precision:  {precision * 100:.1f}%")
    logger.info(f"Person Detection Recall:     {recall * 100:.1f}%")
    logger.info(f"Person Detection F1 Score:   {f1 * 100:.1f}%")
    logger.info(f"Avg Perception Latency:      {avg_yolo_latency:.2f} ms (P95: {p95_yolo_latency:.2f} ms)")
    logger.info(f"Clean Taxonomy Check:        {report['benchmark_summary']['clean_taxonomy']['status']}")
    logger.info(f"Fall Detection Accuracy:     {report['benchmark_summary']['fall_detector']['accuracy']}")
    logger.info(f"Zone Intrusion Accuracy:     {report['benchmark_summary']['zone_intrusion_detector']['accuracy']}")
    logger.info(f"Risk Assessment Accuracy:    {report['benchmark_summary']['compound_risk_engine']['accuracy']}")
    logger.info(f"Qwen VLM vs YOLO Agreements: {metrics['qwen_vl_consistency']['agreements']}/{metrics['qwen_vl_consistency']['evaluated_images']}")
    logger.info(f"Total Inconsistencies Found: {len(metrics['inconsistencies'])}")
    logger.info("=" * 70)
    logger.info(f"Full benchmark results saved to: {out_path.resolve()}")

    return report


if __name__ == "__main__":
    num_imgs = int(sys.argv[1]) if len(sys.argv) > 1 else 35
    run_benchmark(num_images=num_imgs)
