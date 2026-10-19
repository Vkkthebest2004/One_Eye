import os
import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.repositories.retrospective_repo import RetrospectiveRepository
from app.cv.pipeline import pipeline_manager
from app.cv.retrospective import retrospective_engine, SequenceReconstructor

router = APIRouter(prefix="/api/retrospective", tags=["Retrospective Video Sequence Intelligence"])


class RetrospectiveAnalysisRequest(BaseModel):
    domain: str = Field(default="INDUSTRIAL_SOP", description="INDUSTRIAL_SOP, EQUIPMENT_OPERATION, SECURITY_PERIMETER, ERGONOMICS_SAFETY, CUSTOM")
    custom_goal: Optional[str] = Field(default=None, description="Optional custom evaluation rule or investigation goal")
    seconds: float = Field(default=60.0, ge=10.0, le=120.0, description="Duration in seconds to analyze retrospectively")


@router.post("/{camera_id}/analyze")
async def analyze_camera_sequence(
    camera_id: str,
    request: RetrospectiveAnalysisRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reconstructs the past 60 seconds from the camera's rolling video buffer,
    identifies mistakes or unusual situations, and produces an intelligent analysis with suggestions.
    """
    pipe = pipeline_manager.get_pipeline(camera_id)
    if not pipe:
        raise HTTPException(status_code=404, detail=f"Camera pipeline '{camera_id}' not found or inactive")

    buffer = getattr(pipe, "sequence_buffer", None)
    if not buffer:
        raise HTTPException(status_code=400, detail=f"Camera '{camera_id}' does not have an active sequence buffer")

    # Run Sequence Retrospective Analysis
    report_dict = await retrospective_engine.analyze_sequence(
        camera_id=camera_id,
        buffer=buffer,
        domain=request.domain,
        custom_goal=request.custom_goal,
        seconds=request.seconds
    )

    # Persist report in database
    repo = RetrospectiveRepository(db)
    saved_report = await repo.create({
        "id": report_dict["id"],
        "camera_id": camera_id,
        "domain": report_dict.get("domain", "INDUSTRIAL_SOP"),
        "custom_goal": report_dict.get("custom_goal"),
        "what_happened": report_dict.get("what_happened", ""),
        "what_went_wrong": report_dict.get("what_went_wrong", ""),
        "evidence_timeline": report_dict.get("evidence_timeline", []),
        "possible_explanation": report_dict.get("possible_explanation", ""),
        "recommended_next_steps": report_dict.get("recommended_next_steps", []),
        "keyframe_paths": report_dict.get("keyframe_paths", []),
        "clip_path": report_dict.get("clip_path"),
        "analysis_duration_sec": report_dict.get("analysis_duration_sec", 60.0),
        "severity": report_dict.get("severity", "MEDIUM"),
        "reasoning_engine": report_dict.get("reasoning_engine", "ONE EYE Cognitive Sequence Synthesizer"),
    })

    return report_dict


@router.get("/{camera_id}/timeline")
async def get_camera_timeline(
    camera_id: str,
    seconds: float = Query(60.0, ge=10.0, le=120.0)
):
    """
    Returns the lightweight real-time reconstructed event timeline for the past 60s
    without executing a full multi-stage LLM generation pass.
    """
    pipe = pipeline_manager.get_pipeline(camera_id)
    if not pipe:
        raise HTTPException(status_code=404, detail=f"Camera pipeline '{camera_id}' not found")

    buffer = getattr(pipe, "sequence_buffer", None)
    if not buffer or not buffer.buffer:
        return {
            "camera_id": camera_id,
            "buffered_seconds": 0.0,
            "total_snapshots": 0,
            "timeline": [],
            "max_risk_60s": 0,
            "active_hazards": []
        }

    snapshots = buffer.get_snapshots(seconds)
    timeline = SequenceReconstructor.reconstruct(snapshots)

    buffered_seconds = 0.0
    if snapshots:
        buffered_seconds = round(snapshots[-1].timestamp - snapshots[0].timestamp, 1)

    max_risk = max((s.max_risk for s in snapshots), default=0)
    all_hazards = set()
    for s in snapshots:
        all_hazards.update(s.active_hazards)

    return {
        "camera_id": camera_id,
        "buffered_seconds": buffered_seconds,
        "total_snapshots": len(snapshots),
        "timeline": timeline,
        "max_risk_60s": max_risk,
        "active_hazards": list(all_hazards)
    }


@router.get("/reports")
async def list_retrospective_reports(
    camera_id: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """Returns past 60-second retrospective investigation reports."""
    repo = RetrospectiveRepository(db)
    reports, total = await repo.get_all(
        camera_id=camera_id,
        domain=domain,
        severity=severity,
        limit=limit,
        offset=offset
    )

    return {
        "total": total,
        "reports": [
            {
                "id": r.id,
                "camera_id": r.camera_id,
                "domain": r.domain,
                "custom_goal": r.custom_goal,
                "what_happened": r.what_happened,
                "what_went_wrong": r.what_went_wrong,
                "evidence_timeline": r.evidence_timeline,
                "possible_explanation": r.possible_explanation,
                "recommended_next_steps": r.recommended_next_steps,
                "keyframe_paths": r.keyframe_paths,
                "clip_path": r.clip_path,
                "analysis_duration_sec": r.analysis_duration_sec,
                "severity": r.severity,
                "reasoning_engine": r.reasoning_engine,
                "created_at": r.created_at.isoformat() if r.created_at else None
            }
            for r in reports
        ]
    }


@router.get("/reports/{report_id}")
async def get_retrospective_report(
    report_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Retrieves a specific retrospective report by ID."""
    repo = RetrospectiveRepository(db)
    r = await repo.get_by_id(report_id)
    if not r:
        raise HTTPException(status_code=404, detail="Report not found")

    return {
        "id": r.id,
        "camera_id": r.camera_id,
        "domain": r.domain,
        "custom_goal": r.custom_goal,
        "what_happened": r.what_happened,
        "what_went_wrong": r.what_went_wrong,
        "evidence_timeline": r.evidence_timeline,
        "possible_explanation": r.possible_explanation,
        "recommended_next_steps": r.recommended_next_steps,
        "keyframe_paths": r.keyframe_paths,
        "clip_path": r.clip_path,
        "analysis_duration_sec": r.analysis_duration_sec,
        "severity": r.severity,
        "reasoning_engine": r.reasoning_engine,
        "created_at": r.created_at.isoformat() if r.created_at else None
    }


@router.get("/{camera_id}/clip")
async def download_retrospective_clip(
    camera_id: str,
    seconds: float = Query(60.0, ge=10.0, le=120.0)
):
    """Generates and returns an MP4 video clip of the rolling sequence buffer."""
    pipe = pipeline_manager.get_pipeline(camera_id)
    if not pipe:
        raise HTTPException(status_code=404, detail=f"Camera pipeline '{camera_id}' not found")

    buffer = getattr(pipe, "sequence_buffer", None)
    if not buffer or not buffer.buffer:
        raise HTTPException(status_code=400, detail="Insufficient video frames in sequence buffer")

    tmp_dir = Path("./evidence/retrospective/clips")
    tmp_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{camera_id}_{int(seconds)}s_{int(time.time())}.mp4"
    file_path = tmp_dir / filename

    ok = buffer.export_mp4(str(file_path), seconds=seconds)
    if not ok or not file_path.exists():
        raise HTTPException(status_code=500, detail="Failed to render video sequence clip")

    return FileResponse(
        path=str(file_path),
        media_type="video/mp4",
        filename=filename
    )
