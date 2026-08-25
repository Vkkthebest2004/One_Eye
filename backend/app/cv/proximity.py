import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from app.cv.homography import HomographyCalibrator

logger = logging.getLogger(__name__)


@dataclass
class MachineDefinition:
    id: str
    name: str
    camera_id: str
    bbox: Tuple[float, float, float, float] # (x1, y1, x2, y2)
    center: Tuple[float, float]
    danger_radius_m: float = 1.5 # Danger threshold in meters
    warning_radius_m: float = 2.5
    critical_radius_m: float = 0.8
    active: bool = True


@dataclass
class ProximityResult:
    worker_id: int
    machine_id: str
    machine_name: str
    distance_m: float
    distance_mode: str # "METRIC_MODE" or "PIXEL_DISTANCE_MODE"
    proximity_level: str # "SAFE", "WARNING", "DANGER", "CRITICAL"
    is_unsafe: bool


class ProximityEngine:
    """
    Worker-to-Machine Proximity Analysis Engine.
    Evaluates real-time spatial separation and assigns danger severity levels.
    """
    def __init__(self):
        self.machines: Dict[str, MachineDefinition] = {}

    def register_machine(self, machine: MachineDefinition):
        self.machines[machine.id] = machine
        logger.info(f"Registered machine '{machine.name}' (ID: {machine.id}) with danger radius {machine.danger_radius_m}m")

    def unregister_machine(self, machine_id: str):
        if machine_id in self.machines:
            del self.machines[machine_id]

    def clear_machines(self, camera_id: Optional[str] = None):
        if camera_id:
            self.machines = {mid: m for mid, m in self.machines.items() if m.camera_id != camera_id}
        else:
            self.machines.clear()

    def evaluate_worker(
        self,
        worker_id: int,
        foot_anchor: Tuple[float, float],
        camera_id: str,
        calibrator: Optional[HomographyCalibrator] = None
    ) -> List[ProximityResult]:
        results: List[ProximityResult] = []
        relevant_machines = [m for m in self.machines.values() if m.camera_id == camera_id and m.active]

        for machine in relevant_machines:
            machine_base = (machine.center[0], machine.bbox[3]) # Bottom-center of machine

            if calibrator is not None:
                distance, mode = calibrator.compute_distance_m(foot_anchor, machine_base)
            else:
                # Fallback pixel distance scale
                import math
                px_dist = math.hypot(foot_anchor[0] - machine_base[0], foot_anchor[1] - machine_base[1])
                distance = round(px_dist * 0.02, 2)
                mode = "PIXEL_DISTANCE_MODE"

            # Determine severity state
            if distance <= machine.critical_radius_m:
                level = "CRITICAL"
                is_unsafe = True
            elif distance <= machine.danger_radius_m:
                level = "DANGER"
                is_unsafe = True
            elif distance <= machine.warning_radius_m:
                level = "WARNING"
                is_unsafe = False
            else:
                level = "SAFE"
                is_unsafe = False

            results.append(ProximityResult(
                worker_id=worker_id,
                machine_id=machine.id,
                machine_name=machine.name,
                distance_m=distance,
                distance_mode=mode,
                proximity_level=level,
                is_unsafe=is_unsafe
            ))

        return results
