import logging
import math
import time
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field
from app.risk.thresholds import (
    RiskThresholds,
    BASE_HAZARD_SEVERITY,
    HAZARD_ACTION_CODES,
    RECOMMENDED_ACTIONS,
    resolve_hazard_base_severity,
    resolve_hazard_recommended_action,
)

logger = logging.getLogger(__name__)


@dataclass
class RiskAssessment:
    worker_id: Optional[int]
    risk_score: int  # 0 to 100 (smoothed with deadband hysteresis)
    severity: str    # ADVISORY, MEDIUM, HIGH, CRITICAL
    primary_hazard: str
    active_hazards: List[str]
    confidence: float
    base_severity: int
    proximity_score: int
    duration_score: int
    synergy_score: int
    rule_triggered: str
    recommended_action: str
    action_code: str = "ACT-NOMINAL"
    secondary_score: int = 0
    raw_score: int = 0
    trend: str = "STABLE"  # RISING, STABLE, DECLINING
    kinematic_warning: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "worker_id": self.worker_id,
            "risk_score": self.risk_score,
            "raw_score": self.raw_score,
            "severity": self.severity,
            "primary_hazard": self.primary_hazard,
            "active_hazards": self.active_hazards,
            "confidence": round(self.confidence, 3),
            "score_breakdown": {
                "base_severity": self.base_severity,
                "secondary_hazards_score": self.secondary_score,
                "proximity_score": self.proximity_score,
                "duration_score": self.duration_score,
                "synergy_score": self.synergy_score,
            },
            "rule_triggered": self.rule_triggered,
            "recommended_action": self.recommended_action,
            "action_code": self.action_code,
            "trend": self.trend,
            "kinematic_warning": self.kinematic_warning,
        }


