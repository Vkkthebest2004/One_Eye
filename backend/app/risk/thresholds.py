from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class RiskThresholds:
    ADVISORY_MAX: int = 29
    MEDIUM_MIN: int = 30
    MEDIUM_MAX: int = 59
    HIGH_MIN: int = 60
    HIGH_MAX: int = 79
    CRITICAL_MIN: int = 80

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


# Base severity lookup per hazard type
BASE_HAZARD_SEVERITY: Dict[str, int] = {
    "NO_HELMET": 35,
    "NO_VEST": 25,
    "RESTRICTED_ZONE": 55,
    "UNSAFE_PROXIMITY_WARNING": 30,
    "UNSAFE_PROXIMITY_DANGER": 60,
    "UNSAFE_PROXIMITY_CRITICAL": 85,
    "WORKER_FALL": 85,
    "FIRE_DETECTED": 95,
    "SMOKE_DETECTED": 80,
    "UNAUTHORIZED_ACCESS": 50,
}

# Recommended operator action per primary hazard
RECOMMENDED_ACTIONS: Dict[str, str] = {
    "NO_HELMET": "Instruct worker to equip required safety hardhat immediately.",
    "NO_VEST": "Instruct worker to put on high-visibility safety vest.",
    "RESTRICTED_ZONE": "Direct worker to evacuate restricted danger perimeter immediately.",
    "UNSAFE_PROXIMITY_CRITICAL": "Emergency intervene: Halt active machinery and move worker back.",
    "UNSAFE_PROXIMITY_DANGER": "Alert area supervisor to maintain 1.5m minimum safe clearance.",
    "UNSAFE_PROXIMITY_WARNING": "Advise worker to maintain caution near operating machinery.",
    "WORKER_FALL": "Dispatch immediate medical/first-aid team and verify worker status.",
    "FIRE_DETECTED": "Trigger emergency fire alarm and initiate automated plant evacuation.",
    "SMOKE_DETECTED": "Inspect fire sensor zone and prepare fire suppression protocols.",
}
