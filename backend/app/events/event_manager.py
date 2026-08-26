import time
import datetime
import uuid
import logging
from typing import Dict, List, Optional, Tuple, Any, Set
import numpy as np

from app.db.database import AsyncSessionLocal
from app.db.models import SafetyEvent, AuditLog, AlertRecord
from app.db.repositories.event_repo import EventRepository
from app.risk.engine import RiskAssessment
from app.cv.evidence import EvidenceManager
from app.events.state_machine import EventState, EventStateMachine

logger = logging.getLogger(__name__)


class EventManager:
    """
    Consolidated Event Management & Alert Deduplication Engine.
    Tracks active worker hazard episodes, prevents duplicate alert spam,
    triggers evidence capture upon severity escalation, and coordinates dispatching.
    """
    def __init__(self, evidence_manager: Optional[EvidenceManager] = None):
        self.evidence_manager = evidence_manager or EvidenceManager()
        # (camera_id, subject_id, incident_scope) -> active event payload.
        # Subject 0 represents a plant-wide incident (fire/smoke), which the
        # existing database schema can store without losing the alert.
        self.active_worker_events: Dict[Tuple[str, int, str], Dict[str, Any]] = {}
        self._state_machines: Dict[str, EventStateMachine] = {}

    @staticmethod
    def _incident_scope(assessment: RiskAssessment) -> str:
        if assessment.worker_id is not None:
            return "WORKER"
        # Fire/smoke incidents are global. Keep hazard types in the key so a
        # fire and a smoke event can be independently deduplicated if needed.
        return "SYSTEM:" + "+".join(sorted(assessment.active_hazards or ["HAZARD"]))

    def _event_key(self, camera_id: str, assessment: RiskAssessment) -> Tuple[str, int, str]:
        return (camera_id, assessment.worker_id if assessment.worker_id is not None else 0, self._incident_scope(assessment))

    def _generate_event_id(self) -> str:
        now = datetime.datetime.utcnow()
        date_prefix = now.strftime("%Y%m%d")
        time_part = now.strftime("%H%M%S")
        rand_part = uuid.uuid4().hex[:4].upper()
        return f"EVT-{date_prefix}-{time_part}-{rand_part}"

    async def process_assessment(
        self,
        camera_id: str,
        assessment: RiskAssessment,
        frame: Optional[np.ndarray],
        distance_m: Optional[float] = None,
        exposure_sec: float = 0.0,
        highlight_bbox: Optional[Tuple[float, float, float, float]] = None,
        is_demo: bool = False,
        alert_dispatcher = None
    ) -> Optional[Dict[str, Any]]:
        """
        Process risk assessment for worker, handling deduplication, escalation,
        evidence capture, database save, and broadcast.
        """
        worker_id = assessment.worker_id if assessment.worker_id is not None else 0
        key = self._event_key(camera_id, assessment)
        now = datetime.datetime.utcnow()
        timestamp_now = time.time()

        # If no active hazards, resolve any active event for this worker
        if not assessment.active_hazards or assessment.risk_score == 0:
            if key in self.active_worker_events:
                active_info = self.active_worker_events.pop(key)
                event_id = active_info["event_id"]
                subject = f"Worker #{worker_id}" if worker_id else "Plant-wide incident"
                logger.info(f"{subject} resolved. Auto-closing event {event_id}")
                
                # Persist resolution to DB
                try:
                    async with AsyncSessionLocal() as db:
                        repo = EventRepository(db)
                        await repo.resolve(event_id, actor="AUTO_SYSTEM")
                except Exception as e:
                    logger.error(f"Error resolving event in DB: {e}")

                if alert_dispatcher:
                    await alert_dispatcher.broadcast_event_update(
                        event_id=event_id,
                        status="RESOLVED",
                        camera_id=camera_id,
                        worker_id=worker_id
                    )
                self._transition(event_id, EventState.RESOLVED)
                self._state_machines.pop(event_id, None)
            return None

        # Existing active event for worker -> Update & Escalate
        if key in self.active_worker_events:
            active_info = self.active_worker_events[key]
            event_id = active_info["event_id"]
            prev_risk = active_info["risk_score"]
            prev_severity = active_info["severity"]

            # Update metrics
            active_info["last_seen"] = timestamp_now
            active_info["risk_score"] = assessment.risk_score
            active_info["severity"] = assessment.severity
            active_info["exposure_seconds"] = exposure_sec
            active_info["distance_m"] = distance_m
            active_info["active_hazards"] = assessment.active_hazards

            # Check if escalation occurred (e.g. Medium -> Critical or Risk increased by >= 15 points)
            is_escalated = (assessment.severity != prev_severity and assessment.risk_score > prev_risk) or (
                assessment.risk_score >= prev_risk + 15
            )

            if is_escalated and frame is not None:
                # Capture new updated evidence frame
                rel_path, abs_path = self.evidence_manager.capture_snapshot(
                    frame=frame,
                    event_id=event_id,
                    camera_id=camera_id,
                    worker_id=worker_id,
                    hazard_types=assessment.active_hazards,
                    risk_score=assessment.risk_score,
                    severity=assessment.severity,
                    highlight_bbox=highlight_bbox
                )
                active_info["evidence_path"] = rel_path

            # Update database
            try:
                async with AsyncSessionLocal() as db:
                    repo = EventRepository(db)
                    event_record = await repo.get_by_id(event_id)
                    if event_record:
                        event_record.risk_score = assessment.risk_score
                        event_record.severity = assessment.severity
                        event_record.exposure_seconds = exposure_sec
                        event_record.distance_m = distance_m
                        event_record.hazard_types = assessment.active_hazards
                        event_record.primary_hazard = assessment.primary_hazard
                        if "evidence_path" in active_info:
                            event_record.evidence_path = active_info["evidence_path"]
                        await repo.update_event(event_record)
            except Exception as e:
                logger.error(f"Error updating event in DB: {e}")

            # Notify websocket
            if alert_dispatcher:
                await alert_dispatcher.broadcast_event_update(
                    event_id=event_id,
                    status=active_info.get("status", "ALERTING"),
                    camera_id=camera_id,
                    worker_id=worker_id,
                    risk_score=assessment.risk_score,
                    severity=assessment.severity,
                    hazards=assessment.active_hazards,
                    exposure_seconds=exposure_sec,
                    distance_m=distance_m,
                    evidence_url=active_info.get("evidence_path")
                )

            return active_info

        # NEW CONSOLIDATED EVENT CREATION
        event_id = self._generate_event_id()
        evidence_rel = None

        if frame is not None:
            evidence_rel, _ = self.evidence_manager.capture_snapshot(
                frame=frame,
                event_id=event_id,
                camera_id=camera_id,
                worker_id=worker_id,
                hazard_types=assessment.active_hazards,
                risk_score=assessment.risk_score,
                severity=assessment.severity,
                highlight_bbox=highlight_bbox
            )

        new_event = SafetyEvent(
            id=event_id,
            camera_id=camera_id,
            worker_id=worker_id,
            hazard_types=assessment.active_hazards,
            primary_hazard=assessment.primary_hazard,
            risk_score=assessment.risk_score,
            severity=assessment.severity,
            confidence=assessment.confidence,
            started_at=now,
            updated_at=now,
            status="ALERTING",
            evidence_path=evidence_rel,
            distance_m=distance_m,
            exposure_seconds=exposure_sec,
            description=(
                f"Automated plant-wide hazard detection: {', '.join(assessment.active_hazards)}"
                if worker_id == 0
                else f"Automated hazard detection for Worker #{worker_id:02d}: {', '.join(assessment.active_hazards)}"
            ),
            rule_triggered=assessment.rule_triggered,
            recommended_action=assessment.recommended_action,
            is_demo=is_demo
        )

        try:
            async with AsyncSessionLocal() as db:
                repo = EventRepository(db)
                await repo.create(new_event)
        except Exception as e:
            logger.error(f"Error saving new safety event: {e}")

        event_payload = {
            "event_id": event_id,
            "camera_id": camera_id,
            "worker_id": worker_id,
            "primary_hazard": assessment.primary_hazard,
            "hazard_types": assessment.active_hazards,
            "risk_score": assessment.risk_score,
            "severity": assessment.severity,
            "status": "ALERTING",
            "evidence_path": evidence_rel,
            "distance_m": distance_m,
            "exposure_seconds": exposure_sec,
            "timestamp": now.isoformat(),
            "first_seen": timestamp_now,
            "last_seen": timestamp_now,
            "recommended_action": assessment.recommended_action,
            "rule_triggered": assessment.rule_triggered
        }

        self.active_worker_events[key] = event_payload
        state_machine = EventStateMachine()
        for next_state in (EventState.DETECTED, EventState.EVALUATING, EventState.CLASSIFIED, EventState.ALERTING):
            state_machine.transition_to(next_state)
        self._state_machines[event_id] = state_machine

        # Dispatch alerts across channels (WebSocket, Voice/TTS, WhatsApp, Relay)
        if alert_dispatcher:
            await alert_dispatcher.dispatch_alert(event_payload)

        return event_payload

    def _transition(self, event_id: str, next_state: EventState) -> bool:
        state_machine = self._state_machines.get(event_id)
        return state_machine.transition_to(next_state) if state_machine else True

    async def resolve_stale_worker_events(
        self,
        camera_id: str,
        seen_worker_ids: Set[int],
        timeout_seconds: float,
        alert_dispatcher=None,
        now: Optional[float] = None,
    ) -> List[str]:
        """Resolve incidents whose tracked worker has disappeared long enough.

        A detection frame with no track never reaches ``process_assessment``;
        without this reconciliation such incidents remained ALERTING forever.
        """
        now = now if now is not None else time.time()
        resolved_ids: List[str] = []
        for key, active_info in list(self.active_worker_events.items()):
            event_camera, worker_id, scope = key
            if event_camera != camera_id or worker_id == 0 or scope != "WORKER":
                continue
            if worker_id in seen_worker_ids or now - active_info.get("last_seen", now) < timeout_seconds:
                continue

            event_id = active_info["event_id"]
            self.active_worker_events.pop(key, None)
            try:
                async with AsyncSessionLocal() as db:
                    await EventRepository(db).resolve(event_id, actor="AUTO_TRACK_LOSS")
            except Exception as exc:
                logger.error(f"Error resolving stale event {event_id}: {exc}")
            if alert_dispatcher:
                await alert_dispatcher.broadcast_event_update(
                    event_id=event_id,
                    status="RESOLVED",
                    camera_id=camera_id,
                    worker_id=worker_id,
                    actor="AUTO_TRACK_LOSS",
                )
            self._transition(event_id, EventState.RESOLVED)
            self._state_machines.pop(event_id, None)
            resolved_ids.append(event_id)
        return resolved_ids

    async def resolve_absent_system_events(
        self,
        camera_id: str,
        present_scopes: Set[str],
        timeout_seconds: float,
        alert_dispatcher=None,
        now: Optional[float] = None,
    ) -> List[str]:
        """Close plant-wide events after the detector no longer sees them."""
        now = now if now is not None else time.time()
        resolved_ids: List[str] = []
        for key, active_info in list(self.active_worker_events.items()):
            event_camera, worker_id, scope = key
            if event_camera != camera_id or worker_id != 0 or scope in present_scopes:
                continue
            if now - active_info.get("last_seen", now) < timeout_seconds:
                continue
            event_id = active_info["event_id"]
            self.active_worker_events.pop(key, None)
            try:
                async with AsyncSessionLocal() as db:
                    await EventRepository(db).resolve(event_id, actor="AUTO_SYSTEM_CLEAR")
            except Exception as exc:
                logger.error(f"Error resolving system event {event_id}: {exc}")
            if alert_dispatcher:
                await alert_dispatcher.broadcast_event_update(
                    event_id=event_id,
                    status="RESOLVED",
                    camera_id=camera_id,
                    worker_id=0,
                    actor="AUTO_SYSTEM_CLEAR",
                )
            self._transition(event_id, EventState.RESOLVED)
            self._state_machines.pop(event_id, None)
            resolved_ids.append(event_id)
        return resolved_ids

    def sync_operator_action(self, event_id: str, status: str) -> None:
        """Keep transient deduplication state consistent with operator actions."""
        status = status.upper()
        for key, event in list(self.active_worker_events.items()):
            if event.get("event_id") != event_id:
                continue
            if status in {"RESOLVED", "FALSE_POSITIVE"}:
                self.active_worker_events.pop(key, None)
                terminal_state = EventState.RESOLVED if status == "RESOLVED" else EventState.FALSE_POSITIVE
                self._transition(event_id, terminal_state)
                self._state_machines.pop(event_id, None)
            else:
                event["status"] = status
                if status == "ACKNOWLEDGED":
                    self._transition(event_id, EventState.ACKNOWLEDGED)
            return
