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
from app.cv.visual_memory import visual_memory_engine, TrackedVisualZone
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
        target_fps: int = 30
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
        self.yolo_detector = detector
        self._qwen_detector = None
        from app.cv.intrusion import IntrusionDetector
        self.intrusion_detector = IntrusionDetector(evidence_dir=str(settings.get_evidence_dir() / "intrusions"))
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
        from app.cv.retrospective import RollingSequenceBuffer
        self.sequence_buffer = RollingSequenceBuffer(camera_id=self.camera_id, max_seconds=75.0, sample_fps=5.0)
        self._cleanup_counter: int = 0

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
        self._local_lock = asyncio.Lock()
        self._prev_small_gray: Optional[np.ndarray] = None
        self._last_full_eval_time: float = 0.0
        self._last_fire_check_time: float = 0.0

    @property
    def qwen_detector(self):
        if self._qwen_detector is None:
            from app.cv.detector import QwenVLDetector
            self._qwen_detector = QwenVLDetector(fallback_detector=self.yolo_detector)
        return self._qwen_detector

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info(f"[{self.camera_id}] Pipeline online for source {self.source_uri}")

    async def stop(self):
        if not self.is_running and self._task is None:
            return
        self.is_running = False
        task = self._task
        self._task = None
        if task and not task.done():
            try:
                # Give task up to 1.0s to finish loop gracefully
                await asyncio.wait_for(asyncio.shield(task), timeout=1.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass
            except Exception as e:
                logger.warning(f"[{self.camera_id}] Error waiting for pipeline loop to finish: {e}")

        try:
            await asyncio.to_thread(self.source.release)
        except Exception as e:
            logger.warning(f"[{self.camera_id}] Error releasing camera source: {e}")

        self.latest_frame = None
        self.latest_detections = []
        self.latest_tracks = []
        self.measured_fps = 0.0
        self.active_tracks_count = 0
        try:
            await self.dispatcher.broadcast_camera_status(self.camera_id, "OFFLINE", 0.0)
        except Exception:
            pass
        logger.info(f"[{self.camera_id}] Pipeline stopped and camera hardware released")

    async def _run_loop(self):
        try:
            if not await asyncio.to_thread(self.source.connect):
                logger.warning(f"[{self.camera_id}] Initial connection pending. Reconnection active.")

            last_inference_time = 0.0
            fps_timer = time.time()
            fps_frame_count = 0
            target_frame_time = self.frame_interval

            last_frame_received_time = time.time()
            while self.is_running:
                loop_start = time.time()

                ret, frame, timestamp = await asyncio.to_thread(self.source.read)
                if not self.is_running:
                    break
                if not ret or frame is None:
                    if (loop_start - last_frame_received_time) > 5.0:
                        await self.dispatcher.broadcast_camera_status(self.camera_id, "OFFLINE", 0.0)
                    await asyncio.sleep(0.05)
                    continue

                last_frame_received_time = loop_start
                self.latest_frame = frame
                fps_frame_count += 1

                # Feed rolling 60s sequence buffer (internally throttled to sample_fps)
                max_risk_now = max((t.get("current_risk_score", 0) for t in self.latest_tracks), default=0)
                active_hazards_now = set()
                for t in self.latest_tracks:
                    active_hazards_now.update(t.get("hazards", []))
                self.sequence_buffer.append(
                    frame=frame,
                    tracks=self.latest_tracks,
                    detections=self.latest_detections,
                    active_hazards=list(active_hazards_now),
                    max_risk=max_risk_now
                )

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
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{self.camera_id}] Error in run loop: {e}")

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

        # Motion-Gated Inference: If scene is static and no active tracks, skip neural pass
        import cv2
        skip_neural = False
        small_gray = cv2.cvtColor(cv2.resize(frame, (160, 90), interpolation=cv2.INTER_NEAREST), cv2.COLOR_BGR2GRAY)
        if self._prev_small_gray is not None and self.active_tracks_count == 0:
            diff = float(np.mean(cv2.absdiff(small_gray, self._prev_small_gray)))
            if diff < 2.0 and (timestamp - self._last_full_eval_time) < 1.0:
                skip_neural = True
        self._prev_small_gray = small_gray

        if skip_neural:
            self.avg_inference_ms = 0.5
            return

        self._last_full_eval_time = timestamp

        # 1. Primary High-Speed Concurrent Perception (YOLOv8 MPS ~12ms / Qwen2-VL)
        mode = pipeline_manager.perception_mode
        active_detector = self.qwen_detector if mode == "QWEN_VL" else self.yolo_detector
        detections = await asyncio.to_thread(active_detector.predict, frame)

        # Separate detected PPE items for spatial association
        detected_ppe_items: List[PPEItem] = []
        for d in detections:
            if d.category in ("PPE_HELMET", "NO_HELMET", "PPE_VEST", "NO_VEST", "PPE_GLASSES", "NO_GLASSES"):
                detected_ppe_items.append(PPEItem(
                    item_type=d.category,
                    confidence=d.confidence,
                    bbox=d.bbox,
                    center=d.center
                ))

        # 2. Multi-Object Tracking (ByteTrack)
        active_tracks = self.tracker.update(detections, timestamp)
        self.active_tracks_count = len(active_tracks)

        # 3. Fire & Smoke Detection Branch (Checked every 1.5 seconds)
        fire_smoke_results = []
        if (timestamp - self._last_fire_check_time) >= 1.5:
            self._last_fire_check_time = timestamp
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

        # 3.4. Precision Restricted Zone Intrusion Detection (MediaPipe Hands + Point-in-Polygon)
        active_camera_zones = [
            z for z in self.zone_engine.zones.values()
            if (z.camera_id == self.camera_id or (self.camera_id.startswith("CAM_MOB") and z.camera_id.startswith("CAM_MOB"))) and z.active
        ]
        intrusion_events = []
        if active_camera_zones and (self.active_tracks_count > 0 or len(detections) > 0):
            intrusion_events = await asyncio.to_thread(
                self.intrusion_detector.detect_intrusions,
                frame,
                active_camera_zones,
                self.camera_id,
                timestamp
            )
        self.latest_intrusions = intrusion_events
        for ie in intrusion_events:
            if ie.intruded:
                assessment = self.risk_engine.evaluate(
                    worker_id=None,
                    active_hazards=[f"ZONE_INTRUSION_{ie.zone_id}"],
                    detection_confidence=0.96
                )
                assessment.risk_score = max(assessment.risk_score, 90)
                await self.event_manager.process_assessment(
                    camera_id=self.camera_id,
                    assessment=assessment,
                    frame=frame,
                    is_demo=settings.DEMO_MODE,
                    alert_dispatcher=self.dispatcher
                )

        # 3.5. Visual Danger Memory & Dynamic Homography Tracking
        is_mobile_feed = self.camera_id.startswith("CAM_MOB") or self.camera_id == "CAM_MOBILE"
        tracked_visual_zones = visual_memory_engine.track_live_frame(frame, self.camera_id)
        
        for tvz in tracked_visual_zones:
            if tvz.is_visible and len(tvz.polygon_norm) >= 3:
                # The physical object is recognized in current camera frame -> Lock zone to object
                self.zone_engine.register_zone(
                    ZoneDefinition(
                        id=tvz.zone_id,
                        name=tvz.name,
                        camera_id=self.camera_id,
                        polygon_points=tvz.polygon_norm,
                        severity=tvz.severity,
                        active=True,
                    )
                )
            else:
                # The physical object is OUT OF VIEW -> Deactivate zone to prevent false alarms
                if tvz.zone_id in self.zone_engine.zones:
                    self.zone_engine.zones[tvz.zone_id].active = False

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
                explicit_helmet=None,
                explicit_vest=None,
                timestamp=timestamp
            )
            track.has_helmet = ppe_status.has_helmet
            track.has_vest = ppe_status.has_vest
            track.has_glasses = ppe_status.has_glasses
            track.helmet_confidence = ppe_status.helmet_confidence
            track.vest_confidence = ppe_status.vest_confidence
            track.glasses_confidence = ppe_status.glasses_confidence
            track.requires_vlm = ppe_status.requires_vlm_disambiguation

            if ppe_status.is_violation and not ppe_status.has_helmet:
                worker_hazards.append("NO_HELMET")
            if ppe_status.is_violation and not ppe_status.has_vest:
                worker_hazards.append("NO_VEST")
            if ppe_status.is_violation and not ppe_status.has_glasses and "SAFETY_GLASSES" in ppe_status.missing_items:
                worker_hazards.append("NO_GLASSES")

            # B. Restricted Zone Geofencing (Point-in-Polygon & Spatial Intersection)
            zone_events = self.zone_engine.evaluate_worker(
                worker_id=worker_id,
                foot_x=foot_x,
                foot_y=foot_y,
                timestamp=timestamp,
                camera_id=self.camera_id,
                frame_w=w,
                frame_h=h,
                bbox=bbox,
                center_x=track.center[0],
                center_y=track.center[1]
            )
            for ze in zone_events:
                if ze.state in ("ENTERED", "INSIDE"):
                    worker_hazards.append("DANGER_ZONE_REACHED")
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
                keypoints=track.keypoints,
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
                detection_confidence=track.confidence,
                timestamp=timestamp
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

        # Cleanup removed worker tracks across all state tracking subsystems
        for rem_id in getattr(self.tracker, "latest_removed_ids", []):
            self.ppe_engine.cleanup_worker(rem_id)
            self.fall_detector.cleanup_worker(rem_id)
            self.risk_engine.cleanup_worker(rem_id)
            self.exposure_tracker.reset(self.camera_id, rem_id)

        # Periodic memory hygiene & state prune (every ~10-15 seconds / 150 frames)
        self._cleanup_counter += 1
        if self._cleanup_counter >= 150:
            self._cleanup_counter = 0
            self.exposure_tracker.cleanup_old_records(max_age_seconds=30.0, current_time=timestamp)
            self.fall_detector.cleanup_stale_workers(max_age_seconds=60.0, current_time=timestamp)
            self.ppe_engine.cleanup_stale_workers(max_age_seconds=60.0, current_time=timestamp)
            self.risk_engine.cleanup_stale_workers({t.track_id for t in active_tracks}, max_idle_sec=30.0, now=timestamp)
            import gc, torch
            gc.collect()
            if torch.backends.mps.is_available():
                torch.mps.empty_cache()

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

        visual_zones_payload = [
            {
                "zone_id": tvz.zone_id,
                "name": tvz.name,
                "polygon": tvz.polygon_norm,
                "is_visible": tvz.is_visible,
                "confidence": tvz.match_confidence,
                "inlier_count": tvz.inlier_count,
            }
            for tvz in tracked_visual_zones
        ]

        intrusions_payload = [
            {
                "zone_id": ie.zone_id,
                "zone_name": ie.zone_name,
                "intruded": ie.intruded,
                "contact_points": ie.contact_points,
                "norm_contact_points": ie.norm_contact_points,
                "intrusion_points": ie.norm_contact_points,
                "intrusion_type": ie.intrusion_type,
            }
            for ie in getattr(self, "latest_intrusions", []) if ie.intruded
        ]

        await self.dispatcher.broadcast_detections(
            camera_id=self.camera_id,
            detections=self.latest_detections,
            tracks=self.latest_tracks,
            fps=self.measured_fps,
            latency_ms=self.avg_inference_ms,
            visual_zones=visual_zones_payload,
            intrusions=intrusions_payload,
        )


