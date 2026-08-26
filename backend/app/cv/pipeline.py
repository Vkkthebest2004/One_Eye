import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from app.cv.source import CameraSource
from app.cv.detector import Detector, Detection
from app.cv.tracker import MultiObjectTracker, Track
from app.cv.ppe import PPEEngine, PPEItem, PPEStatus
from app.cv.zones import ZoneEngine, ZoneDefinition, ZoneEvent
from app.cv.homography import HomographyCalibrator
from app.cv.proximity import ProximityEngine, MachineDefinition, ProximityResult
from app.cv.exposure import ExposureTracker
from app.cv.fall import FallDetector
from app.cv.fire_smoke import FireSmokeDetector
from app.cv.evidence import EvidenceManager
from app.risk.engine import RiskEngine
from app.events.event_manager import EventManager
from app.alerts.dispatcher import dispatcher, AlertDispatcher
from app.reasoning.interface import QwenReasoner, NoOpReasoner
from app.config import settings

logger = logging.getLogger(__name__)


class CameraPipeline:
    """
    Production-Grade Multi-Stage Safety Decision Pipeline for a single camera feed.
    
    Architecture Progression:
    1. Video Ingestion: 30-60 FPS unblocked streaming.
    2. Primary Perception: YOLO object/person/machine/fire detector (Apple Silicon MPS).
    3. Multi-Object Tracking: ByteTrack persistent identity continuity.
    4. PPE Association: Spatial Head & Body ROI containment matching.
    5. Spatial Geometry: Point-in-polygon restricted zones & 3x3 Planar Homography distance.
    6. Pose & Fall: 4-stage temporal posture confirmation (STANDING -> FALL_CONFIRMED).
    7. Temporal Reasoning: Continuous dwell time-series exposure accumulation.
    8. Ambiguity Resolution: Qwen3-VL VLM layer (invoked ONLY on ambiguous cases).
    9. Compound Risk Engine: 0-100 score with multi-hazard synergy bonus rules.
    10. Event State Machine: Complete lifecycle management & forensic snapshot logging.
    """
    def __init__(
        self,
        camera_id: str,
        source_uri: str,
        detector: Detector,
        evidence_manager: EvidenceManager,
        event_manager: EventManager,
        alert_dispatcher: AlertDispatcher = dispatcher,
        target_fps: int = 12
    ):
        self.camera_id = camera_id
        self.source_uri = source_uri
        self.detector = detector
        self.evidence_manager = evidence_manager
        self.event_manager = event_manager
        self.dispatcher = alert_dispatcher
        self.target_fps = target_fps
        self.frame_interval = 1.0 / max(1, target_fps)

        # Core CV Subsystems
        self.source = CameraSource(camera_id=camera_id, source=source_uri, loop=True)
        self.tracker = MultiObjectTracker()
        self.ppe_engine = PPEEngine(persistence_threshold_sec=1.0)
        self.zone_engine = ZoneEngine()
        self.homography = HomographyCalibrator(camera_id=camera_id)
        self.proximity_engine = ProximityEngine()
        self.exposure_tracker = ExposureTracker()
        self.fall_detector = FallDetector()
        self.fire_detector = FireSmokeDetector()
        self.risk_engine = RiskEngine()
        self.reasoner = QwenReasoner() if (settings.ENABLE_QWEN and settings.QWEN_API_KEY) else NoOpReasoner()

        # Operational State
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_detections: List[Dict[str, Any]] = []
        self.latest_tracks: List[Dict[str, Any]] = []
        self.measured_fps: float = 0.0
        self.avg_inference_ms: float = 0.0
        self.active_tracks_count: int = 0
        self._inference_in_flight: bool = False
        self._ai_interval: float = 1.0 / max(1, settings.INFERENCE_FPS)
        self._inference_lock: Optional[asyncio.Lock] = None

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[{self.camera_id}] Pipeline online for source {self.source_uri}")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        await asyncio.to_thread(self.source.release)
        logger.info(f"[{self.camera_id}] Pipeline stopped")

    async def _run_loop(self):
        if not await asyncio.to_thread(self.source.connect):
            logger.warning(f"[{self.camera_id}] Initial connection pending. Reconnection active.")

        last_inference_time = 0.0
        fps_timer = time.time()
        fps_frame_count = 0
        target_frame_time = self.frame_interval

        while self.is_running:
            loop_start = time.time()

            ret, frame, timestamp = await asyncio.to_thread(self.source.read)
            if not ret or frame is None:
                await self.dispatcher.broadcast_camera_status(self.camera_id, "OFFLINE", 0.0)
                await asyncio.sleep(0.1)
                continue

            self.latest_frame = frame
            fps_frame_count += 1

            if time.time() - fps_timer >= 1.0:
                self.measured_fps = fps_frame_count / (time.time() - fps_timer)
                fps_frame_count = 0
                fps_timer = time.time()

            # Non-blocking AI Hazard Inference
            if (loop_start - last_inference_time) >= self._ai_interval and not self._inference_in_flight:
                last_inference_time = loop_start
                if pipeline_manager.ai_enabled:
                    self._inference_in_flight = True
                    asyncio.create_task(self._process_frame_async(frame.copy(), timestamp))
                else:
                    self.latest_detections = []
                    self.latest_tracks = []
                    self.active_tracks_count = 0
                    self.avg_inference_ms = 0.0

            elapsed = time.time() - loop_start
            sleep_time = max(0.002, target_frame_time - elapsed)
            await asyncio.sleep(sleep_time)

    async def _process_frame_async(self, frame: np.ndarray, timestamp: float):
        try:
            await self._process_frame(frame, timestamp)
        except Exception as e:
            logger.warning(f"[{self.camera_id}] AI inference error: {e}")
        finally:
            self._inference_in_flight = False

    async def _process_frame(self, frame: np.ndarray, timestamp: float):
        t0 = time.time()
        h, w = frame.shape[:2]

        # 1. Primary Perception
        if self._inference_lock is None:
            self._inference_lock = pipeline_manager.inference_lock
        async with self._inference_lock:
            detections = await asyncio.to_thread(self.detector.predict, frame)

        # Separate detected PPE items for spatial association
        detected_ppe_items: List[PPEItem] = []
        for d in detections:
            if d.category in ("PPE_HELMET", "NO_HELMET", "PPE_VEST", "NO_VEST"):
                detected_ppe_items.append(PPEItem(
                    item_type=d.category,
                    confidence=d.confidence,
                    bbox=d.bbox,
                    center=d.center
                ))

        # 2. Multi-Object Tracking (ByteTrack)
        active_tracks = self.tracker.update(detections, timestamp)
        self.active_tracks_count = len(active_tracks)

        # 3. Fire & Smoke Detection Branch
        fire_smoke_results = await asyncio.to_thread(self.fire_detector.detect, frame)
        present_system_scopes = set()
        for fs in fire_smoke_results:
            fs_assessment = self.risk_engine.evaluate(
                worker_id=None,
                active_hazards=[f"{fs.hazard_type}_DETECTED"],
                detection_confidence=fs.confidence
            )
            if fs_assessment.risk_score >= 80:
                present_system_scopes.add(self.event_manager._incident_scope(fs_assessment))
                await self.event_manager.process_assessment(
                    camera_id=self.camera_id,
                    assessment=fs_assessment,
                    frame=frame,
                    is_demo=settings.DEMO_MODE,
                    alert_dispatcher=self.dispatcher
                )

        await self.event_manager.resolve_absent_system_events(
            camera_id=self.camera_id,
            present_scopes=present_system_scopes,
            timeout_seconds=settings.TRACK_LOSS_RESOLUTION_SECONDS,
            alert_dispatcher=self.dispatcher,
            now=timestamp,
        )

        # 4. Worker-Level Spatial, Temporal, and Risk Analysis
        for track in active_tracks:
            if track.category != "PERSON":
                continue

            worker_id = track.track_id
            foot_x, foot_y = track.foot_anchor
            bbox = track.bbox
            worker_hazards: List[str] = []

            # A. PPE Spatial Association Layer
            ppe_status = self.ppe_engine.analyze_worker(
                worker_id=worker_id,
                person_bbox=bbox,
                frame=frame,
                detected_ppe_items=detected_ppe_items,
                explicit_helmet=track.has_helmet,
                explicit_vest=track.has_vest,
                timestamp=timestamp
            )
            track.has_helmet = ppe_status.has_helmet
            track.has_vest = ppe_status.has_vest
            track.helmet_confidence = ppe_status.helmet_confidence
            track.vest_confidence = ppe_status.vest_confidence
            track.requires_vlm = ppe_status.requires_vlm_disambiguation

            if ppe_status.is_violation and not ppe_status.has_helmet:
                worker_hazards.append("NO_HELMET")
            if ppe_status.is_violation and not ppe_status.has_vest:
                worker_hazards.append("NO_VEST")

            # B. Restricted Zone Geofencing (Point-in-Polygon)
            zone_events = self.zone_engine.evaluate_worker(
                worker_id=worker_id,
                foot_x=foot_x,
                foot_y=foot_y,
                timestamp=timestamp,
                camera_id=self.camera_id
            )
            for ze in zone_events:
                if ze.state in ("ENTERED", "INSIDE"):
                    worker_hazards.append("RESTRICTED_ZONE")
                    track.current_zone_id = ze.zone_id

            # C. Worker-Machine Proximity (3x3 Planar Homography)
            prox_results = self.proximity_engine.evaluate_worker(
                worker_id=worker_id,
                foot_anchor=(foot_x, foot_y),
                camera_id=self.camera_id,
                calibrator=self.homography
            )
            min_dist: Optional[float] = None
            closest_machine_id: Optional[str] = None

            for pr in prox_results:
                if min_dist is None or pr.distance_m < min_dist:
                    min_dist = pr.distance_m
                    closest_machine_id = pr.machine_id

                if pr.is_unsafe:
                    if pr.proximity_level == "CRITICAL":
                        worker_hazards.append("UNSAFE_PROXIMITY_CRITICAL")
                    elif pr.proximity_level == "DANGER":
                        worker_hazards.append("UNSAFE_PROXIMITY_DANGER")
                    elif pr.proximity_level == "WARNING":
                        worker_hazards.append("UNSAFE_PROXIMITY_WARNING")

            track.closest_machine_id = closest_machine_id
            track.closest_machine_distance_m = min_dist

            # D. Pose & Fall Detection (4-Stage Temporal Progression)
            fall_status = self.fall_detector.evaluate_worker(
                worker_id=worker_id,
                bbox=bbox,
                velocity=track.velocity,
                timestamp=timestamp
            )
            track.is_fallen = fall_status.is_fall
            track.fall_state = fall_status.state
            if fall_status.is_fall:
                worker_hazards.append("WORKER_FALL")

            # E. Temporal Exposure Dwell Tracking
            has_any_hazard = len(worker_hazards) > 0
            primary_hazard_key = worker_hazards[0] if has_any_hazard else "NONE"
            
            exposure_rec = self.exposure_tracker.update_exposure(
                camera_id=self.camera_id,
                worker_id=worker_id,
                hazard_key=primary_hazard_key,
                is_hazard_present=has_any_hazard,
                timestamp=timestamp
            )
            track.exposure_seconds = exposure_rec.duration_seconds

            # F. Qwen3-VL Ambiguity Disambiguation (Triggered only when flagged)
            if track.requires_vlm and has_any_hazard:
                asyncio.create_task(self.reasoner.analyze(frame, {
                    "worker_id": worker_id,
                    "hazard_type": primary_hazard_key
                }))

            # G. Compound 0-100 Risk Engine
            assessment = self.risk_engine.evaluate(
                worker_id=worker_id,
                active_hazards=worker_hazards,
                exposure_duration_sec=exposure_rec.duration_seconds,
                proximity_distance_m=min_dist,
                detection_confidence=track.confidence
            )
            track.current_risk_score = assessment.risk_score

            # H. Event State Machine Lifecycle & Forensic Snapshot Capture
            await self.event_manager.process_assessment(
                camera_id=self.camera_id,
                assessment=assessment,
                frame=frame,
                distance_m=min_dist,
                exposure_sec=exposure_rec.duration_seconds,
                highlight_bbox=bbox,
                is_demo=settings.DEMO_MODE,
                alert_dispatcher=self.dispatcher
            )

        await self.event_manager.resolve_stale_worker_events(
            camera_id=self.camera_id,
            seen_worker_ids={track.track_id for track in active_tracks},
            timeout_seconds=settings.TRACK_LOSS_RESOLUTION_SECONDS,
            alert_dispatcher=self.dispatcher,
            now=timestamp,
        )

        self.avg_inference_ms = round((time.time() - t0) * 1000, 1)

        # Broadcast live detection and tracking overlay updates to UI with normalized coords
        self.latest_detections = [
            {
                **d.to_dict(),
                "norm_bbox": [round(d.x1 / w, 4), round(d.y1 / h, 4), round(d.x2 / w, 4), round(d.y2 / h, 4)],
                "norm_foot": [round(d.foot_x / w, 4), round(d.foot_y / h, 4)]
            }
            for d in detections
        ]
        self.latest_tracks = [
            {
                **t.to_dict(),
                "norm_bbox": [round(t.bbox[0] / w, 4), round(t.bbox[1] / h, 4), round(t.bbox[2] / w, 4), round(t.bbox[3] / h, 4)],
                "norm_foot": [round(t.foot_anchor[0] / w, 4), round(t.foot_anchor[1] / h, 4)]
            }
            for t in active_tracks
        ]

        await self.dispatcher.broadcast_detections(
            camera_id=self.camera_id,
            detections=self.latest_detections,
            tracks=self.latest_tracks,
            fps=self.measured_fps,
            latency_ms=self.avg_inference_ms
        )


