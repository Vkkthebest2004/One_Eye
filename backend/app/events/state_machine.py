import logging
from enum import Enum
from typing import Set, Dict, Optional
import datetime

logger = logging.getLogger(__name__)


class EventState(str, Enum):
    MONITORING = "MONITORING"
    DETECTED = "DETECTED"
    REASONING = "REASONING"
    EVALUATING = "EVALUATING"
    CLASSIFIED = "CLASSIFIED"
    ALERTING = "ALERTING"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    LOGGED = "LOGGED"
    FALSE_POSITIVE = "FALSE_POSITIVE"


class EventStateMachine:
    """
    Explicit Hazard Lifecycle State Machine.
    Enforces valid state transitions and audit history.
    """
    VALID_TRANSITIONS: Dict[EventState, Set[EventState]] = {
        EventState.MONITORING: {EventState.DETECTED},
        EventState.DETECTED: {EventState.REASONING, EventState.EVALUATING, EventState.MONITORING},
        EventState.REASONING: {EventState.EVALUATING, EventState.MONITORING},
        EventState.EVALUATING: {EventState.CLASSIFIED, EventState.MONITORING},
        EventState.CLASSIFIED: {EventState.ALERTING, EventState.MONITORING},
        EventState.ALERTING: {EventState.ACKNOWLEDGED, EventState.RESOLVED, EventState.FALSE_POSITIVE, EventState.ALERTING},
        EventState.ACKNOWLEDGED: {EventState.RESOLVED, EventState.ALERTING, EventState.FALSE_POSITIVE},
        EventState.RESOLVED: {EventState.LOGGED},
        EventState.FALSE_POSITIVE: {EventState.LOGGED},
        EventState.LOGGED: set()
    }

    def __init__(self, initial_state: EventState = EventState.MONITORING):
        self.current_state: EventState = initial_state
        self.history = [(initial_state, datetime.datetime.utcnow())]

    def can_transition_to(self, next_state: EventState) -> bool:
        allowed = self.VALID_TRANSITIONS.get(self.current_state, set())
        return next_state in allowed

    def transition_to(self, next_state: EventState) -> bool:
        if self.can_transition_to(next_state):
            prev = self.current_state
            self.current_state = next_state
            self.history.append((next_state, datetime.datetime.utcnow()))
            logger.debug(f"State transition: {prev.value} -> {next_state.value}")
            return True
        else:
            logger.warning(f"Illegal state transition attempted: {self.current_state.value} -> {next_state.value}")
            return False
