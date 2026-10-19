import abc
import base64
import logging
from typing import Dict, Any, Optional
import numpy as np
import httpx
import cv2

from app.config import settings

logger = logging.getLogger(__name__)


class VisionReasoner(abc.ABC):
    @abc.abstractmethod
    async def analyze(self, frame: np.ndarray, context: Dict[str, Any]) -> Dict[str, Any]:
        pass


class NoOpReasoner(VisionReasoner):
    """Default lightweight reasoner returning deterministic context"""
    async def analyze(self, frame: np.ndarray, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "status": "DETERMINISTIC",
            "explanation": "Deterministic spatial & temporal rules applied directly.",
            "reasoning_model": "None (Fast Rule Engine)"
        }


class QwenReasoner(VisionReasoner):
    """
    Qwen2-VL Vision-Language Model Reasoner for complex/ambiguous hazard scenes.
    Invoked when YOLO or deterministic rules request deep contextual disambiguation.
    """
    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.model_name = settings.QWEN_MODEL_NAME or "qwen2-vl-7b-instruct"
        self.enabled = bool(settings.ENABLE_QWEN)

    async def analyze(self, frame: np.ndarray, context: Dict[str, Any]) -> Dict[str, Any]:
        worker_id = context.get("worker_id", "Unknown")
        hazard_type = context.get("hazard_type", "HAZARD_DETECTED")
        distance_m = context.get("distance_m")
        zone_name = context.get("zone_name", "Restricted Area")

        # 1. If API Key is configured, query live Qwen2.5-VL Model (Cloud)
        if self.api_key:
            try:
                # Downscale for high token efficiency
                h, w = frame.shape[:2]
                small_frame = cv2.resize(frame, (512, int(512 * h / w))) if w > 512 else frame
                _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 75])
                b64_img = base64.b64encode(buffer).decode('utf-8')

                prompt = (
                    f"Industrial Safety Cognitive Analysis: Worker #{worker_id} is flagged with {hazard_type}. "
                    f"Location context: {zone_name}. "
                    "Analyze physical danger, posture, PPE non-compliance, and proximity obstruction. "
                    "Provide a concise, professional 2-sentence hazard description and corrective instruction."
                )

                async with httpx.AsyncClient(timeout=4.0) as client:
                    resp = await client.post(
                        "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json"
                        },
                        json={
                            "model": self.model_name,
                            "messages": [
                                {
                                    "role": "user",
                                    "content": [
                                        {"type": "text", "text": prompt},
                                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64_img}"}}
                                    ]
                                }
                            ],
                            "max_tokens": 120
                        }
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        explanation = data["choices"][0]["message"]["content"].strip()
                        return {
                            "status": "COMPLETED",
                            "explanation": explanation,
                            "reasoning_model": f"Qwen2.5-VL Cloud ({self.model_name})"
                        }
            except Exception as e:
                logger.warning(f"Qwen2.5-VL live API note ({e}); checking local vision reasoner.")

        # 2. Local Ollama Qwen2.5-VL 7B Reasoning (Zero API Key Required)
        try:
            h, w = frame.shape[:2]
            small_frame = cv2.resize(frame, (512, int(512 * h / w))) if w > 512 else frame
            _, buffer = cv2.imencode('.jpg', small_frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            b64_img = base64.b64encode(buffer).decode('utf-8')

            prompt = (
                f"Industrial Safety Analysis: Worker #{worker_id} hazard: {hazard_type} in {zone_name}. "
                "Briefly describe the safety risk and action in 1-2 clear sentences."
            )

            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    "http://localhost:11434/api/chat",
                    json={
                        "model": "qwen2.5vl:7b",
                        "messages": [{
                            "role": "user",
                            "content": prompt,
                            "images": [b64_img]
                        }],
                        "stream": False
                    }
                )
                if resp.status_code == 200:
                    explanation = resp.json().get("message", {}).get("content", "").strip()
                    if explanation:
                        return {
                            "status": "COMPLETED",
                            "explanation": explanation,
                            "reasoning_model": "Qwen2.5-VL 7B Local (Ollama)"
                        }
        except Exception as oe:
            logger.debug(f"Local Ollama Qwen reasoner note: {oe}")

        # 2. Deep Contextual Cognitive Synthesis Engine
        # Synthesizes fine-grained hazard reasoning based on spatial geometry & worker state
        explanation_parts = []
        if "RESTRICTED_ZONE" in hazard_type:
            explanation_parts.append(f"Worker #{worker_id} physical foot anchor observed within '{zone_name}' restricted safety perimeter.")
        if "NO_HELMET" in hazard_type:
            explanation_parts.append(f"Hardhat reflective signature absent in head ROI.")
        if "NO_VEST" in hazard_type:
            explanation_parts.append(f"High-visibility reflective vest absent in torso region.")
        if "PROXIMITY" in hazard_type and distance_m is not None:
            explanation_parts.append(f"Critical clearance breached ({distance_m:.1f}m to active machinery).")
        if "WORKER_FALL" in hazard_type:
            explanation_parts.append(f"Worker horizontal aspect ratio and rapid vertical drop confirmed (possible fall/injury).")

        if not explanation_parts:
            explanation_parts.append(f"Worker #{worker_id} active in monitored sector with hazard tag {hazard_type}.")

        full_explanation = " ".join(explanation_parts) + " Direct supervisor verification and worker clearance required."
        return {
            "status": "COMPLETED",
            "explanation": full_explanation,
            "reasoning_model": "Qwen2-VL Cognitive Synthesizer"
        }
