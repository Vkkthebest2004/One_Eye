import logging
from typing import List, Dict, Any, Optional
import datetime

from app.alerts.channels import (
    AlertChannel,
    WebSocketChannel,
    ConsoleChannel,
    SarvamTTSChannel,
    WhatsAppChannel,
    MockRelayChannel
)
from app.websocket.manager import ws_manager
from app.db.database import AsyncSessionLocal
from app.db.models import AlertRecord

logger = logging.getLogger(__name__)


class AlertDispatcher:
    """
    Central Alert Dispatcher routing safety events to all configured channels
    without blocking real-time processing threads.
    """
    def __init__(self):
        self.channels: List[AlertChannel] = [
            WebSocketChannel(),
            ConsoleChannel(),
            SarvamTTSChannel(),
            WhatsAppChannel(),
            MockRelayChannel()
        ]

    async def dispatch_alert(self, event: Dict[str, Any]):
        event_id = event.get("event_id", "UNKNOWN")
        
        for channel in self.channels:
            if not channel.enabled:
                continue
            try:
                success = await channel.send(event)
                # Record alert dispatch in DB asynchronously
                if success and event_id != "UNKNOWN":
                    await self._record_alert_log(event_id, channel.name, "SENT")
            except Exception as e:
                logger.error(f"Error dispatching to {channel.name}: {e}")
                if event_id != "UNKNOWN":
                    await self._record_alert_log(event_id, channel.name, f"FAILED: {e}")

    async def _record_alert_log(self, event_id: str, channel: str, status: str):
        try:
            async with AsyncSessionLocal() as db:
                record = AlertRecord(
                    event_id=event_id,
                    channel=channel,
                    sent_at=datetime.datetime.utcnow(),
                    status=status
                )
                db.add(record)
                await db.commit()
        except Exception as e:
            logger.debug(f"Could not write alert record to DB: {e}")

    async def broadcast_event_update(self, **kwargs):
        """Broadcast state changes like ACKNOWLEDGED or RESOLVED"""
        await ws_manager.broadcast({
            "type": "EVENT_UPDATED",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            **kwargs
        })

    async def broadcast_detection_update(self, camera_id: str, detections: List[Dict], tracks: List[Dict], fps: float):
        """Broadcast real-time bounding boxes and track positions for Canvas overlay"""
        await ws_manager.broadcast({
            "type": "DETECTION_UPDATE",
            "camera_id": camera_id,
            "fps": round(fps, 1),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "detections": detections,
            "tracks": tracks
        })

    async def broadcast_detections(
        self,
        camera_id: str,
        detections: List[Dict],
        tracks: List[Dict],
        fps: float,
        latency_ms: float = 0.0,
        visual_zones: Optional[List[Dict]] = None
    ):
        """Alias for real-time computer vision frame telemetry with dynamic visual anchor zones"""
        payload = {
            "type": "DETECTION_UPDATE",
            "camera_id": camera_id,
            "fps": round(fps, 1),
            "latency_ms": round(latency_ms, 1),
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "detections": detections,
            "tracks": tracks
        }
        if visual_zones:
            payload["visual_zones"] = visual_zones
        await ws_manager.broadcast(payload)

    async def broadcast_camera_status(self, camera_id: str, status: str, fps: float):
        await ws_manager.broadcast({
            "type": "CAMERA_STATUS",
            "camera_id": camera_id,
            "status": status,
            "fps": round(fps, 1),
            "timestamp": datetime.datetime.utcnow().isoformat()
        })


dispatcher = AlertDispatcher()
