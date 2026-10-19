#!/usr/bin/env python3
"""
ONE EYE — Real-Life Industrial Safety Scenario Simulation Test Harness.

Simulates dynamic industrial shift operations with realistic temporal events:
Phase 1: Shift Routine & Authorized Transit (All Clear, 0 alarms)
Phase 2: Routine Maintenance with PPE Non-Compliance (Advisory Warning)
Phase 3: Real-Life Non-Hazard Action (Crouching / Bending with keypoint spine angle validation)
Phase 4: Spatial Danger Zone Breach & Critical Machine Proximity (Synergy Escalation)
Phase 5: Acute Incident (True Worker Slip & Fall inside Danger Zone -> Max Emergency)
Phase 6: Emergency Response, Evacuation & Incident Resolution Lifecycle
Cognitive Tier: Qwen 2.5-VL root-cause analysis on incident frame.
"""

import sys
import time
import math
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Tuple
import numpy as np
import cv2

# Configure root paths
root_dir = Path(__file__).resolve().parent.parent
backend_dir = root_dir / "backend"
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(backend_dir))

from app.cv.detector import Detector, Detection
from app.cv.ppe import PPEEngine, PPEItem
from app.cv.fall import FallDetector, FallStatus
from app.cv.intrusion import IntrusionDetector
from app.cv.exposure import ExposureTracker
from app.cv.zones import ZoneEngine, ZoneDefinition
from app.risk.engine import RiskEngine
from app.risk.thresholds import RiskThresholds
from app.events.state_machine import EventStateMachine, EventState

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RealLifeSimulation")


def create_mock_keypoints(shoulder_mid: Tuple[float, float], hip_mid: Tuple[float, float], ankle_mid: Tuple[float, float]) -> List[List[float]]:
    """Generate synthetic 17-point COCO keypoints matching specified body anchors"""
    kpts = [[0.0, 0.0, 0.9] for _ in range(17)]
    # 0: nose
    kpts[0] = [shoulder_mid[0], shoulder_mid[1] - 30.0, 0.9]
    # 5: left shoulder, 6: right shoulder
    kpts[5] = [shoulder_mid[0] - 25.0, shoulder_mid[1], 0.95]
    kpts[6] = [shoulder_mid[0] + 25.0, shoulder_mid[1], 0.95]
    # 11: left hip, 12: right hip
    kpts[11] = [hip_mid[0] - 20.0, hip_mid[1], 0.95]
    kpts[12] = [hip_mid[0] + 20.0, hip_mid[1], 0.95]
    # 15: left ankle, 16: right ankle
    kpts[15] = [ankle_mid[0] - 15.0, ankle_mid[1], 0.9]
    kpts[16] = [ankle_mid[0] + 15.0, ankle_mid[1], 0.9]
    return kpts


