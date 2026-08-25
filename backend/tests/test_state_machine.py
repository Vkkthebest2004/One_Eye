import pytest
from app.events.state_machine import EventStateMachine, EventState


def test_event_state_machine_legal_transitions():
    sm = EventStateMachine(initial_state=EventState.MONITORING)
    assert sm.current_state == EventState.MONITORING

    # Legal: MONITORING -> DETECTED
    assert sm.transition_to(EventState.DETECTED) is True
    assert sm.current_state == EventState.DETECTED

    # Legal: DETECTED -> EVALUATING
    assert sm.transition_to(EventState.EVALUATING) is True
    assert sm.current_state == EventState.EVALUATING

    # Legal: EVALUATING -> CLASSIFIED
    assert sm.transition_to(EventState.CLASSIFIED) is True

    # Legal: CLASSIFIED -> ALERTING
    assert sm.transition_to(EventState.ALERTING) is True

    # Legal: ALERTING -> ACKNOWLEDGED
    assert sm.transition_to(EventState.ACKNOWLEDGED) is True

    # Legal: ACKNOWLEDGED -> RESOLVED
    assert sm.transition_to(EventState.RESOLVED) is True

    # Legal: RESOLVED -> LOGGED
    assert sm.transition_to(EventState.LOGGED) is True


def test_event_state_machine_illegal_transition():
    sm = EventStateMachine(initial_state=EventState.MONITORING)
    
    # Illegal: Cannot jump directly from MONITORING to RESOLVED
    assert sm.transition_to(EventState.RESOLVED) is False
    assert sm.current_state == EventState.MONITORING
