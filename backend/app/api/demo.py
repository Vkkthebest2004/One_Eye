import time
import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
import cv2

from app.db.database import get_db
from app.api.schemas import DemoScenarioTrigger, SafetyEventResponse
from app.cv.pipeline import pipeline_manager
from app.risk.engine import RiskAssessment
from app.alerts.dispatcher import dispatcher

router = APIRouter(prefix="/api/demo", tags=["Demo & Scenarios"])


@router.post("/trigger", response_model=dict)
async def trigger_demo_scenario(payload: DemoScenarioTrigger, db: AsyncSession = Depends(get_db)):
    cam_id = payload.camera_id
    worker_id = payload.worker_id
    scenario = payload.scenario.lower()

    pipeline = pipeline_manager.get_pipeline(cam_id)
    frame = None
    if pipeline and pipeline.latest_frame is not None:
        frame = pipeline.latest_frame.copy()
    else:
        # Generate synthetic factory scene frame
        frame = np.full((720, 1280, 3), (35, 35, 35), dtype=np.uint8)
        cv2.putText(frame, "ONE EYE DEMO FEED", (50, 100), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        cv2.rectangle(frame, (400, 250), (650, 600), (0, 0, 200), 2) # Machine area

    now_ts = time.time()

    if scenario == "missing_helmet":
        hazards = ["NO_HELMET"]
        exposure = 3.5
        distance_m = None
        assessment = pipeline_manager.event_manager.evidence_manager and RiskAssessment(
            worker_id=worker_id,
            risk_score=52,
            severity="MEDIUM",
            primary_hazard="NO_HELMET",
            active_hazards=hazards,
            confidence=0.92,
            base_severity=35,
            proximity_score=0,
            duration_score=7,
            synergy_score=10,
            rule_triggered="PPE Debounce Confirmed: Worker #07 Missing Safety Hardhat",
            recommended_action="Instruct worker to equip required safety hardhat immediately."
        )
    elif scenario == "restricted_zone":
        hazards = ["RESTRICTED_ZONE"]
        exposure = 6.2
        distance_m = 2.1
        assessment = RiskAssessment(
            worker_id=worker_id,
            risk_score=72,
            severity="HIGH",
            primary_hazard="RESTRICTED_ZONE",
            active_hazards=hazards,
            confidence=0.94,
            base_severity=55,
            proximity_score=5,
            duration_score=12,
            synergy_score=0,
            rule_triggered="Restricted Zone Breach: Worker foot contact inside Press Machine Danger Perimeter",
            recommended_action="Direct worker to evacuate restricted danger perimeter immediately."
        )
    elif scenario == "proximity_danger":
        hazards = ["RESTRICTED_ZONE", "UNSAFE_PROXIMITY_CRITICAL", "NO_HELMET"]
        exposure = 8.4
        distance_m = 1.1
        assessment = RiskAssessment(
            worker_id=worker_id,
            risk_score=86,
            severity="CRITICAL",
            primary_hazard="UNSAFE_PROXIMITY_CRITICAL",
            active_hazards=hazards,
            confidence=0.96,
            base_severity=85,
            proximity_score=25,
            duration_score=16,
            synergy_score=20,
            rule_triggered="Critical Compound Hazard: Missing Helmet + Zone Breach + 1.1m Machine Distance",
            recommended_action="Emergency intervene: Halt active machinery and move worker back."
        )
    elif scenario == "fire_smoke":
        hazards = ["FIRE_DETECTED", "SMOKE_DETECTED"]
        exposure = 1.2
        distance_m = None
        assessment = RiskAssessment(
            worker_id=None,
            risk_score=95,
            severity="CRITICAL",
            primary_hazard="FIRE_DETECTED",
            active_hazards=hazards,
            confidence=0.95,
            base_severity=95,
            proximity_score=0,
            duration_score=0,
            synergy_score=0,
            rule_triggered="Thermal Optical Anomaly: Active Flame and Smoke Core Detected",
            recommended_action="Trigger emergency fire alarm and initiate automated plant evacuation."
        )
    elif scenario == "worker_fall":
        hazards = ["WORKER_FALL"]
        exposure = 2.0
        distance_m = None
        assessment = RiskAssessment(
            worker_id=worker_id,
            risk_score=88,
            severity="CRITICAL",
            primary_hazard="WORKER_FALL",
            active_hazards=hazards,
            confidence=0.93,
            base_severity=85,
            proximity_score=0,
            duration_score=3,
            synergy_score=0,
            rule_triggered="Temporal Fall Confirmation: Worker sustained horizontal posture > 1.5s",
            recommended_action="Dispatch immediate medical/first-aid team and verify worker status."
        )
    else:
        raise HTTPException(status_code=400, detail=f"Unknown scenario '{scenario}'")

    highlight_box = (300.0, 200.0, 450.0, 550.0) if worker_id else (450.0, 300.0, 600.0, 450.0)

    # Process through consolidated event manager
    res = await pipeline_manager.event_manager.process_assessment(
        camera_id=cam_id,
        assessment=assessment,
        frame=frame,
        distance_m=distance_m,
        exposure_sec=exposure,
        highlight_bbox=highlight_box,
        is_demo=True,
        alert_dispatcher=dispatcher
    )

    return {
        "status": "SUCCESS",
        "scenario": scenario,
        "event": res
    }
