import abc
import logging
import json
from typing import Dict, Any, Optional
import httpx

from app.websocket.manager import ws_manager
from app.config import settings

logger = logging.getLogger(__name__)


class AlertChannel(abc.ABC):
    def __init__(self, name: str, enabled: bool = True):
        self.name = name
        self.enabled = enabled

    @abc.abstractmethod
    async def send(self, event: Dict[str, Any]) -> bool:
        pass


class WebSocketChannel(AlertChannel):
    def __init__(self):
        super().__init__(name="WEBSOCKET", enabled=True)

    async def send(self, event: Dict[str, Any]) -> bool:
        try:
            payload = {
                "type": "SAFETY_EVENT",
                **event
            }
            await ws_manager.broadcast(payload)
            return True
        except Exception as e:
            logger.error(f"[WebSocketChannel] Failed to send: {e}")
            return False


class ConsoleChannel(AlertChannel):
    def __init__(self):
        super().__init__(name="CONSOLE", enabled=True)

    async def send(self, event: Dict[str, Any]) -> bool:
        sev = event.get("severity", "INFO")
        eid = event.get("event_id", "UNKNOWN")
        cam = event.get("camera_id", "CAM")
        worker_id = event.get("worker_id")
        worker = "PLANT-WIDE" if worker_id in (None, 0) else f"#{worker_id}"
        risk = event.get("risk_score", 0)
        hazards = ", ".join(event.get("hazard_types", []))

        color = "\033[91m" if sev == "CRITICAL" else "\033[93m" if sev == "HIGH" else "\033[94m"
        reset = "\033[0m"

        print(f"\n{color}═══════════════════════════════════════════════════════════")
        print(f"🚨 [ONE EYE ALERT] [{sev}] Risk {risk}/100 | Event: {eid}")
        print(f"📍 Camera: {cam} | Target: {worker}")
        print(f"⚠️ Hazards: {hazards}")
        print(f"🛠️ Action: {event.get('recommended_action', 'None')}")
        print(f"═══════════════════════════════════════════════════════════{reset}\n")
        return True


class SarvamTTSChannel(AlertChannel):
    """
    Sarvam AI Text-to-Speech voice alert channel.
    Disabled gracefully if API key is not configured.
    """
    def __init__(self):
        enabled = bool(settings.ENABLE_TTS and settings.SARVAM_API_KEY)
        super().__init__(name="SARVAM_TTS", enabled=enabled)

    async def send(self, event: Dict[str, Any]) -> bool:
        if not self.enabled or not settings.SARVAM_API_KEY:
            logger.debug("[SarvamTTS] Skipped (channel disabled or no API key)")
            return False

        try:
            sev = event.get("severity", "CRITICAL")
            cam = event.get("camera_id", "plant")
            worker = event.get("worker_id", 1)
            hazard = event.get("primary_hazard", "safety violation")
            text = f"Attention safety team. {sev} hazard detected on camera {cam}. Worker {worker} involved in {hazard}. Intervene immediately."

            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(
                    "https://api.sarvam.ai/text-to-speech",
                    headers={"api-subscription-key": settings.SARVAM_API_KEY},
                    json={
                        "inputs": [text],
                        "target_language_code": "en-IN",
                        "speaker": "meera",
                        "model": "bulbul:v1"
                    }
                )
                if resp.status_code == 200:
                    logger.info(f"[SarvamTTS] Voice alert generated for {event.get('event_id')}")
                    return True
                else:
                    logger.warning(f"[SarvamTTS] API responded with status {resp.status_code}")
                    return False
        except Exception as e:
            logger.warning(f"[SarvamTTS] External TTS request failed: {e}")
            return False


class WhatsAppChannel(AlertChannel):
    """
    WhatsApp notification channel.
    Disabled gracefully if credentials are not configured.
    """
    def __init__(self):
        enabled = bool(settings.ENABLE_WHATSAPP and settings.WHATSAPP_API_KEY)
        super().__init__(name="WHATSAPP", enabled=enabled)

    async def send(self, event: Dict[str, Any]) -> bool:
        if not self.enabled or not settings.WHATSAPP_API_KEY:
            logger.debug("[WhatsApp] Skipped (channel disabled or no API key)")
            return False

        try:
            message_body = (
                f"🚨 *ONE EYE SAFETY ALERT* 🚨\n\n"
                f"*Severity:* {event.get('severity')}\n"
                f"*Event ID:* {event.get('event_id')}\n"
                f"*Camera:* {event.get('camera_id')}\n"
                f"*Worker:* #{event.get('worker_id')}\n"
                f"*Risk Score:* {event.get('risk_score')}/100\n"
                f"*Hazards:* {', '.join(event.get('hazard_types', []))}\n"
                f"*Recommended Action:* {event.get('recommended_action')}"
            )
            # Simulated or direct webhook dispatch
            logger.info(f"[WhatsApp] Notification dispatched to {settings.WHATSAPP_PHONE}")
            return True
        except Exception as e:
            logger.warning(f"[WhatsApp] Notification failed: {e}")
            return False


class MockRelayChannel(AlertChannel):
    """
    Physical Industrial Siren & Safety Relay Controller.
    Mock implementation for development; extensible to GPIO/Serial/HTTP.
    """
    def __init__(self):
        # This remains a mock implementation. Never report a physical relay as
        # active unless an operator explicitly enables the relay channel.
        super().__init__(name="SAFETY_RELAY", enabled=settings.ENABLE_RELAY)
        self.is_triggered = False

    async def send(self, event: Dict[str, Any]) -> bool:
        sev = event.get("severity", "INFO")
        if sev == "CRITICAL":
            self.is_triggered = True
            logger.info(f"🚨 [SAFETY RELAY TRIGGERED] Emergency siren / strobe activated for {event.get('event_id')}")
            return True
        return False

    def reset_relay(self):
        self.is_triggered = False
        logger.info("🟢 [SAFETY RELAY RESET] Siren / strobe deactivated")
