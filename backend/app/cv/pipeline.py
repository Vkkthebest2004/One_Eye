import asyncio
import time
import logging
from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from app.cv.source import CameraSource
from app.cv.detector import Detector, Detection
from app.cv.tracker import MultiObjectTracker, Track
from app.cv.ppe import PPEEngine, PPEStatus
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
from app.config import settings

logger = logging.getLogger(__name__)


class CameraPipeline:
    """
    Real-time safety analysis pipeline for a single camera stream.
    Executes: Detection -> Tracking -> Spatial Reasoning -> Hazard Assessment -> Risk -> Dispatch.
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

        # Operational State
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.latest_frame: Optional[np.ndarray] = None
        self.latest_detections: List[Dict] = []
        self.latest_tracks: List[Dict] = []
        self.measured_fps: float = 0.0
        self.avg_inference_ms: float = 0.0
        self.active_tracks_count: int = 0
        self._inference_in_flight: bool = False
        self._ai_interval: float = 0.12  # Run YOLO ~8 times/sec without stalling 30fps video stream

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[{self.camera_id}] Pipeline started for source {self.source_uri}")

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.source.release()
        logger.info(f"[{self.camera_id}] Pipeline stopped")

    async def _run_loop(self):
        # Connect to camera source
        if not self.source.connect():
            logger.warning(f"[{self.camera_id}] Failed initial connection. Will retry in loop...")

        last_inference_time = 0.0
        fps_timer = time.time()
        fps_frame_count = 0
        target_frame_time = 1.0 / 30.0  # 30 FPS video ingestion

        while self.is_running:
            loop_start = time.time()

            # Read frame
            ret, frame, timestamp = self.source.read()
            if not ret or frame is None:
                await self.dispatcher.broadcast_camera_status(self.camera_id, "OFFLINE", 0.0)
                await asyncio.sleep(0.1)
                continue

            self.latest_frame = frame
            fps_frame_count += 1

            # Compute measured FPS every 1 second
            if time.time() - fps_timer >= 1.0:
                self.measured_fps = fps_frame_count / (time.time() - fps_timer)
                fps_frame_count = 0
                fps_timer = time.time()

            # Non-blocking AI Hazard Inference (runs concurrently in background task)
            if (loop_start - last_inference_time) >= self._ai_interval and not self._inference_in_flight:
                last_inference_time = loop_start
                if pipeline_manager.ai_enabled:
                    self._inference_in_flight = True
                    # Launch inference asynchronously so frame loop keeps streaming at full 30 FPS
                    asyncio.create_task(self._process_frame_async(frame.copy(), timestamp))
                else:
                    self.latest_detections = []
                    self.latest_tracks = []
                    self.active_tracks_count = 0
                    self.avg_inference_ms = 0.0

            # Sleep precisely for 30 FPS cadence
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

        # 1. Object Detection
        detections = self.detector.predict(frame)

        # 2. Multi-Object Tracking
        active_tracks = self.tracker.update(detections, timestamp)
        self.active_tracks_count = len(active_tracks)

        # 3. Fire / Smoke Detection
        fire_smoke_results = self.fire_detector.detect(frame)
        for fs in fire_smoke_results:
            fs_assessment = self.risk_engine.evaluate(
                worker_id=None,
                active_hazards=[f"{fs.hazard_type}_DETECTED"],
                detection_confidence=fs.confidence
            )
            # High priority dispatch for fire
            if fs_assessment.risk_score >= 80:
                await self.event_manager.process_assessment(
                    camera_id=self.camera_id,
                    assessment=fs_assessment,
                    frame=frame,
                    is_demo=settings.DEMO_MODE,
                    alert_dispatcher=self.dispatcher
                )

        # 4. Worker-level Hazard & Risk Evaluation
        for track in active_tracks:
            worker_id = track.track_id
            foot_x, foot_y = track.foot_anchor
            bbox = track.bbox
            worker_hazards: List[str] = []

            # A. PPE Verification
            # Crop head & torso
            bx1, by1, bx2, by2 = [int(v) for v in bbox]
            bx1, by1 = max(0, bx1), max(0, by1)
            bx2, by2 = min(w, bx2), min(h, by2)
            
            head_crop = frame[by1:min(h, by1 + int((by2 - by1) * 0.3)), bx1:bx2] if by2 > by1 and bx2 > bx1 else None
            torso_crop = frame[by1 + int((by2 - by1) * 0.2):by1 + int((by2 - by1) * 0.6), bx1:bx2] if by2 > by1 and bx2 > bx1 else None

            ppe_status = self.ppe_engine.analyze_worker(
                worker_id=worker_id,
                head_crop=head_crop,
                torso_crop=torso_crop,
                explicit_helmet=track.has_helmet,
                explicit_vest=track.has_vest,
                timestamp=timestamp
            )
            if not ppe_status.has_helmet:
                worker_hazards.append("NO_HELMET")
            if not ppe_status.has_vest:
                worker_hazards.append("NO_VEST")

            # B. Restricted Zones
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

            # C. Worker-Machine Proximity
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

            # D. Fall Detection
            fall_status = self.fall_detector.evaluate_worker(
                worker_id=worker_id,
                bbox=bbox,
                velocity=track.velocity,
                timestamp=timestamp
            )
            track.is_fallen = fall_status.is_fall
            if fall_status.is_fall:
                worker_hazards.append("WORKER_FALL")

            # E. Temporal Exposure Tracking
            has_any_hazard = len(worker_hazards) > 0
            primary_hazard_key = worker_hazards[0] if has_any_hazard else "NONE"
            
            exposure_rec = self.exposure_tracker.update_exposure(
                camera_id=self.camera_id,
                worker_id=worker_id,
                hazard_key=primary_hazard_key,
                is_hazard_present=has_any_hazard,
                timestamp=timestamp
            )

            # F. Compound 0-100 Risk Scoring
            assessment = self.risk_engine.evaluate(
                worker_id=worker_id,
                active_hazards=worker_hazards,
                exposure_duration_sec=exposure_rec.duration_seconds,
                proximity_distance_m=min_dist,
                detection_confidence=track.confidence
            )
            track.current_risk_score = assessment.risk_score

            # G. Event Lifecycle & Deduplication Dispatch
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

        # Record inference time
        self.avg_inference_ms = round((time.time() - t0) * 1000, 1)

        # Broadcast live detection overlay updates to connected frontend clients
        self.latest_detections = [d.to_dict() for d in detections]
        self.latest_tracks = [t.to_dict() for t in active_tracks]

        await self.dispatcher.broadcast_detection_update(
            camera_id=self.camera_id,
            detections=self.latest_detections,
            tracks=self.latest_tracks,
            fps=self.measured_fps
        )


class CameraPipelineManager:
    """
    Manages concurrent multi-camera execution pipelines.
    """
    def __init__(self):
        self.pipelines: Dict[str, CameraPipeline] = {}
        self.ai_enabled: bool = True
        self.detector = Detector(
            model_path=settings.YOLO_MODEL_PATH,
            confidence_threshold=settings.YOLO_CONFIDENCE,
            device=settings.MODEL_DEVICE
        )
        self.evidence_manager = EvidenceManager(base_dir=str(settings.get_evidence_dir()))
        self.event_manager = EventManager(evidence_manager=self.evidence_manager)

    def toggle_ai(self, enabled: Optional[bool] = None) -> bool:
        """Toggle AI scanning engine on or off across all active camera pipelines."""
        if enabled is not None:
            self.ai_enabled = enabled
        else:
            self.ai_enabled = not self.ai_enabled
        logger.info(f"AI Safety Inference Engine status changed to: {self.ai_enabled}")
        return self.ai_enabled

    def register_camera(self, camera_id: str, source_uri: str, target_fps: int = 12) -> CameraPipeline:
        if camera_id in self.pipelines:
            return self.pipelines[camera_id]

        pipeline = CameraPipeline(
            camera_id=camera_id,
            source_uri=source_uri,
            detector=self.detector,
            evidence_manager=self.evidence_manager,
            event_manager=self.event_manager,
            alert_dispatcher=dispatcher,
            target_fps=target_fps
        )
        self.pipelines[camera_id] = pipeline
        return pipeline

    def start_camera(self, camera_id: str):
        if camera_id in self.pipelines:
            self.pipelines[camera_id].start()

    def start_all(self):
        for p in self.pipelines.values():
            p.start()

    async def stop_all(self):
        for p in self.pipelines.values():
            await p.stop()

    def get_pipeline(self, camera_id: str) -> Optional[CameraPipeline]:
        return self.pipelines.get(camera_id)


pipeline_manager = CameraPipelineManager()