class RiskEngine:
    """
    Industrial Compound 0-100 Risk Intelligence Engine (ISO 45001 / OSHA Compliant).
    
    Synthesizes:
    1. Multi-hazard compounding with marginal diminishing additive penalties
    2. Continuous physical clearance & kinematic Time-to-Impact (TTI) proximity
    3. Category-calibrated temporal exposure accumulation
    4. Cross-domain synergy interaction tensor
    5. Asymmetric EMA smoothing & deadband hysteresis (zero alert flapping)
    """

    def __init__(
        self,
        duration_weight: float = 2.0,
        max_duration_score: int = 25,
        max_synergy_score: int = 35,
        ema_alpha_rise: float = 0.65,
        ema_alpha_decay: float = 0.30,
    ):
        self.duration_weight = duration_weight
        self.max_duration_score = max_duration_score
        self.max_synergy_score = max_synergy_score
        self.ema_alpha_rise = ema_alpha_rise
        self.ema_alpha_decay = ema_alpha_decay

        # (worker_id) -> state dict: {smoothed_score, previous_severity, last_updated, last_raw_score}
        self._worker_states: Dict[int, Dict[str, Any]] = {}

    def _has_zone_breach(self, hazard_set: set) -> bool:
        """Helper to match any zone breach variant (RESTRICTED_ZONE, DANGER_ZONE_REACHED, ZONE_INTRUSION_*)"""
        return any(
            ("ZONE" in h) or ("INTRUSION" in h) or ("RESTRICTED" in h)
            for h in hazard_set
        )

    def _has_machine_danger(self, hazard_set: set, proximity_m: Optional[float] = None) -> bool:
        """Helper to match dangerous proximity to operating machinery"""
        if any("PROXIMITY_DANGER" in h or "PROXIMITY_CRITICAL" in h for h in hazard_set):
            return True
        if proximity_m is not None and proximity_m < 1.5:
            return True
        return False

    def compute_synergy(
        self,
        hazards: List[str],
        proximity_distance_m: Optional[float] = None
    ) -> Tuple[int, str, List[str]]:
        """
        Computes compound hazard synergy interaction bonuses based on concurrent safety failures.
        """
        hazard_set = set(hazards)
        bonus = 0
        rules = []

        ppe_violations = [h for h in ["NO_HELMET", "NO_VEST", "NO_GLASSES"] if h in hazard_set]
        has_zone = self._has_zone_breach(hazard_set)
        has_machine = self._has_machine_danger(hazard_set, proximity_distance_m)
        has_fall = "WORKER_FALL" in hazard_set or any("FALL" in h for h in hazard_set)
        has_fire = any("FIRE" in h or "SMOKE" in h for h in hazard_set)

        # Rule 1: PPE violation inside restricted zone (unprotected worker exposed to plant hazards)
        if ppe_violations and has_zone:
            bonus += 15
            rules.append("SYNERGY: PPE Violation in Restricted Zone (+15)")

        # Rule 2: PPE violation in close proximity to machine (entanglement / impact / flying chips risk)
        if ppe_violations and has_machine:
            bonus += 20
            rules.append("SYNERGY: Unprotected Worker Near Active Machine (+20)")

        # Rule 3: Restricted zone breach + Unsafe machine proximity (dual boundary breach)
        if has_zone and has_machine:
            bonus += 20
            rules.append("SYNERGY: Zone Breach at Operating Machine (+20)")

        # Rule 4: Worker fall near operating machine or in danger zone (immobilized in hazard zone)
        if has_fall and (has_machine or has_zone):
            bonus += 25
            rules.append("SYNERGY: Incapacitated Worker in Machine/Zone Perimeter (+25)")

        # Rule 5: Systemic PPE violations (escalates exponentially with total unequipped items)
        if len(ppe_violations) == 3:
            bonus += 18
            rules.append("SYNERGY: Complete PPE Non-Compliance [Helmet+Vest+Glasses] (+18)")
        elif len(ppe_violations) == 2:
            bonus += 10
            rules.append("SYNERGY: Multiple PPE Violations (+10)")

        # Rule 6: Fire / Smoke with workers in danger perimeters
        if has_fire and (has_zone or has_machine):
            bonus += 20
            rules.append("SYNERGY: Environmental Hazard with Personnel in Danger Perimeter (+20)")

        capped_bonus = min(self.max_synergy_score, bonus)
        rule_summary = " | ".join(rules) if rules else "STANDARD_RULE_SET"
        return capped_bonus, rule_summary, rules

    def compute_proximity_score(
        self,
        distance_m: Optional[float],
        velocity_towards_m_s: Optional[float] = None
    ) -> Tuple[int, Optional[str]]:
        """
        Continuous exponential clearance decay curve with kinematic Time-to-Impact (TTI) adjustment.
        Replaces rigid step jumps with a smooth physical safety field.
        """
        if distance_m is None:
            return 0, None

        kinematic_warning: Optional[str] = None

        # 1. Continuous physical clearance curve (0 to 25 points)
        if distance_m <= 0.6:
            prox_score = 25
        elif distance_m < 2.5:
            # Smooth power decay from 25 to 0 between 0.6m and 2.5m
            norm = (2.5 - distance_m) / 1.9
            prox_score = int(round(25.0 * math.pow(norm, 1.25)))
        else:
            prox_score = 0

        # 2. Kinematic Time-to-Impact (TTI) Acceleration
        if velocity_towards_m_s is not None and velocity_towards_m_s > 0.35 and distance_m < 3.0:
            tti = distance_m / velocity_towards_m_s
            if tti < 1.5:
                # Worker is rapidly closing distance into hazardous machinery
                prox_score = min(25, prox_score + 8)
                kinematic_warning = f"RAPID_APPROACH (TTI: {tti:.1f}s at {velocity_towards_m_s:.1f}m/s)"
        elif velocity_towards_m_s is not None and velocity_towards_m_s < -0.30 and distance_m > 0.8:
            # Worker is actively retreating away from machine -> apply 20% clearance grace
            prox_score = max(0, int(prox_score * 0.80))

        return prox_score, kinematic_warning

    def compute_duration_score(
        self,
        exposure_duration_sec: float,
        primary_hazard: str
    ) -> int:
        """
        Category-calibrated exposure accumulation:
        Zone breach & Falls escalate with high urgency; PPE violations accumulate steadily.
        """
        if exposure_duration_sec <= 0.2:
            return 0

        upper = primary_hazard.upper()
        if "ZONE" in upper or "INTRUSION" in upper or "CRITICAL" in upper or "FALL" in upper:
            rate = 3.2  # Reach max score in ~7.8 seconds
        elif "PROXIMITY" in upper:
            rate = 2.4
        else:  # PPE non-compliance
            rate = self.duration_weight  # Default 2.0 (reaches max in 12.5s)

        score = int(round(exposure_duration_sec * rate))
        return min(self.max_duration_score, max(0, score))

    def evaluate(
        self,
        worker_id: Optional[int],
        active_hazards: List[str],
        exposure_duration_sec: float = 0.0,
        proximity_distance_m: Optional[float] = None,
        detection_confidence: float = 0.90,
        velocity_towards_m_s: Optional[float] = None,
        timestamp: Optional[float] = None
    ) -> RiskAssessment:
        now = timestamp or time.time()

        # All-Clear State
        if not active_hazards:
            # Reset worker state on full resolution
            if worker_id is not None and worker_id in self._worker_states:
                del self._worker_states[worker_id]

            return RiskAssessment(
                worker_id=worker_id,
                risk_score=0,
                raw_score=0,
                severity="ADVISORY",
                primary_hazard="NONE",
                active_hazards=[],
                confidence=detection_confidence,
                base_severity=0,
                proximity_score=0,
                duration_score=0,
                synergy_score=0,
                secondary_score=0,
                rule_triggered="ALL_CLEAR: Normal operations.",
                recommended_action="Normal operations. All safety perimeters nominal.",
                action_code="ACT-NOMINAL",
                trend="STABLE"
            )

        # 1. Intelligent Base Severity Resolution & Primary Hazard Selection
        hazard_severities = [
            (resolve_hazard_base_severity(h), h) for h in active_hazards
        ]
        hazard_severities.sort(key=lambda x: x[0], reverse=True)

        max_base = hazard_severities[0][0]
        primary_hazard = hazard_severities[0][1]

        # 2. Diminishing Marginal Compounding for Concurrent Secondary Hazards
        secondary_score = 0
        if len(hazard_severities) > 1:
            weights = [0.30, 0.20, 0.15, 0.10]
            sec_sum = 0.0
            for idx, (sev, _) in enumerate(hazard_severities[1:]):
                w = weights[min(idx, len(weights) - 1)]
                sec_sum += sev * w
            secondary_score = min(25, int(round(sec_sum)))

        # 3. Continuous Proximity & Kinematic Time-To-Impact
        proximity_score, kinematic_warning = self.compute_proximity_score(
            proximity_distance_m, velocity_towards_m_s
        )

        # 4. Calibrated Temporal Exposure Score
        duration_score = self.compute_duration_score(exposure_duration_sec, primary_hazard)

        # 5. Cross-Domain Contextual Synergy
        synergy_score, synergy_rule_str, synergy_rule_list = self.compute_synergy(
            active_hazards, proximity_distance_m
        )

        # 6. Raw Compound Score
        raw_score = max_base + secondary_score + proximity_score + duration_score + synergy_score

        # 7. Confidence Calibration (discounts uncertain or low-light perception detections)
        if detection_confidence < 0.85:
            conf_factor = max(0.65, detection_confidence)
            calibrated_score = float(raw_score) * conf_factor
        else:
            calibrated_score = float(raw_score)

        clamped_score = max(0, min(100, int(round(calibrated_score))))

        # 8. Asymmetric Temporal EMA Smoothing & Deadband Hysteresis
        prev_severity: Optional[str] = None
        trend = "STABLE"

        if worker_id is not None:
            if worker_id in self._worker_states:
                st = self._worker_states[worker_id]
                prev_smoothed = st["smoothed_score"]
                prev_severity = st["previous_severity"]

                # Asymmetric alpha: rise quickly on danger, decay gracefully
                alpha = self.ema_alpha_rise if clamped_score >= prev_smoothed else self.ema_alpha_decay
                smoothed_score = int(round(alpha * clamped_score + (1.0 - alpha) * prev_smoothed))

                # Trend detection
                if smoothed_score > prev_smoothed + 2:
                    trend = "RISING"
                elif smoothed_score < prev_smoothed - 2:
                    trend = "DECLINING"
                else:
                    trend = "STABLE"
            else:
                smoothed_score = clamped_score
                trend = "RISING"

            final_severity = RiskThresholds.get_severity_with_hysteresis(smoothed_score, prev_severity)

            self._worker_states[worker_id] = {
                "smoothed_score": smoothed_score,
                "previous_severity": final_severity,
                "last_updated": now,
                "last_raw_score": raw_score,
            }
            final_risk_score = smoothed_score
        else:
            final_risk_score = clamped_score
            final_severity = RiskThresholds.get_severity(final_risk_score)

        # 9. Formulate Clear Action Codes & Operator Instructions
        recommended_action = resolve_hazard_recommended_action(primary_hazard)
        action_code = HAZARD_ACTION_CODES.get(primary_hazard, "ACT-INVESTIGATE")

        # Explainability Rule String
        breakdown_str = (
            f"Base={max_base} [{primary_hazard}]"
            f"{f' + Sec={secondary_score}' if secondary_score else ''}"
            f"{f' + Prox={proximity_score}' if proximity_score else ''}"
            f"{f' + Dur={duration_score}' if duration_score else ''}"
            f"{f' + Synergy(+{synergy_score}: {synergy_rule_str})' if synergy_score else ''}"
        )
        rule_triggered = f"Rule [{primary_hazard}]: {breakdown_str} -> Score={final_risk_score} ({final_severity})"
        if kinematic_warning:
            rule_triggered += f" [{kinematic_warning}]"

        return RiskAssessment(
            worker_id=worker_id,
            risk_score=final_risk_score,
            raw_score=raw_score,
            severity=final_severity,
            primary_hazard=primary_hazard,
            active_hazards=active_hazards,
            confidence=detection_confidence,
            base_severity=max_base,
            secondary_score=secondary_score,
            proximity_score=proximity_score,
            duration_score=duration_score,
            synergy_score=synergy_score,
            rule_triggered=rule_triggered,
            recommended_action=recommended_action,
            action_code=action_code,
            trend=trend,
            kinematic_warning=kinematic_warning
        )

    def cleanup_worker(self, worker_id: int):
        """Clean up state for a worker whose track was removed."""
        self._worker_states.pop(worker_id, None)

    def cleanup_stale_workers(self, active_worker_ids: set, max_idle_sec: float = 30.0, now: Optional[float] = None):
        """Periodically cleans up idle workers from memory."""
        current_time = now or time.time()
        stale = [
            wid for wid, st in self._worker_states.items()
            if wid not in active_worker_ids and (current_time - st.get("last_updated", 0.0)) > max_idle_sec
        ]
        for wid in stale:
            del self._worker_states[wid]
