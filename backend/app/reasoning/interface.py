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
    Qwen3-VL Vision-Language Model Reasoner for complex/ambiguous hazard scenes.
    Invoked only when deterministic rules request disambiguation.
    """
    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.model_name = settings.QWEN_MODEL_NAME
        self.enabled = bool(settings.ENABLE_QWEN and self.api_key)

    async def analyze(self, frame: np.ndarray, context: Dict[str, Any]) -> Dict[str, Any]:
        if not self.enabled or not self.api_key:
            return {
                "status": "DISABLED",
                "explanation": "Qwen3-VL reasoning disabled (QWEN_API_KEY not configured).",
                "reasoning_model": "None"
            }

        try:
            # Encode frame as JPEG base64
            _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            b64_img = base64.b64encode(buffer).decode('utf-8')
            
            prompt = (
                f"Analyze this industrial safety scene. Context: Worker #{context.get('worker_id')} "
                f"detected with possible hazard: {context.get('hazard_type')}. "
                "Assess if the worker is in immediate physical danger, if PPE is absent, "
                "or if there is an equipment obstruction. Respond concisely in 2 sentences."
            )

            # OpenAI/DashScope compatible call
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
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
                        "max_tokens": 150
                    }
                )
                if response.status_code == 200:
                    data = response.json()
                    analysis_text = data["choices"][0]["message"]["content"]
                    return {
                        "status": "COMPLETED",
                        "explanation": analysis_text,
                        "reasoning_model": self.model_name
                    }
                else:
                    logger.warning(f"Qwen API error: {response.status_code}")
                    return {"status": "ERROR", "explanation": f"API error: {response.status_code}"}
        except Exception as e:
            logger.error(f"Error calling Qwen reasoner: {e}")
            return {"status": "ERROR", "explanation": str(e)}