class PipelineManager:
    def __init__(self):
        self.pipelines: Dict[str, CameraPipeline] = {}
        self.ai_enabled: bool = True
        self.inference_lock: asyncio.Lock = asyncio.Lock()

    def set_ai_enabled(self, enabled: bool):
        self.ai_enabled = enabled
        logger.info(f"System AI Hazard Scanning mode set to: {'ENABLED' if enabled else 'DISABLED (Camera-Only)'}")

    def register(self, pipeline: CameraPipeline):
        self.pipelines[pipeline.camera_id] = pipeline
        pipeline.start()

    async def unregister(self, camera_id: str):
        if camera_id in self.pipelines:
            pipeline = self.pipelines.pop(camera_id)
            await pipeline.stop()

    def get(self, camera_id: str) -> Optional[CameraPipeline]:
        return self.pipelines.get(camera_id)

    def get_pipeline(self, camera_id: str) -> Optional[CameraPipeline]:
        return self.pipelines.get(camera_id)

    def toggle_ai(self, enabled: Optional[bool] = None) -> bool:
        if enabled is not None:
            self.ai_enabled = enabled
        else:
            self.ai_enabled = not self.ai_enabled
        logger.info(f"System AI Hazard Scanning toggled: {self.ai_enabled}")
        return self.ai_enabled

    async def stop_all(self):
        for p in self.pipelines.values():
            await p.stop()
        self.pipelines.clear()


# Global Singleton Pipeline Manager
pipeline_manager = PipelineManager()
