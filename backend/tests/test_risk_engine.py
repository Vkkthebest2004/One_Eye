import pytest
from app.risk.engine import RiskEngine
from app.risk.thresholds import RiskThresholds, resolve_hazard_base_severity


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
    assert assessment.action_code == "ACT-EQUIP-HELMET"


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
    assert assessment.action_code == "ACT-NOMINAL"


def test_multi_hazard_compounding_secondary_penalty():
    """
    Test that concurrent secondary hazards (e.g., completely unequipped worker:
    No Helmet + No Vest + No Glasses) apply structured compounding rather than
    ignoring secondary infractions.
    """
    engine = RiskEngine()
    assessment = engine.evaluate(
        worker_id=12,
        active_hazards=["NO_HELMET", "NO_VEST", "NO_GLASSES"],
        exposure_duration_sec=0.0,
        proximity_distance_m=None,
        detection_confidence=0.95
    )
    # Base: 35 (NO_HELMET) + secondary penalties (0.30*25 + 0.20*20) + 3-PPE synergy (+18)
    assert assessment.base_severity == 35
    assert assessment.secondary_score > 0
    assert assessment.synergy_score >= 18
    assert assessment.risk_score >= 60  # Accurately reaches HIGH severity
    assert assessment.severity == "HIGH"


def test_continuous_proximity_curve():
    """Verify smooth decay across proximity distance boundaries."""
    engine = RiskEngine()

    p_close, _ = engine.compute_proximity_score(0.4)
    p_near, _ = engine.compute_proximity_score(1.2)
    p_mid, _ = engine.compute_proximity_score(2.0)
    p_far, _ = engine.compute_proximity_score(3.0)

    assert p_close == 25
    assert 10 <= p_near <= 20
    assert 0 < p_mid < 10
    assert p_far == 0


def test_kinematic_time_to_impact():
    """
    Verify that a worker rapidly approaching a machine triggers
    kinematic warning and elevates proximity risk.
    """
    engine = RiskEngine()
    assessment = engine.evaluate(
        worker_id=15,
        active_hazards=["UNSAFE_PROXIMITY_DANGER"],
        proximity_distance_m=1.8,
        velocity_towards_m_s=1.5  # High speed approach towards machine
    )
    assert assessment.kinematic_warning is not None
    assert "RAPID_APPROACH" in assessment.kinematic_warning
    assert assessment.proximity_score > 10


def test_zone_breach_naming_robustness():
    """
    Ensure dynamically generated zone names like DANGER_ZONE_REACHED or
    ZONE_INTRUSION_BAY_1 trigger full severity and PPE synergy.
    """
    engine = RiskEngine()
    assessment = engine.evaluate(
        worker_id=22,
        active_hazards=["ZONE_INTRUSION_LATHE_AREA", "NO_HELMET"],
        exposure_duration_sec=1.5,
        detection_confidence=0.92
    )
    assert assessment.base_severity >= 85
    assert assessment.synergy_score > 0
    assert "SYNERGY" in assessment.rule_triggered
    assert assessment.severity == "CRITICAL"


def test_deadband_hysteresis_eliminates_flapping():
    """
    Verify hysteresis deadband prevents alert flickering on borderline scores.
    """
    engine = RiskEngine()

    # Step 1: Multi-hazard PPE score is ~65 (HIGH)
    st1 = engine.evaluate(worker_id=30, active_hazards=["NO_HELMET", "NO_VEST", "NO_GLASSES"])
    assert st1.severity == "HIGH"
    assert st1.risk_score >= 60

    # Step 2: Minor detection jitter drops score slightly to 57 (still above de-escalation floor 55)
    # In standard systems without hysteresis, 57 flips back to MEDIUM!
    # With hysteresis, it maintains HIGH to avoid annoying alarm flapping.
    sev = RiskThresholds.get_severity_with_hysteresis(57, previous_severity="HIGH")
    assert sev == "HIGH"

    # Step 3: Significant improvement down to 48 -> drops to MEDIUM
    sev_down = RiskThresholds.get_severity_with_hysteresis(48, previous_severity="HIGH")
    assert sev_down == "MEDIUM"


def test_worker_fall_synergy_with_danger_zone():
    """Worker falling inside a danger zone must escalate to emergency priority."""
    engine = RiskEngine()
    assessment = engine.evaluate(
        worker_id=99,
        active_hazards=["WORKER_FALL", "DANGER_ZONE_REACHED"],
        exposure_duration_sec=3.0,
        detection_confidence=0.95
    )
    assert assessment.severity == "CRITICAL"
    assert assessment.action_code in ("ACT-DISPATCH-FIRST-AID", "ACT-EVACUATE-ZONE")
    assert assessment.synergy_score >= 20