def run_simulation() -> Dict[str, Any]:
    logger.info("=" * 75)
    logger.info("  ONE EYE — REAL-LIFE INDUSTRIAL SHIFT SAFETY SIMULATION")
    logger.info("=" * 75)

    # 1. Initialize Engines
    logger.info("Initializing Core Intelligence Engines...")
    detector = Detector(device="mps")
    ppe_engine = PPEEngine()
    fall_detector = FallDetector(confirmation_duration_sec=1.5)
    zone_engine = ZoneEngine()
    risk_engine = RiskEngine()
    exposure_tracker = ExposureTracker(inactivity_timeout_sec=3.0)

    # Register Hydraulic Press Danger Zone
    press_zone = ZoneDefinition(
        id="ZONE_PRESS_01",
        name="Hydraulic Stamping Press Danger Perimeter",
        camera_id="CAM_FACTORY_01",
        polygon_points=[(0.40, 0.40), (0.85, 0.40), (0.85, 0.85), (0.40, 0.85)],
        severity="CRITICAL",
        active=True
    )
    zone_engine.register_zone(press_zone)

    results = {
        "simulation_title": "End-to-End Factory Floor Shift Lifecycle",
        "phases_executed": 6,
        "phase_results": {},
        "all_passed": True,
        "inconsistencies": []
    }

    sim_start = 10000.0

    # -------------------------------------------------------------------------
    # PHASE 1: Shift Routine & Authorized Transit (All Clear)
    # -------------------------------------------------------------------------
    logger.info("\n>>> PHASE 1: Normal Authorized Transit (Worker #101)")
    p1_passed = True
    # Worker 101 walks along safe aisle (x=0.15, y=0.50), full PPE, safe machine distance (3.5m)
    p1_kpts = create_mock_keypoints(shoulder_mid=(150, 200), hip_mid=(150, 320), ankle_mid=(150, 450))
    p1_fall = fall_detector.evaluate_worker(
        worker_id=101,
        bbox=(100, 150, 200, 460),
        velocity=(0, 0),
        keypoints=p1_kpts,
        timestamp=sim_start
    )
    # Zone check (foot at 150, 450 in 1000x1000 frame -> 0.15, 0.45)
    p1_zone_events = zone_engine.evaluate_worker(
        worker_id=101,
        foot_x=150,
        foot_y=450,
        timestamp=sim_start,
        camera_id="CAM_FACTORY_01",
        frame_w=1000,
        frame_h=1000
    )
    p1_in_zone = any(ze.state in ("ENTERED", "INSIDE") for ze in p1_zone_events)
    p1_assessment = risk_engine.evaluate(
        worker_id=101,
        active_hazards=[],
        proximity_distance_m=3.5,
        detection_confidence=0.96
    )

    if p1_fall.is_fall:
        p1_passed = False
        results["inconsistencies"].append("Phase 1: False fall detected on upright worker.")
    if p1_in_zone:
        p1_passed = False
        results["inconsistencies"].append("Phase 1: False zone intrusion outside perimeter.")
    if p1_assessment.risk_score > 25 or p1_assessment.severity != "ADVISORY":
        p1_passed = False
        results["inconsistencies"].append(f"Phase 1: Expected Advisory risk score, got {p1_assessment.risk_score}")

    results["phase_results"]["Phase 1: Authorized Transit"] = {
        "passed": p1_passed,
        "risk_score": p1_assessment.risk_score,
        "severity": p1_assessment.severity,
        "fall_detected": p1_fall.is_fall,
        "zone_breach": p1_in_zone
    }
    logger.info(f"  Phase 1 Result: {'PASSED' if p1_passed else 'FAILED'} (Risk={p1_assessment.risk_score}, Severity={p1_assessment.severity})")

    # -------------------------------------------------------------------------
    # PHASE 2: Routine Maintenance with PPE Non-Compliance Warning
    # -------------------------------------------------------------------------
    logger.info("\n>>> PHASE 2: PPE Non-Compliance Warning (Worker #102)")
    p2_passed = True
    # Worker 102 removes hardhat
    no_helmet_item = PPEItem(
        item_type="NO_HELMET",
        confidence=0.92,
        bbox=(120, 110, 180, 160),
        center=(150, 135)
    )
    p2_ppe = ppe_engine.analyze_worker(
        worker_id=102,
        person_bbox=(100, 100, 200, 420),
        detected_ppe_items=[no_helmet_item],
        timestamp=sim_start + 10.0
    )
    p2_hazards = ["NO_HELMET"] if not p2_ppe.has_helmet else []
    p2_assessment = risk_engine.evaluate(
        worker_id=102,
        active_hazards=p2_hazards,
        proximity_distance_m=2.6,
        detection_confidence=0.92
    )

    if p2_ppe.has_helmet is True:
        p2_passed = False
        results["inconsistencies"].append("Phase 2: Failed to detect missing helmet.")
    if not (30 <= p2_assessment.risk_score <= 55 and p2_assessment.severity == "MEDIUM"):
        p2_passed = False
        results["inconsistencies"].append(f"Phase 2: Expected Medium risk (30-55), got {p2_assessment.risk_score} ({p2_assessment.severity})")

    results["phase_results"]["Phase 2: PPE Warning"] = {
        "passed": p2_passed,
        "risk_score": p2_assessment.risk_score,
        "severity": p2_assessment.severity,
        "missing_items": p2_ppe.missing_items
    }
    logger.info(f"  Phase 2 Result: {'PASSED' if p2_passed else 'FAILED'} (Risk={p2_assessment.risk_score}, Missing={p2_ppe.missing_items})")

    # -------------------------------------------------------------------------
    # PHASE 3: Real-Life Non-Hazard Action (Crouching / Bending to Retrieve Tools)
    # -------------------------------------------------------------------------
    logger.info("\n>>> PHASE 3: Real-Life Crouching Worker & Safe Workspace Objects")
    p3_passed = True
    # Worker 103 crouches down: bbox is squarish (w=180, h=180, aspect_ratio=1.0)
    # But keypoints show vertical spine: mid-shoulder=(240, 280), mid-hip=(235, 360) -> angle = 86 deg!
    crouch_kpts = create_mock_keypoints(shoulder_mid=(240, 280), hip_mid=(235, 360), ankle_mid=(235, 400))
    p3_fall_1 = fall_detector.evaluate_worker(
        worker_id=103,
        bbox=(150, 240, 330, 420), # aspect_ratio = 1.0
        velocity=(0, 2),
        keypoints=crouch_kpts,
        timestamp=sim_start + 20.0
    )
    # Worker remains crouched for 2.5s
    p3_fall_2 = fall_detector.evaluate_worker(
        worker_id=103,
        bbox=(150, 240, 330, 420),
        velocity=(0, 0),
        keypoints=crouch_kpts,
        timestamp=sim_start + 22.5
    )

    if p3_fall_2.is_fall or p3_fall_2.state == "FALL_CONFIRMED":
        p3_passed = False
        results["inconsistencies"].append("Phase 3: False fall alarm triggered on crouching worker!")

    # Check clean taxonomy on safe-space non-hazard objects
    safe_object_names = ["cell phone", "bottle", "chair", "laptop", "backpack", "cup"]
    for name in safe_object_names:
        cat = detector._categorize_class(name)
        if cat == "HAZARD_OBJECT":
            p3_passed = False
            results["inconsistencies"].append(f"Phase 3: Safe object '{name}' categorized as HAZARD_OBJECT.")

    results["phase_results"]["Phase 3: Crouching Non-Hazard"] = {
        "passed": p3_passed,
        "crouch_fall_state": p3_fall_2.state,
        "is_fall": p3_fall_2.is_fall,
        "aspect_ratio": p3_fall_2.aspect_ratio,
        "safe_objects_false_alarms": 0 if p3_passed else 1
    }
    logger.info(f"  Phase 3 Result: {'PASSED' if p3_passed else 'FAILED'} (Crouch State={p3_fall_2.state}, IsFall={p3_fall_2.is_fall})")

    # -------------------------------------------------------------------------
    # PHASE 4: Spatial Danger Zone Breach & Critical Proximity Synergy
    # -------------------------------------------------------------------------
    logger.info("\n>>> PHASE 4: Restricted Danger Zone Breach & Critical Machine Proximity")
    p4_passed = True
    # Worker 104 without helmet steps inside Hydraulic Press Perimeter:
    # foot at (600, 600) in 1000x1000 -> norm (0.60, 0.60) which is inside [(0.4, 0.4), (0.85, 0.85)]
    p4_zone_events = zone_engine.evaluate_worker(
        worker_id=104,
        foot_x=600,
        foot_y=600,
        timestamp=sim_start + 30.0,
        camera_id="CAM_FACTORY_01",
        frame_w=1000,
        frame_h=1000
    )
    p4_in_zone = any(ze.state in ("ENTERED", "INSIDE") for ze in p4_zone_events)

    # Exposure dwells for 4.2 seconds
    _ = exposure_tracker.update_exposure("CAM_FACTORY_01", 104, "RESTRICTED_ZONE", True, timestamp=sim_start + 30.0)
    p4_exp = exposure_tracker.update_exposure("CAM_FACTORY_01", 104, "RESTRICTED_ZONE", True, timestamp=sim_start + 34.2)

    # Compound synergy: NO_HELMET + RESTRICTED_ZONE + UNSAFE_PROXIMITY_CRITICAL
    p4_assessment = risk_engine.evaluate(
        worker_id=104,
        active_hazards=["NO_HELMET", "RESTRICTED_ZONE", "UNSAFE_PROXIMITY_CRITICAL"],
        exposure_duration_sec=p4_exp.duration_seconds,
        proximity_distance_m=0.65,
        detection_confidence=0.96
    )

    if not p4_in_zone:
        p4_passed = False
        results["inconsistencies"].append("Phase 4: Failed to detect zone intrusion at (0.60, 0.60).")
    if p4_assessment.synergy_score <= 0:
        p4_passed = False
        results["inconsistencies"].append("Phase 4: Multi-hazard synergy failed to trigger bonus.")
    if p4_assessment.risk_score < 85 or p4_assessment.severity != "CRITICAL":
        p4_passed = False
        results["inconsistencies"].append(f"Phase 4: Expected Critical risk >= 85, got {p4_assessment.risk_score} ({p4_assessment.severity})")

    results["phase_results"]["Phase 4: Danger Zone Breach"] = {
        "passed": p4_passed,
        "in_zone": p4_in_zone,
        "exposure_seconds": round(p4_exp.duration_seconds, 1),
        "synergy_score": p4_assessment.synergy_score,
        "risk_score": p4_assessment.risk_score,
        "severity": p4_assessment.severity
    }
    logger.info(f"  Phase 4 Result: {'PASSED' if p4_passed else 'FAILED'} (Risk={p4_assessment.risk_score}, Synergy=+{p4_assessment.synergy_score}, Severity={p4_assessment.severity})")

    # -------------------------------------------------------------------------
    # PHASE 5: Acute Incident (True Worker Slip & Fall inside Danger Perimeter)
    # -------------------------------------------------------------------------
    logger.info("\n>>> PHASE 5: Acute Incident — Slip & Fall inside Danger Zone")
    p5_passed = True
    # Worker 104 slips: horizontal spine (mid-shoulder at 550, 680; mid-hip at 660, 690 -> angle 5.2 deg!)
    fall_kpts = create_mock_keypoints(shoulder_mid=(550, 680), hip_mid=(660, 690), ankle_mid=(750, 700))
    # Immediate fall motion
    _ = fall_detector.evaluate_worker(
        worker_id=104,
        bbox=(520, 650, 800, 720), # aspect_ratio = 70/280 = 0.25
        velocity=(0, 45), # Downward velocity spike
        keypoints=fall_kpts,
        timestamp=sim_start + 35.0
    )
    # Persists fallen for 1.8s (> confirmation threshold 1.5s)
    p5_fall = fall_detector.evaluate_worker(
        worker_id=104,
        bbox=(520, 650, 800, 720),
        velocity=(0, 0),
        keypoints=fall_kpts,
        timestamp=sim_start + 36.8
    )

    p5_hazards = ["WORKER_FALL", "RESTRICTED_ZONE", "NO_HELMET", "UNSAFE_PROXIMITY_CRITICAL"]
    p5_assessment = risk_engine.evaluate(
        worker_id=104,
        active_hazards=p5_hazards,
        exposure_duration_sec=6.8,
        proximity_distance_m=0.65,
        detection_confidence=0.98
    )

    if not p5_fall.is_fall or p5_fall.state != "FALL_CONFIRMED":
        p5_passed = False
        results["inconsistencies"].append(f"Phase 5: Worker fall not confirmed (state={p5_fall.state}, is_fall={p5_fall.is_fall})")
    if p5_assessment.risk_score < 95 or p5_assessment.severity != "CRITICAL":
        p5_passed = False
        results["inconsistencies"].append(f"Phase 5: Acute fall did not reach max critical score (got {p5_assessment.risk_score})")

    results["phase_results"]["Phase 5: Acute Fall Incident"] = {
        "passed": p5_passed,
        "fall_confirmed": p5_fall.is_fall,
        "fall_state": p5_fall.state,
        "fall_duration_sec": p5_fall.duration_sec,
        "risk_score": p5_assessment.risk_score,
        "severity": p5_assessment.severity,
        "recommended_action": p5_assessment.recommended_action
    }
    logger.info(f"  Phase 5 Result: {'PASSED' if p5_passed else 'FAILED'} (Fall={p5_fall.state}, Risk={p5_assessment.risk_score}, Action='{p5_assessment.recommended_action}')")

    # -------------------------------------------------------------------------
    # PHASE 6: Emergency Response, Evacuation & Incident Resolution Lifecycle
    # -------------------------------------------------------------------------
    logger.info("\n>>> PHASE 6: Emergency Response, Evacuation & Incident Resolution")
    p6_passed = True
    sm = EventStateMachine(initial_state=EventState.ALERTING)
    
    # Emergency intervention occurs -> Evacuate to safe coordinates
    can_resolve = sm.transition_to(EventState.RESOLVED)
    if not can_resolve or sm.current_state != EventState.RESOLVED:
        p6_passed = False
        results["inconsistencies"].append("Phase 6: Illegal transition to RESOLVED in state machine.")

    # Audit logging transition
    can_log = sm.transition_to(EventState.LOGGED)
    if not can_log or sm.current_state != EventState.LOGGED:
        p6_passed = False
        results["inconsistencies"].append("Phase 6: Failed to reach final LOGGED state in audit history.")

    # Reset exposure dwell
    p6_exp = exposure_tracker.update_exposure("CAM_FACTORY_01", 104, "RESTRICTED_ZONE", False, timestamp=sim_start + 45.0)
    p6_assessment = risk_engine.evaluate(
        worker_id=104,
        active_hazards=[],
        proximity_distance_m=4.5,
        detection_confidence=0.95
    )

    if p6_exp.is_active or p6_exp.duration_seconds != 0.0:
        p6_passed = False
        results["inconsistencies"].append("Phase 6: Exposure tracker did not reset upon hazard clearance.")
    if p6_assessment.risk_score != 0 or p6_assessment.severity != "ADVISORY":
        p6_passed = False
        results["inconsistencies"].append(f"Phase 6: Post-evacuation risk score not 0 (got {p6_assessment.risk_score})")

    results["phase_results"]["Phase 6: Evacuation & Resolution"] = {
        "passed": p6_passed,
        "final_event_state": sm.current_state.value,
        "exposure_reset": not p6_exp.is_active,
        "final_risk_score": p6_assessment.risk_score,
        "audit_trail_length": len(sm.history)
    }
    logger.info(f"  Phase 6 Result: {'PASSED' if p6_passed else 'FAILED'} (State={sm.current_state.value}, ExposureReset={not p6_exp.is_active}, FinalRisk={p6_assessment.risk_score})")

    # -------------------------------------------------------------------------
    # COGNITIVE VISION TIER: Qwen 2.5-VL Root Cause Explanation
    # -------------------------------------------------------------------------
    logger.info("\n>>> COGNITIVE VLM TIER: Qwen 2.5-VL Root-Cause Assessment on Incident Frame")
    import httpx
    import base64
    vlm_result = {"status": "SKIPPED", "summary": ""}
    try:
        # Generate an incident frame representing Phase 5 with warning banner
        incident_frame = np.full((480, 640, 3), 35, dtype=np.uint8) # Factory floor gray
        cv2.rectangle(incident_frame, (int(0.4*640), int(0.4*480)), (int(0.85*640), int(0.85*480)), (0, 0, 180), 2)
        cv2.putText(incident_frame, "RESTRICTED HYDRAULIC PRESS ZONE", (int(0.4*640)+10, int(0.4*480)+25), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        # Fallen worker figure
        cv2.ellipse(incident_frame, (400, 320), (120, 30), 0, 0, 360, (50, 120, 220), -1)
        cv2.circle(incident_frame, (300, 320), 20, (180, 180, 180), -1)
        cv2.putText(incident_frame, "WORKER 104 (COLLAPSED)", (320, 365), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (255, 255, 255), 1)

        # Scale to max 448 for fast cognitive processing
        small_f = cv2.resize(incident_frame, (448, 336), interpolation=cv2.INTER_AREA)
        _, jpg_bytes = cv2.imencode(".jpg", small_f, [cv2.IMWRITE_JPEG_QUALITY, 75])
        b64 = base64.b64encode(jpg_bytes).decode("utf-8")

        prompt = (
            "You are an industrial safety expert AI monitoring a high-risk factory environment.\n"
            "Analyze this incident frame and provide a concise JSON object with:\n"
            "{\n"
            '  "primary_hazard": "<hazard type>",\n'
            '  "incident_severity": "CRITICAL",\n'
            '  "immediate_operator_action": "<action recommendation>"\n'
            "}"
        )
        t0 = time.perf_counter()
        with httpx.Client(timeout=45.0) as client:
            res = client.post(
                "http://localhost:11434/api/chat",
                json={
                    "model": "qwen2.5vl:7b",
                    "messages": [{"role": "user", "content": prompt, "images": [b64]}],
                    "stream": False,
                    "options": {"temperature": 0.1}
                }
            )
        dt_ms = (time.perf_counter() - t0) * 1000
        if res.status_code == 200:
            raw = res.json().get("message", {}).get("content", "")
            vlm_result = {
                "status": "SUCCESS",
                "latency_ms": round(dt_ms, 1),
                "qwen_response": raw[:250].replace("\n", " ")
            }
            logger.info(f"  Qwen 2.5-VL Incident Reasoning ({dt_ms:.1f}ms): {raw[:120]}...")
    except Exception as e:
        vlm_result = {"status": "SKIPPED_OR_ERROR", "note": str(e)}
        logger.warning(f"  VLM evaluation notice: {e}")

    results["cognitive_vlm"] = vlm_result

    # Final Check
    all_passed = all(pr.get("passed", False) for pr in results["phase_results"].values())
    results["all_passed"] = all_passed
    results["total_inconsistencies"] = len(results["inconsistencies"])

    # Persist artifact
    out_file = Path("datasets/real_life_simulation_results.json")
    with open(out_file, "w") as f:
        json.dump(results, f, indent=2)

    logger.info("\n" + "=" * 75)
    logger.info("             SIMULATION RESULTS SUMMARY")
    logger.info("=" * 75)
    logger.info(f"Overall Simulation Result:    {'ALL 6 PHASES PASSED (PERFECT)' if all_passed else 'FAILED'}")
    logger.info(f"Total Inconsistencies Found:  {len(results['inconsistencies'])}")
    for phase_name, pr in results["phase_results"].items():
        logger.info(f"  - {phase_name:<34}: {'PASSED' if pr['passed'] else 'FAILED'}")
    logger.info("=" * 75)
    logger.info(f"Simulation audit report saved to: {out_file.resolve()}\n")

    return results


if __name__ == "__main__":
    res = run_simulation()
    if not res["all_passed"]:
        sys.exit(1)