class PipelineManager:
    def __init__(self):
        self.pipelines: Dict[str, CameraPipeline] = {}
        self.ai_enabled: bool = True
        self.perception_mode: str = getattr(settings, "DEFAULT_PERCEPTION_MODE", "YOLO") # "YOLO" | "QWEN_VL" | "HYBRID"
        self.inference_lock: asyncio.Lock = asyncio.Lock()
        self._shared_detector = None

    def get_shared_detector(self):
        if self._shared_detector is None:
            from app.cv.detector import Detector
            self._shared_detector = Detector(
                model_path=getattr(settings, "YOLO_MODEL_PATH", "yolov8n.pt"),
                confidence_threshold=getattr(settings, "YOLO_CONFIDENCE", 0.25),
                device=getattr(settings, "MODEL_DEVICE", "mps")
            )
        return self._shared_detector

    def set_ai_enabled(self, enabled: bool):
        self.ai_enabled = enabled
        logger.info(f"System AI Hazard Scanning mode set to: {'ENABLED' if enabled else 'DISABLED (Camera-Only)'}")

    def set_perception_mode(self, mode: str) -> str:
        valid_modes = {"YOLO", "QWEN_VL", "HYBRID"}
        mode_upper = mode.upper()
        if mode_upper in valid_modes:
            self.perception_mode = mode_upper
            logger.info(f"Switched system perception engine mode to: {self.perception_mode}")
        return self.perception_mode

    def register(self, pipeline: CameraPipeline):
        self.pipelines[pipeline.camera_id] = pipeline
        pipeline.start()

    def register_camera(self, camera_id: str, source_uri: str) -> CameraPipeline:
        """Register a camera by ID and source URI and start its pipeline immediately."""
        if camera_id in self.pipelines:
            existing = self.pipelines[camera_id]
            if existing.source_uri == source_uri and existing.is_running:
                return existing
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(existing.stop())
            except RuntimeError:
                pass

        from app.cv.evidence import EvidenceManager
        from app.events.event_manager import EventManager
        from app.alerts.dispatcher import dispatcher

        pipeline = CameraPipeline(
            camera_id=camera_id,
            source_uri=source_uri,
            detector=self.get_shared_detector(),
            evidence_manager=EvidenceManager(),
            event_manager=EventManager(),
            alert_dispatcher=dispatcher,
        )
        self.register(pipeline)
        return pipeline

    def start_camera(self, camera_id: str) -> bool:
        """Start or ensure a camera pipeline is running."""
        p = self.get(camera_id)
        if p:
            if not p.is_running:
                p.start()
            return True
        return False

    async def stop_camera(self, camera_id: str) -> bool:
        """Stop camera pipeline and release hardware resources without unregistering."""
        p = self.get(camera_id)
        if p and p.is_running:
            await p.stop()
            return True
        return False

    def is_camera_running(self, camera_id: str) -> bool:
        p = self.get(camera_id)
        return bool(p and p.is_running)

    async def remove_camera(self, camera_id: str):
        """Remove and stop a camera pipeline."""
        await self.unregister(camera_id)

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
