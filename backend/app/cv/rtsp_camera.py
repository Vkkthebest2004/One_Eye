import logging
import os
import shutil
import subprocess
import time
from typing import Optional, Tuple
import numpy as np

logger = logging.getLogger(__name__)


class RTSPCamera:
    """
    Industrial low-latency RTSP / HTTP Video Ingestion Engine.
    Uses FFmpeg rawvideo pipe for zero-buffer, low-latency BGR24 decoding.
    Fallback to OpenCV VideoCapture if FFmpeg stream pipe fails.
    """

    def __init__(self, rtsp_url: str, width: int = 1280, height: int = 720, target_fps: int = 30):
        self.rtsp_url = rtsp_url
        self.width = width
        self.height = height
        self.fps = float(target_fps)
        self.frame_size = self.width * self.height * 3
        self.process: Optional[subprocess.Popen] = None
        self.is_running = False
        self._last_frame_time = 0.0
        self._ffmpeg_bin = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"

    def start(self) -> bool:
        """Spawn low-latency FFmpeg process reading RTSP / HTTP stream."""
        if self.is_running and self.process and self.process.poll() is None:
            return True

        self.stop()

        if not os.path.exists(self._ffmpeg_bin):
            logger.warning(f"FFmpeg binary not found at '{self._ffmpeg_bin}'.")
            return False

        command = [
            self._ffmpeg_bin,
            "-rtsp_transport", "tcp",
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-strict", "experimental",
            "-i", self.rtsp_url,
            "-an",
            "-sn",
            "-vf", f"scale={self.width}:{self.height}",
            "-pix_fmt", "bgr24",
            "-f", "rawvideo",
            "-v", "error",
            "-"
        ]

        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                bufsize=10**7
            )
            self.is_running = True
            self._last_frame_time = time.time()
            logger.info(f"RTSPCamera started FFmpeg pipe for: {self.rtsp_url} ({self.width}x{self.height})")
            return True
        except Exception as e:
            logger.error(f"Failed to start RTSPCamera FFmpeg process: {e}")
            self.stop()
            return False

    def read(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Read the latest unbuffered BGR frame from FFmpeg stdout pipe.
        Returns: (success, frame_ndarray, timestamp)
        """
        if not self.is_running or self.process is None:
            return False, None, time.time()

        if self.process.poll() is not None:
            logger.warning(f"RTSPCamera FFmpeg process died for {self.rtsp_url}. Reconnecting...")
            self.stop()
            self.start()
            return False, None, time.time()

        try:
            raw = self.process.stdout.read(self.frame_size)
            now = time.time()
            if len(raw) != self.frame_size:
                return False, None, now

            frame = np.frombuffer(raw, dtype=np.uint8).reshape((self.height, self.width, 3))
            self._last_frame_time = now
            return True, frame, now
        except Exception as e:
            logger.warning(f"Error reading frame from RTSPCamera: {e}")
            return False, None, time.time()

    def is_alive(self) -> bool:
        return self.is_running and self.process is not None and (self.process.poll() is None)

    def stop(self):
        self.is_running = False
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=1.5)
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None
