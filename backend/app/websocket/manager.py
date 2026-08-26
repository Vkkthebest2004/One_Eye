import json
import logging
from typing import List, Dict, Any, Set
from fastapi import WebSocket
import numpy as np

logger = logging.getLogger(__name__)


class NumpySafeJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.bool_):
            return bool(obj)
        if isinstance(obj, (np.integer, np.int64, np.int32, np.int16, np.int8)):
            return int(obj)
        if isinstance(obj, (np.floating, np.float64, np.float32, np.float16)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        return super().default(obj)


class ConnectionManager:
    """
    WebSocket Connection Manager broadcasting real-time safety events,
    frame detection bounding boxes, camera status changes, and metrics.
    """
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"WebSocket client connected. Total clients: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.discard(websocket)
        logger.info(f"WebSocket client disconnected. Total clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]):
        if not self.active_connections:
            return

        dead_connections = []
        try:
            msg_text = json.dumps(message, cls=NumpySafeJSONEncoder)
        except Exception:
            msg_text = json.dumps(message, default=str)
        
        for connection in list(self.active_connections):
            try:
                await connection.send_text(msg_text)
            except Exception as e:
                logger.warning(f"Error broadcasting to WebSocket client: {e}")
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)


ws_manager = ConnectionManager()
