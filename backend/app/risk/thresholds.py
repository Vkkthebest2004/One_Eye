from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class RiskThresholds:
    ADVISORY_MAX: int = 29
    MEDIUM_MIN: int = 30
    MEDIUM_MAX: int = 59
    HIGH_MIN: int = 60
    HIGH_MAX: int = 79
    CRITICAL_MIN: int = 80

    # Hysteresis deadband thresholds (prevents alert flickering across boundaries)
    DEESCALATE_TO_ADVISORY: int = 25
    DEESCALATE_TO_MEDIUM: int = 55
    DEESCALATE_TO_HIGH: int = 75

    @classmethod
    def get_severity(cls, score: int) -> str:
        if score >= cls.CRITICAL_MIN:
            return "CRITICAL"
        elif score >= cls.HIGH_MIN:
            return "HIGH"
        elif score >= cls.MEDIUM_MIN:
            return "MEDIUM"
        else:
            return "ADVISORY"

    @classmethod
    def get_severity_with_hysteresis(cls, score: int, previous_severity: Optional[str] = None) -> str:
        """
        Calculates severity with deadband hysteresis to eliminate alert flapping
        on fluctuating video detector confidence.
        """
        if previous_severity is None:
            return cls.get_severity(score)

        prev = previous_severity.upper()
        if prev == "CRITICAL":
            # De-escalate only if drops strictly below de-escalation floor
            if score < cls.DEESCALATE_TO_HIGH:
                return cls.get_severity(score)
            return "CRITICAL"
        elif prev == "HIGH":
            if score >= cls.CRITICAL_MIN:
                return "CRITICAL"
            elif score < cls.DEESCALATE_TO_MEDIUM:
                return cls.get_severity(score)
            return "HIGH"
        elif prev == "MEDIUM":
            if score >= cls.HIGH_MIN:
                return "HIGH"
            elif score < cls.DEESCALATE_TO_ADVISORY:
                return "ADVISORY"
            return "MEDIUM"
        else: # ADVISORY
            if score >= cls.MEDIUM_MIN:
                return cls.get_severity(score)
            return "ADVISORY"


# Base severity lookup per hazard type
BASE_HAZARD_SEVERITY: Dict[str, int] = {
    "NO_HELMET": 35,
    "NO_VEST": 25,
    "NO_GLASSES": 20,
    "RESTRICTED_ZONE": 80,
    "RESTRICTED_ZONE_CRITICAL": 90,
    "DANGER_ZONE_REACHED": 90,
    "ZONE_INTRUSION": 88,
    "UNSAFE_PROXIMITY_WARNING": 30,
    "UNSAFE_PROXIMITY_DANGER": 60,
    "UNSAFE_PROXIMITY_CRITICAL": 85,
    "WORKER_FALL": 85,
    "FIRE_DETECTED": 95,
    "SMOKE_DETECTED": 80,
    "UNAUTHORIZED_ACCESS": 50,
}

# Standardized ISO / OSHA Operational Action Codes
HAZARD_ACTION_CODES: Dict[str, str] = {
    "NO_HELMET": "ACT-EQUIP-HELMET",
    "NO_VEST": "ACT-EQUIP-VEST",
    "NO_GLASSES": "ACT-EQUIP-GLASSES",
    "RESTRICTED_ZONE": "ACT-EVACUATE-ZONE",
    "RESTRICTED_ZONE_CRITICAL": "ACT-EMERGENCY-HALT",
    "DANGER_ZONE_REACHED": "ACT-EVACUATE-ZONE",
    "ZONE_INTRUSION": "ACT-INTERCEPT-INTRUDER",
    "UNSAFE_PROXIMITY_CRITICAL": "ACT-HALT-MACHINE",
    "UNSAFE_PROXIMITY_DANGER": "ACT-CLEAR-PERIMETER",
    "UNSAFE_PROXIMITY_WARNING": "ACT-ADVISE-CAUTION",
    "WORKER_FALL": "ACT-DISPATCH-FIRST-AID",
    "FIRE_DETECTED": "ACT-TRIGGER-EVACUATION",
    "SMOKE_DETECTED": "ACT-FIRE-SUPPRESSION",
    "UNAUTHORIZED_ACCESS": "ACT-VERIFY-CREDENTIALS",
    "NONE": "ACT-NOMINAL",
}

