import datetime
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, JSON, ForeignKey
from sqlalchemy.orm import relationship
from app.db.database import Base


class Camera(Base):
    __tablename__ = "cameras"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    source = Column(String(512), nullable=False) # e.g. 0, rtsp://..., ./videos/...
    source_type = Column(String(32), default="video") # video, webcam, rtsp
    status = Column(String(32), default="ONLINE") # ONLINE, OFFLINE, ERROR
    fps = Column(Float, default=30.0)
    resolution = Column(String(32), default="1280x720")
    calibration_matrix = Column(JSON, nullable=True) # 3x3 homography matrix
    calibration_points = Column(JSON, nullable=True) # Image & World reference points
    is_calibrated = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    zones = relationship("Zone", back_populates="camera", cascade="all, delete-orphan")
    machines = relationship("Machine", back_populates="camera", cascade="all, delete-orphan")
    events = relationship("SafetyEvent", back_populates="camera")


class Zone(Base):
    __tablename__ = "zones"

    id = Column(String(64), primary_key=True, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False)
    name = Column(String(128), nullable=False)
    polygon = Column(JSON, nullable=False) # [[x1, y1], [x2, y2], ...]
    severity = Column(Integer, default=80) # 0-100
    allowed_classes = Column(JSON, default=list) # e.g. ["authorized_personnel"]
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    camera = relationship("Camera", back_populates="zones")


class Machine(Base):
    __tablename__ = "machines"

    id = Column(String(64), primary_key=True, index=True)
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False)
    name = Column(String(128), nullable=False)
    geometry = Column(JSON, nullable=False) # BBox or Center point [x, y, w, h]
    danger_radius_m = Column(Float, default=1.5) # in meters (or pixels if uncalibrated)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    camera = relationship("Camera", back_populates="machines")


class WorkerTrack(Base):
    __tablename__ = "worker_tracks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False)
    track_id = Column(Integer, nullable=False, index=True)
    first_seen = Column(DateTime, default=datetime.datetime.utcnow)
    last_seen = Column(DateTime, default=datetime.datetime.utcnow)
    total_violations = Column(Integer, default=0)


class SafetyEvent(Base):
    __tablename__ = "safety_events"

    id = Column(String(64), primary_key=True, index=True) # e.g. EVT-20260825-0001
    camera_id = Column(String(64), ForeignKey("cameras.id"), nullable=False)
    worker_id = Column(Integer, nullable=False, index=True)
    hazard_types = Column(JSON, nullable=False) # ["PPE_VIOLATION", "RESTRICTED_ZONE", ...]
    primary_hazard = Column(String(64), nullable=False) # Primary classification
    risk_score = Column(Integer, nullable=False) # 0-100
    severity = Column(String(32), nullable=False) # ADVISORY, MEDIUM, HIGH, CRITICAL
    confidence = Column(Float, default=0.90)
    started_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow)
    acknowledged_at = Column(DateTime, nullable=True)
    resolved_at = Column(DateTime, nullable=True)
    status = Column(String(32), default="ALERTING") # ALERTING, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE
    evidence_path = Column(String(512), nullable=True)
    distance_m = Column(Float, nullable=True)
    exposure_seconds = Column(Float, default=0.0)
    description = Column(Text, nullable=True)
    rule_triggered = Column(String(256), nullable=True)
    recommended_action = Column(String(256), nullable=True)
    is_demo = Column(Boolean, default=False)

    camera = relationship("Camera", back_populates="events")
    alerts = relationship("AlertRecord", back_populates="event", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="event", cascade="all, delete-orphan")


class AlertRecord(Base):
    __tablename__ = "alert_records"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), ForeignKey("safety_events.id"), nullable=False)
    channel = Column(String(32), nullable=False) # websocket, tts, whatsapp, telegram, relay
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)
    status = Column(String(32), default="SENT") # SENT, DELIVERED, FAILED
    details = Column(Text, nullable=True)

    event = relationship("SafetyEvent", back_populates="alerts")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), ForeignKey("safety_events.id"), nullable=True)
    action = Column(String(64), nullable=False) # DETECTED, ESCALATED, ACKNOWLEDGED, RESOLVED, FALSE_POSITIVE
    actor = Column(String(64), default="SYSTEM") # SYSTEM, OPERATOR_1, SAFETY_OFFICER
    timestamp = Column(DateTime, default=datetime.datetime.utcnow, index=True)
    metadata_json = Column(JSON, nullable=True)

    event = relationship("SafetyEvent", back_populates="audit_logs")
