from dataclasses import replace

import pytest

from app.events.event_manager import EventManager
from app.risk.engine import RiskAssessment


class BrokenSession:
    """Avoid touching a real database while testing in-memory safety behavior."""
    async def __aenter__(self):
        raise RuntimeError("database unavailable in unit test")

    async def __aexit__(self, exc_type, exc, traceback):
        return False


class RecordingDispatcher:
    def __init__(self):
        self.alerts = []
        self.updates = []

    async def dispatch_alert(self, event):
        self.alerts.append(event)

    async def broadcast_event_update(self, **kwargs):
        self.updates.append(kwargs)


def fire_assessment() -> RiskAssessment:
    return RiskAssessment(
        worker_id=None,
        risk_score=95,
        severity="CRITICAL",
        primary_hazard="FIRE_DETECTED",
        active_hazards=["FIRE_DETECTED", "SMOKE_DETECTED"],
        confidence=0.95,
        base_severity=95,
        proximity_score=0,
        duration_score=0,
        synergy_score=0,
        rule_triggered="fire test",
        recommended_action="Evacuate.",
    )


@pytest.mark.asyncio
async def test_plant_wide_fire_event_is_dispatched(monkeypatch):
    monkeypatch.setattr("app.events.event_manager.AsyncSessionLocal", lambda: BrokenSession())
    manager = EventManager()
    dispatcher = RecordingDispatcher()

    event = await manager.process_assessment(
        camera_id="CAM_01",
        assessment=fire_assessment(),
        frame=None,
        alert_dispatcher=dispatcher,
    )

    assert event is not None
    assert event["worker_id"] == 0
    assert event["primary_hazard"] == "FIRE_DETECTED"
    assert len(dispatcher.alerts) == 1

    event["last_seen"] = 10.0
    resolved = await manager.resolve_absent_system_events(
        camera_id="CAM_01",
        present_scopes=set(),
        timeout_seconds=3.0,
        alert_dispatcher=dispatcher,
        now=14.0,
    )
    assert resolved == [event["event_id"]]
    assert dispatcher.updates[-1]["status"] == "RESOLVED"


@pytest.mark.asyncio
async def test_stale_worker_event_is_resolved(monkeypatch):
    monkeypatch.setattr("app.events.event_manager.AsyncSessionLocal", lambda: BrokenSession())
    manager = EventManager()
    dispatcher = RecordingDispatcher()
    assessment = replace(fire_assessment(), worker_id=7, primary_hazard="NO_HELMET", active_hazards=["NO_HELMET"])

    event = await manager.process_assessment(
        camera_id="CAM_01",
        assessment=assessment,
        frame=None,
        alert_dispatcher=dispatcher,
    )
    event["last_seen"] = 10.0

    resolved = await manager.resolve_stale_worker_events(
        camera_id="CAM_01",
        seen_worker_ids=set(),
        timeout_seconds=3.0,
        alert_dispatcher=dispatcher,
        now=14.0,
    )

    assert resolved == [event["event_id"]]
    assert dispatcher.updates[-1]["status"] == "RESOLVED"