# Recommended operator action per primary hazard
RECOMMENDED_ACTIONS: Dict[str, str] = {
    "NO_HELMET": "Instruct worker to equip required safety hardhat immediately.",
    "NO_VEST": "Instruct worker to put on high-visibility safety vest.",
    "NO_GLASSES": "Instruct worker to put on certified safety glasses / eye protection.",
    "RESTRICTED_ZONE": "Direct worker to evacuate restricted danger perimeter immediately.",
    "RESTRICTED_ZONE_CRITICAL": "Emergency intervene: halt the hazardous operation and evacuate the no-entry zone.",
    "DANGER_ZONE_REACHED": "⚠️ DANGER ZONE REACHED: Direct worker to evacuate marked danger coordinate perimeter immediately.",
    "ZONE_INTRUSION": "Intervene immediately: Worker or foreign object has crossed active geofence barrier.",
    "UNSAFE_PROXIMITY_CRITICAL": "Emergency intervene: Halt active machinery and move worker back.",
    "UNSAFE_PROXIMITY_DANGER": "Alert area supervisor to maintain 1.5m minimum safe clearance.",
    "UNSAFE_PROXIMITY_WARNING": "Advise worker to maintain caution near operating machinery.",
    "WORKER_FALL": "Dispatch immediate medical/first-aid team and verify worker status.",
    "FIRE_DETECTED": "Trigger emergency fire alarm and initiate automated plant evacuation.",
    "SMOKE_DETECTED": "Inspect fire sensor zone and prepare fire suppression protocols.",
    "NONE": "Normal operations. All safety perimeters nominal.",
}


def resolve_hazard_base_severity(hazard_name: str) -> int:
    """
    Intelligently resolves base severity for standard or dynamically generated hazard tags
    (e.g., ZONE_INTRUSION_ZN_DANGER_01, RESTRICTED_ZONE_BAY_2).
    """
    if hazard_name in BASE_HAZARD_SEVERITY:
        return BASE_HAZARD_SEVERITY[hazard_name]

    upper = hazard_name.upper()
    if upper.startswith("ZONE_INTRUSION") or "INTRUSION" in upper:
        return 88
    if "RESTRICTED_ZONE" in upper or "DANGER_ZONE" in upper:
        return 85
    if "FIRE" in upper:
        return 95
    if "SMOKE" in upper:
        return 80
    if "FALL" in upper:
        return 85
    if "PROXIMITY_CRITICAL" in upper:
        return 85
    if "PROXIMITY_DANGER" in upper:
        return 60
    if "PROXIMITY_WARNING" in upper or "PROXIMITY" in upper:
        return 30
    if "HELMET" in upper:
        return 35
    if "VEST" in upper:
        return 25
    if "GLASSES" in upper or "GOGGLE" in upper:
        return 20

    return 30


def resolve_hazard_recommended_action(hazard_name: str) -> str:
    """
    Resolves actionable instruction for standard or parameterized hazard tags.
    """
    if hazard_name in RECOMMENDED_ACTIONS:
        return RECOMMENDED_ACTIONS[hazard_name]

    upper = hazard_name.upper()
    if "INTRUSION" in upper or "ZONE" in upper:
        return "Direct worker to evacuate marked danger coordinate perimeter immediately."
    if "PROXIMITY_CRITICAL" in upper:
        return "Emergency intervene: Halt active machinery and move worker back."
    if "PROXIMITY" in upper:
        return "Maintain minimum safe operating clearance from active machinery."
    if "FALL" in upper:
        return "Dispatch immediate medical/first-aid team and verify worker status."
    if "FIRE" in upper:
        return "Trigger emergency fire alarm and initiate automated plant evacuation."
    if "SMOKE" in upper:
        return "Inspect fire sensor zone and prepare fire suppression protocols."

    return "Investigate hazard area and verify personnel safety compliance."
