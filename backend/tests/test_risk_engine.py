import pytest
from app.risk.engine import RiskEngine


def test_compound_risk_engine_single_hazard():
    engine = RiskEngine()
    assessment = engine.evaluate(
        worker_id=3,
        active_hazards=["NO_HELMET"],
        exposure_duration_sec=0.0,
        proximity_distance_m=None,
        detection_confidence=0.90
    )
    assert assessment.risk_score >= 30
    assert assessment.severity in ("MEDIUM", "ADVISORY")
    assert assessment.primary_hazard == "NO_HELMET"


def test_compound_risk_engine_multi_hazard_synergy():
    engine = RiskEngine()
    # Missing Helmet + Machine Zone + Danger Proximity + Long Exposure (8.4s)
    assessment = engine.evaluate(
        worker_id=7,
        active_hazards=["NO_HELMET", "RESTRICTED_ZONE", "UNSAFE_PROXIMITY_CRITICAL"],
        exposure_duration_sec=8.4,
        proximity_distance_m=0.7,
        detection_confidence=0.95
    )
    assert assessment.risk_score >= 80
    assert assessment.severity == "CRITICAL"
    assert assessment.synergy_score > 0
    assert "SYNERGY" in assessment.rule_triggered


def test_compound_risk_engine_all_clear():
    engine = RiskEngine()
    assessment = engine.evaluate(
        worker_id=1,
        active_hazards=[],
        exposure_duration_sec=0.0,
        proximity_distance_m=5.0,
        detection_confidence=0.95
    )
    assert assessment.risk_score == 0
    assert assessment.severity == "ADVISORY"
