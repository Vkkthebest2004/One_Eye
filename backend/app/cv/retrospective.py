import cv2
import time
import base64
import datetime
import logging
import httpx
from collections import deque
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class SequenceSnapshot:
    """A single temporal observation snapshot within the rolling buffer."""
    __slots__ = (
        "timestamp",
        "jpeg_bytes",
        "tracks",
        "detections",
        "active_hazards",
        "max_risk",
        "motion_score",
        "worker_count"
    )

    def __init__(
        self,
        timestamp: float,
        jpeg_bytes: bytes,
        tracks: List[Dict[str, Any]],
        detections: List[Dict[str, Any]],
        active_hazards: List[str],
        max_risk: int,
        motion_score: float,
        worker_count: int
    ):
        self.timestamp = timestamp
        self.jpeg_bytes = jpeg_bytes
        self.tracks = tracks
        self.detections = detections
        self.active_hazards = active_hazards
        self.max_risk = max_risk
        self.motion_score = motion_score
        self.worker_count = worker_count


class RollingSequenceBuffer:
    """
    Rolling 60-second video & CV observation ring buffer.
    Maintains timestamped frames & telemetry in memory with zero disk wear,
    consuming ~6-10 MB of RAM per camera channel.
    """
    def __init__(self, camera_id: str, max_seconds: float = 75.0, sample_fps: float = 5.0):
        self.camera_id = camera_id
        self.max_seconds = max_seconds
        self.sample_fps = max(1.0, min(15.0, sample_fps))
        self.sample_interval = 1.0 / self.sample_fps
        self.max_snapshots = int(self.max_seconds * self.sample_fps)
        self.buffer: deque[SequenceSnapshot] = deque(maxlen=self.max_snapshots)
        self._last_sample_time: float = 0.0
        self._prev_gray: Optional[np.ndarray] = None
        self._encode_params = [cv2.IMWRITE_JPEG_QUALITY, 75]

    def append(
        self,
        frame: np.ndarray,
        tracks: List[Dict[str, Any]],
        detections: List[Dict[str, Any]],
        active_hazards: List[str],
        max_risk: int
    ):
        now = time.time()
        if (now - self._last_sample_time) < self.sample_interval:
            return

        self._last_sample_time = now

        try:
            h, w = frame.shape[:2]
            # Downscale to 640 width for ultra-lightweight in-memory storage (~20KB per frame)
            if w > 640:
                scaled = cv2.resize(frame, (640, int(h * 640.0 / w)), interpolation=cv2.INTER_LINEAR)
            else:
                scaled = frame

            # Calculate motion score relative to previous frame
            gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
            motion_score = 0.0
            if self._prev_gray is not None and self._prev_gray.shape == gray.shape:
                diff = cv2.absdiff(self._prev_gray, gray)
                motion_score = float(np.mean(diff))
            self._prev_gray = gray

            ok, jpeg = cv2.imencode(".jpg", scaled, self._encode_params)
            if not ok:
                return

            worker_count = sum(1 for t in tracks if t.get("is_worker", True))
            snapshot = SequenceSnapshot(
                timestamp=now,
                jpeg_bytes=jpeg.tobytes(),
                tracks=tracks.copy() if tracks else [],
                detections=detections.copy() if detections else [],
                active_hazards=list(active_hazards) if active_hazards else [],
                max_risk=int(max_risk),
                motion_score=round(motion_score, 2),
                worker_count=worker_count
            )
            self.buffer.append(snapshot)
        except Exception as e:
            logger.debug(f"[{self.camera_id}] Buffer append note: {e}")

    def get_snapshots(self, seconds: float = 60.0) -> List[SequenceSnapshot]:
        """Returns snapshots recorded within the last `seconds` in chronological order."""
        if not self.buffer:
            return []
        now = time.time()
        cutoff = now - seconds
        return [s for s in self.buffer if s.timestamp >= cutoff]

    def extract_critical_keyframes(self, seconds: float = 60.0, count: int = 6) -> List[Tuple[float, np.ndarray, SequenceSnapshot]]:
        """
        Samples the most informative keyframes across the sequence:
        - Beginning / baseline (00:00)
        - Key transitions (first movement, peak risk, hazard triggers)
        - Climax / latest state (00:60)
        Returns list of (rel_seconds, cv2_bgr_frame, snapshot).
        """
        snapshots = self.get_snapshots(seconds)
        if not snapshots:
            return []

        start_time = snapshots[0].timestamp
        total_span = snapshots[-1].timestamp - start_time
        if total_span <= 0:
            total_span = 1.0

        scored_candidates: List[Tuple[float, SequenceSnapshot]] = []
        for s in snapshots:
            # Score importance: risk, hazards, high motion, presence of workers
            score = float(s.max_risk)
            if s.active_hazards:
                score += 50.0
            score += min(30.0, s.motion_score * 3.0)
            scored_candidates.append((score, s))

        # Always include first and last
        selected_snapshots = [snapshots[0]]

        # Pick peak risk moment
        peak_snapshot = max(snapshots, key=lambda s: (s.max_risk, len(s.active_hazards), s.motion_score))
        if peak_snapshot not in selected_snapshots:
            selected_snapshots.append(peak_snapshot)

        # Distribute evenly across remaining slots
        step = max(1, len(snapshots) // (count - len(selected_snapshots)))
        for i in range(step, len(snapshots) - 1, step):
            if snapshots[i] not in selected_snapshots:
                selected_snapshots.append(snapshots[i])
            if len(selected_snapshots) >= count - 1:
                break

        if snapshots[-1] not in selected_snapshots:
            selected_snapshots.append(snapshots[-1])

        # Sort chronologically
        selected_snapshots.sort(key=lambda s: s.timestamp)

        results = []
        for s in selected_snapshots:
            rel_sec = round(s.timestamp - start_time, 1)
            arr = np.frombuffer(s.jpeg_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
            if img is not None:
                results.append((rel_sec, img, s))

        return results

    def export_mp4(self, output_path: str, seconds: float = 60.0) -> bool:
        """Renders the rolling sequence buffer to an MP4 video clip with timestamp watermark."""
        snapshots = self.get_snapshots(seconds)
        if len(snapshots) < 2:
            return False

        try:
            first_arr = np.frombuffer(snapshots[0].jpeg_bytes, dtype=np.uint8)
            first_img = cv2.imdecode(first_arr, cv2.IMREAD_COLOR)
            if first_img is None:
                return False

            h, w = first_img.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            out = cv2.VideoWriter(output_path, fourcc, self.sample_fps, (w, h))

            t0 = snapshots[0].timestamp
            for s in snapshots:
                arr = np.frombuffer(s.jpeg_bytes, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    continue

                rel_sec = s.timestamp - t0
                mins = int(rel_sec // 60)
                secs = int(rel_sec % 60)
                time_tag = f"T+{mins:02d}:{secs:02d} | RISK: {s.max_risk}/100"

                # Watermark banner
                cv2.rectangle(img, (10, 10), (320, 42), (20, 20, 20), -1)
                color = (0, 0, 255) if s.max_risk >= 70 else (0, 215, 255) if s.max_risk >= 40 else (0, 255, 120)
                cv2.putText(img, time_tag, (18, 32), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 2)

                out.write(img)

            out.release()
            return True
        except Exception as e:
            logger.error(f"[{self.camera_id}] Error exporting retrospective MP4: {e}")
            return False


class SequenceReconstructor:
    """
    Reconstructs an ordered, chronological event timeline from 60 seconds of video telemetry.
    """
    @staticmethod
    def reconstruct(snapshots: List[SequenceSnapshot]) -> List[Dict[str, Any]]:
        if not snapshots:
            return []

        t0 = snapshots[0].timestamp
        timeline: List[Dict[str, Any]] = []

        prev_worker_count = 0
        prev_hazards = set()
        prev_zones = set()
        prev_motion_low = False
        machine_approach_logged = set()
        ppe_violation_logged = set()

        for idx, s in enumerate(snapshots):
            rel_sec = s.timestamp - t0
            mins = int(rel_sec // 60)
            secs = int(rel_sec % 60)
            ts_str = f"{mins:02d}:{secs:02d}"

            # 1. Baseline Entry / Exit
            if s.worker_count > prev_worker_count and prev_worker_count == 0:
                timeline.append({
                    "timestamp_sec": round(rel_sec, 1),
                    "timestamp_str": ts_str,
                    "label": "Worker Arrival",
                    "description": f"Worker entered the monitored camera sector (active targets: {s.worker_count}).",
                    "category": "ACTION",
                    "risk_level": "SAFE",
                    "keyframe_index": idx
                })
            elif s.worker_count < prev_worker_count and s.worker_count == 0:
                timeline.append({
                    "timestamp_sec": round(rel_sec, 1),
                    "timestamp_str": ts_str,
                    "label": "Worker Departure",
                    "description": "Worker vacated the monitored workstation.",
                    "category": "ACTION",
                    "risk_level": "SAFE",
                    "keyframe_index": idx
                })
            prev_worker_count = s.worker_count

            # 2. Tracks & Proximity Analysis
            for t in s.tracks:
                tid = t.get("track_id", 1)
                dist = t.get("distance_to_machine")
                zone_id = t.get("current_zone_id")
                has_helmet = t.get("has_helmet", True)
                has_vest = t.get("has_vest", True)
                has_glasses = t.get("has_glasses", True)
                is_fallen = t.get("is_fallen", False)

                # Machine interaction
                if dist is not None and dist < 1.5 and tid not in machine_approach_logged:
                    machine_approach_logged.add(tid)
                    timeline.append({
                        "timestamp_sec": round(rel_sec, 1),
                        "timestamp_str": ts_str,
                        "label": "Equipment Proximity",
                        "description": f"Worker #{tid} moved within critical operating boundary of machinery ({dist:.1f}m clearance).",
                        "category": "PROCEDURE",
                        "risk_level": "WARNING" if dist < 1.0 else "SAFE",
                        "keyframe_index": idx
                    })

                # Restricted Zone Entry
                if zone_id and zone_id not in prev_zones:
                    prev_zones.add(zone_id)
                    timeline.append({
                        "timestamp_sec": round(rel_sec, 1),
                        "timestamp_str": ts_str,
                        "label": "Restricted Zone Entry",
                        "description": f"Worker #{tid} foot anchor entered perimeter '{zone_id}'.",
                        "category": "HAZARD",
                        "risk_level": "DANGER",
                        "keyframe_index": idx
                    })

                # PPE Non-Compliance Transitions
                if (not has_helmet or not has_vest or not has_glasses) and tid not in ppe_violation_logged:
                    missing = []
                    if not has_helmet: missing.append("hard hat")
                    if not has_vest: missing.append("reflective vest")
                    if not has_glasses: missing.append("safety glasses")
                    ppe_violation_logged.add(tid)
                    timeline.append({
                        "timestamp_sec": round(rel_sec, 1),
                        "timestamp_str": ts_str,
                        "label": "PPE Non-Compliance",
                        "description": f"Worker #{tid} missing required PPE ({', '.join(missing)}).",
                        "category": "HAZARD",
                        "risk_level": "WARNING",
                        "keyframe_index": idx
                    })

                # Fall / Injury
                if is_fallen:
                    timeline.append({
                        "timestamp_sec": round(rel_sec, 1),
                        "timestamp_str": ts_str,
                        "label": "Worker Fall Detected",
                        "description": f"Worker #{tid} sudden drop and horizontal aspect ratio detected (potential fall).",
                        "category": "HAZARD",
                        "risk_level": "DANGER",
                        "keyframe_index": idx
                    })

            # 3. Motion Cessation / Stall Analysis
            if s.worker_count > 0 and s.motion_score < 0.8 and not prev_motion_low and rel_sec > 10.0:
                prev_motion_low = True
                timeline.append({
                    "timestamp_sec": round(rel_sec, 1),
                    "timestamp_str": ts_str,
                    "label": "Movement Cessation",
                    "description": "Equipment and worker movement ceased abruptly; potential machine pause, stall, or waiting state.",
                    "category": "STATUS",
                    "risk_level": "SAFE",
                    "keyframe_index": idx
                })
            elif s.motion_score >= 1.5:
                prev_motion_low = False

            # 4. Critical Hazards (Fire / Smoke)
            current_hazards = set(s.active_hazards)
            new_hazards = current_hazards - prev_hazards
            for nh in new_hazards:
                if "FIRE" in nh or "SMOKE" in nh:
                    timeline.append({
                        "timestamp_sec": round(rel_sec, 1),
                        "timestamp_str": ts_str,
                        "label": f"{nh.replace('_', ' ').title()} Identified",
                        "description": f"Active thermal plume / optical disturbance observed ({nh}).",
                        "category": "HAZARD",
                        "risk_level": "DANGER",
                        "keyframe_index": idx
                    })
            prev_hazards = current_hazards

        # If no significant milestones triggered, synthesize periodic activity checkpoints
        if len(timeline) < 2:
            step = max(1, len(snapshots) // 3)
            for i in [0, step, len(snapshots) - 1]:
                if i < len(snapshots):
                    s = snapshots[i]
                    rel_sec = s.timestamp - t0
                    mins = int(rel_sec // 60)
                    secs = int(rel_sec % 60)
                    timeline.append({
                        "timestamp_sec": round(rel_sec, 1),
                        "timestamp_str": f"{mins:02d}:{secs:02d}",
                        "label": "Surveillance Checkpoint",
                        "description": f"Work area active: {s.worker_count} personnel observed; system risk at {s.max_risk}/100.",
                        "category": "STATUS",
                        "risk_level": "SAFE" if s.max_risk < 50 else "WARNING",
                        "keyframe_index": i
                    })

        timeline.sort(key=lambda x: x["timestamp_sec"])
        return timeline


class RetrospectiveEngine:
    """
    Multimodal Retrospective Intelligence Engine.
    Analyzes the 60-second video sequence, reconstructs events, evaluates deviations against
    operational SOPs, and synthesizes a professional investigation report.
    """
    def __init__(self):
        self.evidence_dir = settings.get_evidence_dir() / "retrospective"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    async def analyze_sequence(
        self,
        camera_id: str,
        buffer: RollingSequenceBuffer,
        domain: str = "INDUSTRIAL_SOP",
        custom_goal: Optional[str] = None,
        seconds: float = 60.0
    ) -> Dict[str, Any]:
        """
        Executes full 60s retrospective reconstruction, VLM reasoning, and report generation.
        """
        snapshots = buffer.get_snapshots(seconds)
        if not snapshots:
            return self._generate_empty_report(camera_id, domain)

        # 1. Reconstruct Event Timeline
        timeline = SequenceReconstructor.reconstruct(snapshots)

        # 2. Extract Critical Keyframes
        keyframes = buffer.extract_critical_keyframes(seconds=seconds, count=6)
        report_id = f"RETRO-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"

        keyframe_urls: List[str] = []
        keyframe_b64s: List[str] = []

        date_dir = self.evidence_dir / datetime.datetime.utcnow().strftime("%Y/%m/%d")
        date_dir.mkdir(parents=True, exist_ok=True)

        for rel_sec, img, s in keyframes:
            kf_filename = f"{report_id}_t{int(rel_sec):02d}s.jpg"
            kf_file = date_dir / kf_filename
            cv2.imwrite(str(kf_file), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
            rel_url = f"/evidence/retrospective/{datetime.datetime.utcnow().strftime('%Y/%m/%d')}/{kf_filename}"
            keyframe_urls.append(rel_url)

            # Downsample for VLM token efficiency
            h, w = img.shape[:2]
            vlm_img = cv2.resize(img, (480, int(h * 480.0 / w))) if w > 480 else img
            _, enc = cv2.imencode(".jpg", vlm_img, [cv2.IMWRITE_JPEG_QUALITY, 70])
            keyframe_b64s.append(base64.b64encode(enc).decode("utf-8"))

        # Map keyframe URLs to timeline items
        for t_item in timeline:
            sec = t_item["timestamp_sec"]
            # Find closest keyframe
            if keyframes:
                closest_idx = min(range(len(keyframes)), key=lambda i: abs(keyframes[i][0] - sec))
                if closest_idx < len(keyframe_urls):
                    t_item["keyframe_url"] = keyframe_urls[closest_idx]

        # 3. Export optional 60s MP4 Clip
        clip_filename = f"{report_id}_clip.mp4"
        clip_path = date_dir / clip_filename
        clip_saved = buffer.export_mp4(str(clip_path), seconds=seconds)
        clip_url = f"/evidence/retrospective/{datetime.datetime.utcnow().strftime('%Y/%m/%d')}/{clip_filename}" if clip_saved else None

        # 4. Multimodal Sequence Reasoning (Qwen3-VL / Qwen2.5-VL / Cognitive Critic)
        report = await self._run_reasoning(
            camera_id=camera_id,
            domain=domain,
            custom_goal=custom_goal,
            timeline=timeline,
            keyframe_b64s=keyframe_b64s,
            snapshots=snapshots
        )

        report["id"] = report_id
        report["camera_id"] = camera_id
        report["domain"] = domain
        report["custom_goal"] = custom_goal
        report["evidence_timeline"] = timeline
        report["keyframe_paths"] = keyframe_urls
        report["clip_path"] = clip_url
        report["analysis_duration_sec"] = float(seconds)
        report["created_at"] = datetime.datetime.utcnow().isoformat()

        return report

    async def _run_reasoning(
        self,
        camera_id: str,
        domain: str,
        custom_goal: Optional[str],
        timeline: List[Dict[str, Any]],
        keyframe_b64s: List[str],
        snapshots: List[SequenceSnapshot]
    ) -> Dict[str, Any]:
        """
        Executes sequence-level evaluation using Qwen2.5-VL / Qwen3-VL,
        falling back to the deterministic forensic sequence critic.
        """
        timeline_text = "\n".join([f"- {t['timestamp_str']} — {t['label']}: {t['description']}" for t in timeline])

        domain_rubrics = {
            "INDUSTRIAL_SOP": (
                "Domain Standard Operating Procedure: Factory floor workers must wear full PPE (hard hat, high-vis vest, "
                "safety glasses) at all times. Operators must never breach yellow/red danger perimeters without lockout/tagout. "
                "Worker must maintain 1.5m clearance from active machinery."
            ),
            "EQUIPMENT_OPERATION": (
                "Domain Equipment Operation SOP: Worker approaches machinery -> visually inspects hopper -> performs safe loading "
                "without reaching past safety barrier -> verifies clearance -> initiates restart sequence. Machinery must not be "
                "restarted while obstruction or personnel are inside perimeter."
            ),
            "SECURITY_PERIMETER": (
                "Domain Security Protocol: Monitored zone is restricted. Personnel must possess continuous authorized badges. "
                "No loitering exceeding 15 seconds. Tailgating and left-behind containers are critical deviations."
            ),
            "ERGONOMICS_SAFETY": (
                "Domain Ergonomics & Biomechanics: Lifting from knees, maintaining stable center of gravity, immediate response "
                "to trips, falls, or sudden decelerations."
            ),
            "CUSTOM": custom_goal or "Evaluate overall operational safety and procedural anomalies."
        }

        rubric = domain_rubrics.get(domain.upper(), domain_rubrics["INDUSTRIAL_SOP"])
        if custom_goal:
            rubric += f"\nSpecific Investigation Goal: {custom_goal}"

        # 1. Attempt Cloud Qwen2.5-VL / Qwen3-VL API if API key configured
        if settings.ENABLE_QWEN and settings.QWEN_API_KEY and keyframe_b64s:
            try:
                system_prompt = (
                    "You are ONE EYE Senior Industrial Operations & Safety Investigation AI. "
                    "Analyze the 1-minute sequence of events, diagnose what happened, identify mistakes or procedural "
                    "deviations against the SOP, and provide concrete recommendations.\n"
                    "Respond ONLY with a JSON object in this exact schema:\n"
                    "{\n"
                    '  "what_happened": "summary narrative of the minute",\n'
                    '  "what_went_wrong": "deviations from SOP or abnormal patterns observed",\n'
                    '  "possible_explanation": "root-cause hypotheses and technical context",\n'
                    '  "recommended_next_steps": ["step 1", "step 2", "step 3"],\n'
                    '  "severity": "SAFE" | "LOW" | "MEDIUM" | "HIGH" | "CRITICAL"\n'
                    "}"
                )

                content_items: List[Dict[str, Any]] = [
                    {"type": "text", "text": f"{rubric}\n\nReconstructed 60s Timeline:\n{timeline_text}\n\nKeyframes Sequence:"}
                ]
                for b64 in keyframe_b64s[:4]: # Send up to 4 keyframes to balance latency & context
                    content_items.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})

                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(
                        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {settings.QWEN_API_KEY}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": settings.QWEN_MODEL_NAME or "qwen2.5-vl-7b-instruct",
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": content_items}
                            ],
                            "response_format": {"type": "json_object"},
                            "max_tokens": 600
                        }
                    )
                    if resp.status_code == 200:
                        import json
                        parsed = json.loads(resp.json()["choices"][0]["message"]["content"])
                        parsed["reasoning_engine"] = f"Qwen2.5-VL Cloud ({settings.QWEN_MODEL_NAME})"
                        return parsed
            except Exception as e:
                logger.warning(f"Cloud VLM sequence reasoning note: {e}")

        # 2. Attempt Local Ollama (qwen2.5vl:7b) if running
        if keyframe_b64s:
            try:
                prompt = (
                    f"{rubric}\n\nReconstructed 60s Timeline:\n{timeline_text}\n\n"
                    "Analyze this sequence. Return valid JSON: "
                    '{"what_happened": "...", "what_went_wrong": "...", "possible_explanation": "...", "recommended_next_steps": ["..."], "severity": "MEDIUM"}'
                )
                async with httpx.AsyncClient(timeout=12.0) as client:
                    resp = await client.post(
                        "http://localhost:11434/api/chat",
                        json={
                            "model": "qwen2.5vl:7b",
                            "messages": [{
                                "role": "user",
                                "content": prompt,
                                "images": keyframe_b64s[:2]
                            }],
                            "format": "json",
                            "stream": False
                        }
                    )
                    if resp.status_code == 200:
                        import json
                        raw_content = resp.json().get("message", {}).get("content", "")
                        parsed = json.loads(raw_content)
                        parsed["reasoning_engine"] = "Qwen2.5-VL 7B Local (Ollama)"
                        return parsed
            except Exception as oe:
                logger.debug(f"Local Ollama VLM note: {oe}")

        # 3. Deterministic Cognitive Sequence Critic (Fast, accurate, offline-capable)
        return self._cognitive_sequence_critic(camera_id, domain, custom_goal, timeline, snapshots)

    def _cognitive_sequence_critic(
        self,
        camera_id: str,
        domain: str,
        custom_goal: Optional[str],
        timeline: List[Dict[str, Any]],
        snapshots: List[SequenceSnapshot]
    ) -> Dict[str, Any]:
        """
        Forensic rule-based sequence synthesizer that compares the observation sequence
        against domain operational criteria.
        """
        max_risk = max((s.max_risk for s in snapshots), default=0)
        has_fallen = any(any(t.get("is_fallen") for t in s.tracks) for s in snapshots)
        all_hazards = set()
        for s in snapshots:
            all_hazards.update(s.active_hazards)

        ppe_issues = [h for h in all_hazards if "NO_" in h]
        zone_breaches = [h for h in all_hazards if "ZONE" in h or "PERIMETER" in h]
        prox_issues = [h for h in all_hazards if "PROXIMITY" in h]
        motion_cessation = any(t["label"] == "Movement Cessation" for t in timeline)
        equipment_interactions = any(t["label"] == "Equipment Proximity" for t in timeline)

        # Reconstruct "What Happened"
        what_happened_parts = []
        if snapshots[0].worker_count > 0:
            what_happened_parts.append(f"During the monitored 60-second window on camera {camera_id}, personnel were continuously present in the workstation.")
        else:
            what_happened_parts.append(f"Surveillance on camera {camera_id} captured activity beginning after initial workstation vacancy.")

        if equipment_interactions:
            what_happened_parts.append("A worker approached the active machinery boundary and conducted physical tasks.")
        if motion_cessation:
            what_happened_parts.append("Equipment and worker movement subsequently paused mid-cycle.")
        if not equipment_interactions and not motion_cessation:
            what_happened_parts.append("Personnel maintained continuous movement across the monitored operational area.")

        what_happened = " ".join(what_happened_parts)

        # Reconstruct "What Went Wrong"
        wrong_points = []
        severity = "SAFE"
        if has_fallen:
            wrong_points.append("Worker collapse / fall posture detected with rapid loss of vertical stability.")
            severity = "CRITICAL"
        if zone_breaches:
            wrong_points.append(f"Unauthorized ground perimeter breach recorded ({', '.join(zone_breaches)}).")
            severity = "HIGH" if severity != "CRITICAL" else severity
        if ppe_issues:
            wrong_points.append(f"Procedural PPE violation observed: missing {', '.join([h.replace('NO_', '').lower() for h in ppe_issues])}.")
            severity = "HIGH" if severity == "SAFE" else severity
        if prox_issues:
            wrong_points.append("Worker operated within unverified safety clearance (< 1.5m to active moving parts).")
            severity = "MEDIUM" if severity == "SAFE" else severity
        if motion_cessation and domain == "EQUIPMENT_OPERATION":
            wrong_points.append("The equipment stopped prematurely following item interaction; subsequent restart attempts did not verify clearance.")
            severity = "MEDIUM" if severity == "SAFE" else severity

        if not wrong_points:
            what_went_wrong = "No critical procedural errors or safety violations observed during the 60-second sequence. Operational flow complied with baseline guidelines."
            severity = "SAFE"
        else:
            what_went_wrong = " ".join(wrong_points)

        # Possible Explanation
        if has_fallen:
            explanation = "Sudden biomechanical instability, slip/trip hazard on walking surface, or acute physical distress."
        elif zone_breaches and ppe_issues:
            explanation = "Intentional shortcut or complacency bypassing established safety boundaries while omitting required protective gear."
        elif equipment_interactions and motion_cessation:
            explanation = "A feeding obstruction, material jam, or safety interlock trip may have halted machinery. The video alone suggests an unverified restart attempt."
        elif ppe_issues:
            explanation = "PPE removal due to thermal discomfort, lack of enforcement, or rapid transition from non-hazardous zones."
        elif zone_breaches:
            explanation = "Worker reached for tools or components stored inside the danger perimeter without de-energizing the zone."
        else:
            explanation = "Normal operating rhythm observed across the 60-second sequence with standard procedural cadence."

        # Recommended Next Steps
        recommendations = []
        if has_fallen:
            recommendations.append("Dispatch immediate first-response medical personnel to the sector.")
            recommendations.append("Inspect walking-working surfaces for fluid spills, loose cables, or trip obstructions.")
        if ppe_issues:
            recommendations.append("Direct supervisor to issue immediate verbal PPE compliance notice.")
            recommendations.append("Verify mandatory safety glasses and hardhat availability at sector entryway.")
        if zone_breaches:
            recommendations.append("Re-calibrate optical demarcation and audible warning siren at danger boundary.")
            recommendations.append("Enforce Lockout/Tagout (LOTO) verification prior to any perimeter entry.")
        if equipment_interactions and motion_cessation:
            recommendations.append("Review machine fault codes and operating procedures before attempting further restarts.")
            recommendations.append("Inspect machine loading hopper for foreign material jams or misaligned guide rails.")
        if not recommendations:
            recommendations.append("Maintain routine visual surveillance and log baseline 60-second compliance check.")
            recommendations.append("No immediate corrective intervention required.")

        return {
            "what_happened": what_happened,
            "what_went_wrong": what_went_wrong,
            "possible_explanation": explanation,
            "recommended_next_steps": recommendations,
            "severity": severity,
            "reasoning_engine": "ONE EYE Cognitive Sequence Synthesizer"
        }

    def _generate_empty_report(self, camera_id: str, domain: str) -> Dict[str, Any]:
        return {
            "id": f"RETRO-{datetime.datetime.utcnow().strftime('%Y%m%d-%H%M%S')}",
            "camera_id": camera_id,
            "domain": domain,
            "custom_goal": None,
            "what_happened": "Camera buffer is initializing. Insufficient video frames recorded in the last 60 seconds.",
            "what_went_wrong": "Cannot evaluate sequence until camera pipeline has streamed for at least 5-10 seconds.",
            "possible_explanation": "Camera pipeline recently started or offline.",
            "recommended_next_steps": ["Ensure camera pipeline is in ONLINE state and allow buffer to populate."],
            "evidence_timeline": [],
            "keyframe_paths": [],
            "clip_path": None,
            "analysis_duration_sec": 60.0,
            "severity": "SAFE",
            "reasoning_engine": "System Buffer Initializer",
            "created_at": datetime.datetime.utcnow().isoformat()
        }


# Global Singleton Retrospective Engine
retrospective_engine = RetrospectiveEngine()
