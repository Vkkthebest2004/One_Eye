import logging
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass
from app.risk.thresholds import RiskThresholds, BASE_HAZARD_SEVERITY, RECOMMENDED_ACTIONS

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    worker_id: Optional[int]
    risk_score: int # 0 to 100
    severity: str # ADVISORY, MEDIUM, HIGH, CRITICAL
    primary_hazard: str
    active_hazards: List[str]
    confidence: float
    base_severity: int
    proximity_score: int
    duration_score: int
    synergy_score: int
    rule_triggered: str
    recommended_action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "risk_score": self.risk_score,
            "severity": self.severity,
            "primary_hazard": self.primary_hazard,
            "active_hazards": self.active_hazards,
            "confidence": round(self.confidence, 3),
            "score_breakdown": {
                "base_severity": self.base_severity,
                "proximity_score": self.proximity_score,
                "duration_score": self.duration_score,
                "synergy_score": self.synergy_score
            },
            "rule_triggered": self.rule_triggered,
            "recommended_action": self.recommended_action
        }


class RiskEngine:
    """
    Compound 0-100 Industrial Risk Evaluation Engine.
    Combines perception confidence, baseline hazard severity, spatial proximity,
    temporal exposure accumulation, and multi-hazard contextual synergy.
    """
    def __init__(
        self,
        duration_weight: float = 2.0, # +2 points per second of exposure (capped at 25)
        max_duration_score: int = 25
    ):
        self.duration_weight = duration_weight
        self.max_duration_score = max_duration_score

    def compute_synergy(self, hazards: List[str]) -> Tuple[int, str]:
        """Compute compound hazard synergy bonus"""
        hazard_set = set(hazards)
        bonus = 0
        rules = []

        # Rule 1: PPE violation inside restricted zone
        if ("NO_HELMET" in hazard_set or "NO_VEST" in hazard_set) and "RESTRICTED_ZONE" in hazard_set:
            bonus += 15
            rules.append("SYNERGY: PPE Violation inside Restricted Zone (+15)")

        # Rule 2: PPE violation in close proximity to machine
        if ("NO_HELMET" in hazard_set or "NO_VEST" in hazard_set) and (
            "UNSAFE_PROXIMITY_DANGER" in hazard_set or "UNSAFE_PROXIMITY_CRITICAL" in hazard_set
        ):
            bonus += 20
            rules.append("SYNERGY: Unprotected Worker Near Active Machine (+20)")

        # Rule 3: Restricted zone breach + Unsafe machine proximity
        if "RESTRICTED_ZONE" in hazard_set and (
            "UNSAFE_PROXIMITY_DANGER" in hazard_set or "UNSAFE_PROXIMITY_CRITICAL" in hazard_set
        ):
            bonus += 20
            rules.append("SYNERGY: Zone Breach at Operating Machine (+20)")

        # Rule 4: Worker fall near operating machine
        if "WORKER_FALL" in hazard_set and any("PROXIMITY" in h for h in hazard_set):
            bonus += 25
            rules.append("SYNERGY: Worker Fall within Machine Danger Perimeter (+25)")

        # Rule 5: Multiple PPE violations
        if "NO_HELMET" in hazard_set and "NO_VEST" in hazard_set:
            bonus += 10
            rules.append("SYNERGY: Multiple PPE Violations (+10)")

        rule_summary = " | ".join(rules) if rules else "STANDARD_RULE_SET"
        return min(35, bonus), rule_summary

    def evaluate(
        self,
        worker_id: Optional[int],
        active_hazards: List[str],
        exposure_duration_sec: float = 0.0,
        proximity_distance_m: Optional[float] = None,
        detection_confidence: float = 0.90
    ) -> RiskAssessment:
        if not active_hazards:
            return RiskAssessment(
                worker_id=worker_id,
                risk_score=0,
                severity="ADVISORY",
                primary_hazard="NONE",
                active_hazards=[],
                confidence=detection_confidence,
                base_severity=0,
                proximity_score=0,
                duration_score=0,
                synergy_score=0,
                rule_triggered="ALL_CLEAR",
                recommended_action="Normal operations."
            )

        # 1. Determine highest base severity
        base_severities = [BASE_HAZARD_SEVERITY.get(h, 30) for h in active_hazards]
        max_base = max(base_severities)
        primary_hazard = active_hazards[base_severities.index(max_base)]

        # 2. Proximity contribution (0-25)
        proximity_score = 0
        if proximity_distance_m is not None:
            if proximity_distance_m < 0.8:
                proximity_score = 25
            elif proximity_distance_m < 1.5:
                proximity_score = 18
            elif proximity_distance_m < 2.5:
                proximity_score = 10

        # 3. Duration contribution (0-25)
        duration_score = min(
            self.max_duration_score,
            int(exposure_duration_sec * self.duration_weight)
        )

        # 4. Contextual synergy
        synergy_score, synergy_rule = self.compute_synergy(active_hazards)

        # 5. Calculate Raw Compound Risk Score
        raw_score = max_base + proximity_score + duration_score + synergy_score
        # Scale slightly by confidence if confidence is low
        scaled_score = raw_score * max(0.85, detection_confidence)
        final_risk_score = max(0, min(100, int(round(scaled_score))))

        severity = RiskThresholds.get_severity(final_risk_score)
        recommended_action = RECOMMENDED_ACTIONS.get(
            primary_hazard,
            "Investigate hazard area and verify personnel safety."
        )

        if synergy_score > 0:
            rule_triggered = (
                f"Rule [{primary_hazard}] Base={max_base} + Prox={proximity_score} + "
                f"Dur={duration_score} + SYNERGY(+{synergy_score}: {synergy_rule}) -> Score={final_risk_score} ({severity})"
            )
        else:
            rule_triggered = (
                f"Rule [{primary_hazard}] Base={max_base} + Prox={proximity_score} + "
                f"Dur={duration_score} -> Score={final_risk_score} ({severity})"
            )

        return RiskAssessment(
            worker_id=worker_id,
            risk_score=final_risk_score,
            severity=severity,
            primary_hazard=primary_hazard,
            active_hazards=active_hazards,
            confidence=detection_confidence,
            base_severity=max_base,
            proximity_score=proximity_score,
            duration_score=duration_score,
            synergy_score=synergy_score,
            rule_triggered=rule_triggered,
            recommended_action=recommended_action
        )
