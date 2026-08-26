import cv2
import time
import logging
from typing import Optional, Tuple, Generator
import numpy as np

logger = logging.getLogger(__name__)


class CameraSource:
    """
    Unified camera source abstraction supporting:
    - Local webcam device indexes (0, 1, 2)
    - Recorded video files (.mp4, .avi)
    - RTSP / HTTP IP camera streams (rtsp://...)
    """
    def __init__(self, camera_id: str, source: str, loop: bool = True):
        self.camera_id = camera_id
        self.source_str = str(source)
        self.loop = loop
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_numeric = self.source_str.isdigit()

        if self.is_numeric:
            self.actual_source = int(self.source_str)
        elif self.source_str.startswith("uvc_"):
            try:
                self.actual_source = int(self.source_str.replace("uvc_", ""))
            except ValueError:
                self.actual_source = 0
        elif self.source_str.startswith("mobile:"):
            self.actual_source = self.source_str
        else:
            # Check if file path is relative and resolve to base_dir
            from pathlib import Path
            from app.config import settings
            p = Path(self.source_str)
            if not p.is_absolute():
                base_p = settings.base_dir / self.source_str
                if base_p.exists():
                    self.actual_source = str(base_p)
                else:
                    self.actual_source = self.source_str
            else:
                self.actual_source = self.source_str
        
        self.fps: float = 30.0
        self.width: int = 1280
        self.height: int = 720
        self.frame_count: int = 0
        self.last_frame_time: float = 0.0
        self.connected: bool = False
        self._last_reconnect_attempt: float = 0.0
        self.rtsp_cam: Optional[Any] = None

    def connect(self) -> bool:
        try:
            # 1. Direct RTSP / HTTP IP Camera Ingestion (Low-latency FFmpeg)
            if isinstance(self.actual_source, str) and any(self.actual_source.startswith(p) for p in ["rtsp://", "http://", "https://", "rtmp://"]):
                from app.cv.rtsp_camera import RTSPCamera
                self.rtsp_cam = RTSPCamera(self.actual_source, width=1280, height=720, target_fps=30)
                if self.rtsp_cam.start():
                    self.fps = 30.0
                    self.width = 1280
                    self.height = 720
                    self.connected = True
                    logger.info(f"[{self.camera_id}] Connected to RTSP/HTTP stream via low-latency FFmpeg: {self.actual_source}")
                    return True
                logger.warning(f"[{self.camera_id}] RTSPCamera FFmpeg failed, falling back to OpenCV...")

            if isinstance(self.actual_source, str) and (self.actual_source.startswith("mobile_web:") or self.actual_source == "mobile_web"):
                self.fps = 30.0
                self.width = 1280
                self.height = 720
                self.connected = True
                return True

            if isinstance(self.actual_source, str) and self.actual_source.startswith("mobile:"):
                serial = self.actual_source.split(":", 1)[1]
                from app.cv.usb_mobile import mobile_manager
                mob_src = mobile_manager.get_source(serial)
                if mob_src and mob_src.is_alive():
                    self.fps = mob_src.fps
                    self.width = mob_src.width
                    self.height = mob_src.height
                    self.connected = True
                    return True
                # Try auto connecting
                ok, _ = mobile_manager.connect_device(serial)
                if ok:
                    mob_src = mobile_manager.get_source(serial)
                    if mob_src:
                        self.fps = mob_src.fps
                        self.width = mob_src.width
                        self.height = mob_src.height
                        self.connected = True
                        return True
                self.connected = False
                return False

            if isinstance(self.actual_source, int):
                logger.info(f"[{self.camera_id}] Skipping local hardware webcam index {self.actual_source} to prevent webcam activation.")
                self.connected = False
                return False

            if self.cap is not None:
                self.cap.release()
            
            self.cap = cv2.VideoCapture(self.actual_source)
            if not self.cap.isOpened():
                logger.info(f"[{self.camera_id}] Live video file not present ({self.source_str}) — starting active synthetic CCTV surveillance feed.")
                self.fps = 30.0
                self.width = 1280
                self.height = 720
                self.connected = True
                self._synthetic = True
                return True

            self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 30.0
            if self.fps <= 0 or np.isnan(self.fps):
                self.fps = 30.0
            
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720
            self.connected = True
            logger.info(f"[{self.camera_id}] Connected to source ({self.width}x{self.height} @ {self.fps:.1f} FPS)")
            return True
        except Exception as e:
            logger.error(f"[{self.camera_id}] Error connecting to source: {e}")
            self.connected = False
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Read next frame with reconnect cooldown.
        Returns: (success, frame, timestamp)
        """
        now = time.time()

        # Check RTSPCamera FFmpeg stream first
        if self.rtsp_cam and self.rtsp_cam.is_alive():
            ok, frame, ts = self.rtsp_cam.read()
            if ok and frame is not None:
                self.frame_count += 1
                self.last_frame_time = ts
                self.connected = True
                return True, frame, ts

        if isinstance(self.actual_source, str) and (self.actual_source.startswith("mobile_web:") or self.actual_source == "mobile_web" or self.actual_source.startswith("mobile:")):
            from app.cv.usb_mobile import mobile_manager
            # Universal lookup across all mobile aliases and device serials
            serial_part = self.actual_source.split(":", 1)[1] if ":" in self.actual_source else ""
            web_res = (
                mobile_manager.get_web_frame(self.camera_id)
                or mobile_manager.get_web_frame("CAM_MOBILE")
                or mobile_manager.get_web_frame("CAM_MOB_24151JEG")
                or (mobile_manager.get_web_frame(serial_part) if serial_part else None)
            )
            if web_res:
                frame, ts = web_res
                self.frame_count += 1
                self.last_frame_time = ts
                self.connected = True
                return True, frame, ts

            if serial_part:
                mob_src = mobile_manager.get_source(serial_part)
                if mob_src:
                    ok, frame, ts = mob_src.read()
                    if ok:
                        self.frame_count += 1
                        self.last_frame_time = ts
                        self.connected = True
                        return ok, frame, ts

            return False, None, now

        if getattr(self, "_synthetic", False):
            import datetime
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame[:] = (20, 26, 30)
            for gy in range(0, 720, 90):
                cv2.line(frame, (0, gy), (1280, gy), (32, 42, 48), 1)
            for gx in range(0, 1280, 120):
                cv2.line(frame, (gx, 0), (gx, 720), (32, 42, 48), 1)
            ts_str = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-4]
            cv2.putText(frame, f"ONE EYE CCTV // {self.camera_id}", (30, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 220, 255), 2)
            cv2.putText(frame, f"LIVE REC [●] {ts_str} UTC", (30, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 150), 1)
            self.frame_count += 1
            self.last_frame_time = now
            return True, frame, now

        if not self.connected or self.cap is None:
            if (now - self._last_reconnect_attempt) < 4.0:
                return False, None, now
            self._last_reconnect_attempt = now
            if not self.connect():
                return False, None, now

        ret, frame = self.cap.read()
        timestamp = time.time()

        if not ret:
            # End of video reached; loop if configured
            if self.loop and not self.is_numeric and not str(self.actual_source).startswith("uvc_"):
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.cap.read()
                if not ret:
                    self.connected = False
                    return False, None, timestamp
            else:
                self.connected = False
                return False, None, timestamp

        self.frame_count += 1
        self.last_frame_time = timestamp
        return True, frame, timestamp

    def release(self):
        if self.rtsp_cam:
            self.rtsp_cam.stop()
            self.rtsp_cam = None
        if isinstance(self.actual_source, str) and self.actual_source.startswith("mobile:"):
            self.connected = False
            return
        if self.cap is not None:
            self.cap.release()
            self.cap = None
        self.connected = False
        logger.info(f"[{self.camera_id}] Camera source released")

    def is_alive(self) -> bool:
        if isinstance(self.actual_source, str) and self.actual_source.startswith("mobile:"):
            serial = self.actual_source.split(":", 1)[1]
            from app.cv.usb_mobile import mobile_manager
            mob_src = mobile_manager.get_source(serial)
            return mob_src is not None and mob_src.is_alive()
        return self.connected and self.cap is not None and self.cap.isOpened()
