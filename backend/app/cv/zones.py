import logging
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from shapely.geometry import Point, Polygon

logger = logging.getLogger(__name__)


@dataclass
class ZoneDefinition:
    id: str
    name: str
    camera_id: str
    polygon_points: List[Tuple[float, float]] # [(x1, y1), (x2, y2), ...]
    severity: int = 80 # 0-100
    allowed_classes: List[str] = None
    active: bool = True
    zone_type: str = "NO_ENTRY"
    warning_delay_seconds: float = 2.0
    critical_delay_seconds: float = 8.0
    voice_alert_enabled: bool = True
    siren_enabled: bool = False
    supervisor_alert_enabled: bool = False

    def __post_init__(self):
        if self.allowed_classes is None:
            self.allowed_classes = []
        if len(self.polygon_points) >= 3:
            self._shapely_polygon = Polygon(self.polygon_points)
        else:
            self._shapely_polygon = None

    def contains_point(self, x: float, y: float, frame_w: float = 1280.0, frame_h: float = 720.0) -> bool:
        if not self.active or self._shapely_polygon is None:
            return False
        
        px, py = x, y
        if (px > 1.0 or py > 1.0) and frame_w > 0 and frame_h > 0:
            px = min(1.0, max(0.0, px / frame_w))
            py = min(1.0, max(0.0, py / frame_h))

        point = Point(px, py)
        return self._shapely_polygon.contains(point) or self._shapely_polygon.touches(point)

    def intersects_person(
        self,
        bbox: Tuple[float, float, float, float],
        foot_x: float,
        foot_y: float,
        center_x: float,
        center_y: float,
        frame_w: float = 1280.0,
        frame_h: float = 720.0
    ) -> bool:
        if not self.active or self._shapely_polygon is None:
            return False
        
        # 1. Primary Precision: Test worker foot ground contact anchor
        if self.contains_point(foot_x, foot_y, frame_w, frame_h):
            return True

        # 2. Test worker base center ground contact (90% height)
        x1, y1, x2, y2 = bbox
        base_x = (x1 + x2) / 2.0
        base_y = y1 + (y2 - y1) * 0.90
        if self.contains_point(base_x, base_y, frame_w, frame_h):
            return True

        # 3. Test lower torso (80% height)
        lower_y = y1 + (y2 - y1) * 0.80
        if self.contains_point(base_x, lower_y, frame_w, frame_h):
            return True

        return False


@dataclass
class ZoneEvent:
    worker_id: int
    zone_id: str
    zone_name: str
    severity: int
    state: str # "ENTERED", "INSIDE", "EXITED"
    foot_anchor: Tuple[float, float]
    inside_duration_sec: float


class ZoneEngine:
    """
    Restricted Zones and Danger Boundary Engine.
    Uses foot contact anchor and Shapely 2D polygon intersection.
    """
    def __init__(self):
        # zone_id -> ZoneDefinition
        self.zones: Dict[str, ZoneDefinition] = {}
        # (worker_id, zone_id) -> {'enter_time': float, 'last_seen': float, 'state': str}
        self.worker_zone_states: Dict[Tuple[int, str], Dict] = {}

    def register_zone(self, zone: ZoneDefinition):
        self.zones[zone.id] = zone
        logger.info(f"Registered zone '{zone.name}' (ID: {zone.id}) with {len(zone.polygon_points)} vertices")

    def unregister_zone(self, zone_id: str):
        if zone_id in self.zones:
            del self.zones[zone_id]

    def get_zone(self, zone_id: str) -> Optional[ZoneDefinition]:
        return self.zones.get(zone_id)

    def clear_zones(self, camera_id: Optional[str] = None):
        if camera_id:
            self.zones = {zid: z for zid, z in self.zones.items() if z.camera_id != camera_id}
        else:
            self.zones.clear()

    def evaluate_worker(
        self,
        worker_id: int,
        foot_x: float,
        foot_y: float,
        timestamp: float,
        camera_id: str,
        frame_w: float = 1280.0,
        frame_h: float = 720.0,
        bbox: Optional[Tuple[float, float, float, float]] = None,
        center_x: Optional[float] = None,
        center_y: Optional[float] = None,
    ) -> List[ZoneEvent]:
        events: List[ZoneEvent] = []
        relevant_zones = [
            z for z in self.zones.values()
            if (z.camera_id == camera_id or (camera_id.startswith("CAM_MOB") and z.camera_id.startswith("CAM_MOB"))) and z.active
        ]

        for zone in relevant_zones:
            if bbox is not None and center_x is not None and center_y is not None:
                is_inside = zone.intersects_person(bbox, foot_x, foot_y, center_x, center_y, frame_w, frame_h)
            else:
                is_inside = zone.contains_point(foot_x, foot_y, frame_w, frame_h)
            state_key = (worker_id, zone.id)
            prev_state_info = self.worker_zone_states.get(state_key)

            if is_inside:
                if prev_state_info is None:
                    # Fresh breach
                    self.worker_zone_states[state_key] = {
                        "enter_time": timestamp,
                        "last_seen": timestamp,
                        "state": "ENTERED"
                    }
                    events.append(ZoneEvent(
                        worker_id=worker_id,
                        zone_id=zone.id,
                        zone_name=zone.name,
                        severity=zone.severity,
                        state="ENTERED",
                        foot_anchor=(foot_x, foot_y),
                        inside_duration_sec=0.0
                    ))
                else:
                    # Continued presence
                    enter_time = prev_state_info["enter_time"]
                    duration = timestamp - enter_time
                    prev_state_info["last_seen"] = timestamp
                    prev_state_info["state"] = "INSIDE"
                    events.append(ZoneEvent(
                        worker_id=worker_id,
                        zone_id=zone.id,
                        zone_name=zone.name,
                        severity=zone.severity,
                        state="INSIDE",
                        foot_anchor=(foot_x, foot_y),
                        inside_duration_sec=round(duration, 1)
                    ))
            else:
                if prev_state_info is not None:
                    # Worker just exited
                    duration = timestamp - prev_state_info["enter_time"]
                    del self.worker_zone_states[state_key]
                    events.append(ZoneEvent(
                        worker_id=worker_id,
                        zone_id=zone.id,
                        zone_name=zone.name,
                        severity=zone.severity,
                        state="EXITED",
                        foot_anchor=(foot_x, foot_y),
                        inside_duration_sec=round(duration, 1)
                    ))

        return events
