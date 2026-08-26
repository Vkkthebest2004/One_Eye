from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
import datetime


# CAMERA SCHEMAS
class CameraBase(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "CAM_01"})
    name: str = Field(..., json_schema_extra={"example": "North Assembly Floor"})
    source: str = Field(..., json_schema_extra={"example": "./videos/demo/factory_safety.mp4"})
    source_type: str = Field(default="video", json_schema_extra={"example": "video"})
    fps: float = Field(default=30.0)
    resolution: str = Field(default="1280x720")


class CameraCreate(CameraBase):
    pass


class CameraUpdate(BaseModel):
    name: Optional[str] = None
    source: Optional[str] = None
    source_type: Optional[str] = None
    status: Optional[str] = None


class CameraResponse(CameraBase):
    model_config = ConfigDict(from_attributes=True)
    status: str
    is_calibrated: bool
    created_at: datetime.datetime


# ZONE SCHEMAS
class ZoneBase(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "zone_press_01"})
    camera_id: str = Field(..., json_schema_extra={"example": "CAM_01"})
    name: str = Field(..., json_schema_extra={"example": "Hydraulic Press Danger Zone"})
    polygon: List[List[float]] = Field(..., json_schema_extra={"example": [[100, 200], [400, 200], [450, 500], [80, 500]]})
    severity: int = Field(default=80, ge=0, le=100)
    allowed_classes: List[str] = Field(default_factory=list)
    active: bool = Field(default=True)
    zone_type: Literal["NO_ENTRY"] = Field(default="NO_ENTRY")
    warning_delay_seconds: float = Field(default=2.0, ge=0.0, le=300.0)
    critical_delay_seconds: float = Field(default=8.0, ge=0.0, le=600.0)
    voice_alert_enabled: bool = Field(default=True)
    siren_enabled: bool = Field(default=False)
    supervisor_alert_enabled: bool = Field(default=False)

    @field_validator("polygon")
    @classmethod
    def polygon_must_be_valid(cls, polygon: List[List[float]]):
        if len(polygon) < 3 or any(len(point) != 2 for point in polygon):
            raise ValueError("A zone polygon requires at least three [x, y] points")
        return polygon

    @model_validator(mode="after")
    def escalation_order_must_be_valid(self):
        if self.critical_delay_seconds < self.warning_delay_seconds:
            raise ValueError("critical_delay_seconds must be greater than or equal to warning_delay_seconds")
        return self


class ZoneCreate(ZoneBase):
    keyframe_b64: Optional[str] = None


class ZoneUpdate(BaseModel):
    name: Optional[str] = None
    polygon: Optional[List[List[float]]] = None
    severity: Optional[int] = Field(default=None, ge=0, le=100)
    allowed_classes: Optional[List[str]] = None
    active: Optional[bool] = None
    zone_type: Optional[Literal["NO_ENTRY"]] = None
    warning_delay_seconds: Optional[float] = Field(default=None, ge=0.0, le=300.0)
    critical_delay_seconds: Optional[float] = Field(default=None, ge=0.0, le=600.0)
    voice_alert_enabled: Optional[bool] = None
    siren_enabled: Optional[bool] = None
    supervisor_alert_enabled: Optional[bool] = None


class ZoneResponse(ZoneBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime.datetime


# MACHINE SCHEMAS
class MachineBase(BaseModel):
    id: str = Field(..., json_schema_extra={"example": "press_machine_01"})
    camera_id: str = Field(..., json_schema_extra={"example": "CAM_01"})
    name: str = Field(..., json_schema_extra={"example": "Hydraulic Stamping Press"})
    geometry: List[float] = Field(..., json_schema_extra={"example": [300, 250, 200, 180]})
    danger_radius_m: float = Field(default=1.5)
    active: bool = Field(default=True)


class MachineCreate(MachineBase):
    pass


class MachineResponse(MachineBase):
    model_config = ConfigDict(from_attributes=True)
    created_at: datetime.datetime


# EVENT SCHEMAS
class SafetyEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    camera_id: str
    zone_id: Optional[str] = None
    worker_id: int
    hazard_types: List[str]
    primary_hazard: str
    risk_score: int
    severity: str
    confidence: float
    started_at: datetime.datetime
    updated_at: datetime.datetime
    acknowledged_at: Optional[datetime.datetime] = None
    resolved_at: Optional[datetime.datetime] = None
    status: str
    evidence_path: Optional[str] = None
    distance_m: Optional[float] = None
    exposure_seconds: float
    description: Optional[str] = None
    rule_triggered: Optional[str] = None
    recommended_action: Optional[str] = None
    is_demo: bool


class EventAcknowledgeRequest(BaseModel):
    actor: str = Field(default="OPERATOR", json_schema_extra={"example": "OPERATOR_01"})


class EventResolveRequest(BaseModel):
    actor: str = Field(default="OPERATOR", json_schema_extra={"example": "OPERATOR_01"})


class EventFalsePositiveRequest(BaseModel):
    actor: str = Field(default="OPERATOR", json_schema_extra={"example": "OPERATOR_01"})
    notes: str = Field(default="", json_schema_extra={"example": "Reflection caused false alert"})


# CALIBRATION SCHEMAS
class CalibrationRequest(BaseModel):
    camera_id: str
    image_points: List[List[float]] = Field(..., json_schema_extra={"example": [[120, 420], [600, 420], [700, 700], [80, 700]]})
    world_points: List[List[float]] = Field(..., json_schema_extra={"example": [[0, 0], [10, 0], [10, 8], [0, 8]]})


class CalibrationResponse(BaseModel):
    camera_id: str
    is_calibrated: bool
    matrix: Optional[List[List[float]]]
    message: str


# DEMO TRIGGER SCHEMA
class DemoScenarioTrigger(BaseModel):
    scenario: str = Field(..., json_schema_extra={"example": "missing_helmet"})
    camera_id: str = Field(default="CAM_01")
    worker_id: int = Field(default=7)
