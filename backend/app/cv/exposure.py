import time
import logging
from typing import Dict, Tuple, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ExposureRecord:
    worker_id: int
    hazard_key: str
    camera_id: str
    start_time: float
    last_seen: float
    duration_seconds: float
    is_active: bool
    escalation_level: int # 0=initial, 1=moderate, 2=high, 3=critical


class ExposureTracker:
    """
    Temporal Exposure Tracking Engine.
    Tracks how long a worker has remained exposed to a specific unsafe condition,
    dynamically scaling risk over time.
    """
    def __init__(
        self,
        inactivity_timeout_sec: float = 3.0,
        escalation_intervals: Tuple[float, float, float] = (2.0, 5.0, 8.0)
    ):
        self.inactivity_timeout_sec = inactivity_timeout_sec
        self.escalation_intervals = escalation_intervals
        # (camera_id, worker_id, hazard_key) -> ExposureRecord
        self.records: Dict[Tuple[str, int, str], ExposureRecord] = {}

    def update_exposure(
        self,
        camera_id: str,
        worker_id: int,
        hazard_key: str,
        is_hazard_present: bool,
        timestamp: Optional[float] = None
    ) -> ExposureRecord:
        now = timestamp or time.time()
        key = (camera_id, worker_id, hazard_key)

        if is_hazard_present:
            if key not in self.records or not self.records[key].is_active:
                # Start new exposure tracking
                rec = ExposureRecord(
                    worker_id=worker_id,
                    hazard_key=hazard_key,
                    camera_id=camera_id,
                    start_time=now,
                    last_seen=now,
                    duration_seconds=0.0,
                    is_active=True,
                    escalation_level=0
                )
                self.records[key] = rec
            else:
                # Accumulate duration
                rec = self.records[key]
                rec.last_seen = now
                rec.duration_seconds = round(now - rec.start_time, 1)
                rec.is_active = True

                # Compute escalation level based on duration
                dur = rec.duration_seconds
                if dur >= self.escalation_intervals[2]: # >= 8s
                    rec.escalation_level = 3
                elif dur >= self.escalation_intervals[1]: # >= 5s
                    rec.escalation_level = 2
                elif dur >= self.escalation_intervals[0]: # >= 2s
                    rec.escalation_level = 1
                else:
                    rec.escalation_level = 0
            return self.records[key]
        else:
            if key in self.records and self.records[key].is_active:
                rec = self.records[key]
                # Check if inactive timeout exceeded
                if now - rec.last_seen > self.inactivity_timeout_sec:
                    rec.is_active = False
                    rec.duration_seconds = round(rec.last_seen - rec.start_time, 1)
                return rec
            
            # Return dummy inactive record if not tracked
            return ExposureRecord(
                worker_id=worker_id,
                hazard_key=hazard_key,
                camera_id=camera_id,
                start_time=now,
                last_seen=now,
                duration_seconds=0.0,
                is_active=False,
                escalation_level=0
            )

    def cleanup_old_records(self, max_age_seconds: float = 300.0, current_time: Optional[float] = None):
        now = current_time or time.time()
        to_delete = []
        for key, rec in self.records.items():
            if not rec.is_active and (now - rec.last_seen > max_age_seconds):
                to_delete.append(key)
        for k in to_delete:
            del self.records[k]
