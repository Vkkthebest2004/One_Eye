from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict
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


class ZoneCreate(ZoneBase):
    pass


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
