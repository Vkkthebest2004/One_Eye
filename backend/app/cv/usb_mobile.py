"""
ONE EYE — USB Mobile Phone Camera Connection Module

Supports three connection modes for using a mobile phone camera as a safety feed:

1. UVC_WEBCAM:   Android 14+ / iOS 18+ USB Webcam mode.
   The phone registers as a standard USB video device.
   OpenCV captures it like device index 0/1/2.

2. ADB_SCRCPY:   Android phones with USB debugging enabled.
   Uses `adb` to detect the device, then launches `scrcpy`
   in v4l2 sink mode (Linux) or window-capture mode (macOS)
   to stream the phone's camera.

3. ADB_IPWEBCAM: Android with the "IP Webcam" app installed.
   Uses `adb forward` to tunnel the MJPEG stream from the
   phone's camera app over USB (no Wi-Fi needed).
   OpenCV reads the forwarded http://127.0.0.1:<port>/video stream.
"""

import asyncio
import logging
import os
import platform
import re
import shutil
import subprocess
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

class ConnectionMode(str, Enum):
    """How the phone's camera is being streamed to the host."""
    UVC_WEBCAM = "uvc_webcam"        # Phone acts as a USB webcam device
    ADB_SCRCPY = "adb_scrcpy"        # ADB + scrcpy camera mirror
    ADB_IPWEBCAM = "adb_ipwebcam"    # ADB port-forward + IP Webcam app
    AUTO = "auto"                    # Let the module decide


class DeviceOS(str, Enum):
    ANDROID = "android"
    IOS = "ios"
    UNKNOWN = "unknown"


@dataclass
class USBDevice:
    """Represents a single USB-connected mobile phone."""
    serial: str                     # ADB serial or system USB id
    model: str = "Unknown Device"
    manufacturer: str = ""
    os: DeviceOS = DeviceOS.UNKNOWN
    os_version: str = ""
    connection_mode: ConnectionMode = ConnectionMode.AUTO
    is_connected: bool = False
    video_device_index: Optional[int] = None   # /dev/videoN or macOS index
    forwarded_port: Optional[int] = None        # For ADB port-forward
    scrcpy_process: Optional[subprocess.Popen] = None
    last_heartbeat: float = 0.0
    error_message: str = ""


@dataclass
class MobileConnectionStatus:
    """Aggregate status of all mobile phone connections."""
    adb_available: bool = False
    scrcpy_available: bool = False
    devices: List[USBDevice] = field(default_factory=list)
    platform: str = ""


# ---------------------------------------------------------------------------
# ADB Helper Layer
# ---------------------------------------------------------------------------

class ADBHelper:
    """
    Low-level wrapper around the `adb` command-line tool.
    Detects devices, queries properties, and manages port forwarding.
    """

    def __init__(self, adb_path: Optional[str] = None):
        candidate_paths = [
            adb_path,
            shutil.which("adb"),
            "/opt/homebrew/bin/adb",
            "/usr/local/bin/adb",
            os.path.expanduser("~/Library/Android/sdk/platform-tools/adb"),
            "adb",
        ]
        self.adb_path = next((p for p in candidate_paths if p and (shutil.which(p) or os.path.exists(p))), "adb")
        self._available: Optional[bool] = None

    @property
    def available(self) -> bool:
        if self._available is None:
            self._available = self._check_adb()
        return self._available

    def _check_adb(self) -> bool:
        try:
            result = subprocess.run(
                [self.adb_path, "version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                logger.info(f"ADB found: {result.stdout.strip().splitlines()[0]}")
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        logger.warning("ADB not found. Android USB connections will be limited to UVC webcam mode.")
        return False

    def list_devices(self) -> List[Dict[str, str]]:
        """Return list of connected ADB devices with serial and state."""
        if not self.available:
            return []
        try:
            result = subprocess.run(
                [self.adb_path, "devices", "-l"],
                capture_output=True, text=True, timeout=10
            )
            devices = []
            for line in result.stdout.strip().splitlines()[1:]:
                line = line.strip()
                if not line or "offline" in line:
                    continue
                parts = line.split()
                if len(parts) >= 2 and parts[1] == "device":
                    info = {"serial": parts[0]}
                    # Parse additional key:value pairs
                    for part in parts[2:]:
                        if ":" in part:
                            k, v = part.split(":", 1)
                            info[k] = v
                    devices.append(info)
            return devices
        except Exception as e:
            logger.error(f"ADB list_devices error: {e}")
            return []

    def get_device_prop(self, serial: str, prop: str) -> str:
        """Query a single Android system property via `adb shell getprop`."""
        if not self.available:
            return ""
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "shell", "getprop", prop],
                capture_output=True, text=True, timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return ""

    def get_device_info(self, serial: str) -> Dict[str, str]:
        """Collect model, manufacturer, and Android version."""
        return {
            "model": self.get_device_prop(serial, "ro.product.model"),
            "manufacturer": self.get_device_prop(serial, "ro.product.manufacturer"),
            "os_version": self.get_device_prop(serial, "ro.build.version.release"),
            "sdk_version": self.get_device_prop(serial, "ro.build.version.sdk"),
        }

    def forward_port(self, serial: str, local_port: int, remote_port: int) -> bool:
        """Set up ADB TCP port forwarding: localhost:local -> phone:remote."""
        if not self.available:
            return False
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "forward",
                 f"tcp:{local_port}", f"tcp:{remote_port}"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info(f"ADB forward {local_port} -> {remote_port} on {serial}")
                return True
            logger.error(f"ADB forward failed: {result.stderr}")
            return False
        except Exception as e:
            logger.error(f"ADB forward error: {e}")
            return False

    def remove_forward(self, serial: str, local_port: int) -> bool:
        """Remove a specific port-forward rule."""
        if not self.available:
            return False
        try:
            subprocess.run(
                [self.adb_path, "-s", serial, "forward", "--remove",
                 f"tcp:{local_port}"],
                capture_output=True, text=True, timeout=5
            )
            return True
        except Exception:
            return False

    def check_app_running(self, serial: str, package: str) -> bool:
        """Check if a specific app package is running on the phone."""
        if not self.available:
            return False
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "shell",
                 "pidof", package],
                capture_output=True, text=True, timeout=5
            )
            return bool(result.stdout.strip())
        except Exception:
            return False

    def launch_app(self, serial: str, intent: str) -> bool:
        """Launch an Android app by intent."""
        if not self.available:
            return False
        try:
            result = subprocess.run(
                [self.adb_path, "-s", serial, "shell",
                 "am", "start", "-n", intent],
                capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def launch_camera(self, serial: Optional[str] = None) -> bool:
        """Wake up phone screen and automatically launch the native camera / video capture."""
        if not self.available:
            return False
        target_serial = serial or (self.list_devices()[0]["serial"] if self.list_devices() else None)
        if not target_serial:
            return False
        try:
            # 1. Wake screen and unlock if possible
            subprocess.run([self.adb_path, "-s", target_serial, "shell", "input keyevent 224"], timeout=5)
            subprocess.run([self.adb_path, "-s", target_serial, "shell", "input keyevent 82"], timeout=5)
            # 2. Launch Camera intent
            cmd = (
                "am start -a android.media.action.VIDEO_CAPTURE || "
                "am start -a android.media.action.IMAGE_CAPTURE || "
                "am start -a android.media.action.STILL_IMAGE_CAMERA || "
                "monkey -p com.android.camera -c android.intent.category.LAUNCHER 1 || "
                "monkey -p com.google.android.GoogleCamera -c android.intent.category.LAUNCHER 1"
            )
            result = subprocess.run([self.adb_path, "-s", target_serial, "shell", cmd], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to launch camera via ADB: {e}")
            return False

    def reverse_port(self, serial: str, remote_port: int, local_port: int) -> bool:
        """Set up ADB reverse port forwarding: phone:remote -> localhost:local (enables HTTPS-grade localhost permissions on phone)."""
        if not self.available:
            return False
        try:
            subprocess.run(
                [self.adb_path, "-s", serial, "reverse", f"tcp:{remote_port}", f"tcp:{local_port}"],
                capture_output=True, text=True, timeout=5
            )
            return True
        except Exception:
            return False

    def open_url(self, url: str, serial: Optional[str] = None) -> bool:
        """Automatically reverse ports for secure camera permissions and open the URL on the phone."""
        if not self.available:
            return False
        target_serial = serial or (self.list_devices()[0]["serial"] if self.list_devices() else None)
        if not target_serial:
            return False
        try:
            # Reverse ports 3001 and 8001 so phone accesses localhost securely
            self.reverse_port(target_serial, 3001, 3001)
            self.reverse_port(target_serial, 8001, 8001)

            # Wake screen
            subprocess.run([self.adb_path, "-s", target_serial, "shell", "input keyevent 224"], timeout=5)
            # Use localhost on the device so Chrome grants camera permissions without HTTPS requirements
            target_url = "http://localhost:3001/mobile-cam"
            cmd = f'am start -a android.intent.action.VIEW -d "{target_url}"'
            result = subprocess.run([self.adb_path, "-s", target_serial, "shell", cmd], capture_output=True, text=True, timeout=10)
            return result.returncode == 0
        except Exception as e:
            logger.error(f"Failed to open URL via ADB: {e}")
            return False


# ---------------------------------------------------------------------------
# UVC Device Scanner (cross-platform, zero OpenCV hardware probing)
# ---------------------------------------------------------------------------

class UVCScanner:
    """
    Detects video capture devices purely via passive OS metadata (system_profiler on macOS,
    sysfs on Linux) without EVER calling cv2.VideoCapture() in probing loops.
    This guarantees zero camera indicator flashing or hardware cycling.
    """
    _cached_devices: List[Dict[str, any]] = []
    _last_scan_time: float = 0.0

    @staticmethod
    def find_video_devices(force_refresh: bool = False) -> List[Dict[str, any]]:
        now = time.time()
        if not force_refresh and UVCScanner._cached_devices and (now - UVCScanner._last_scan_time < 60.0):
            return UVCScanner._cached_devices

        system = platform.system()
        devices = []

        if system == "Linux":
            for path in sorted(Path("/dev").glob("video*")):
                try:
                    idx = int(re.search(r"\d+", path.name).group())
                    name = UVCScanner._get_linux_device_name(path)
                    devices.append({
                        "index": idx,
                        "path": str(path),
                        "name": name,
                        "is_phone": UVCScanner._looks_like_phone(name),
                    })
                except Exception:
                    pass
        elif system == "Darwin":
            # macOS: Query system_profiler passively (zero camera hardware access)
            try:
                out = subprocess.run(
                    ["system_profiler", "SPCameraDataType"],
                    capture_output=True, text=True, timeout=3
                ).stdout
                
                # Parse camera entries from system_profiler output
                lines = [line.strip() for line in out.splitlines() if line.strip()]
                cam_names = []
                for line in lines:
                    if line.endswith(":") and not line.startswith("Camera:") and not line.startswith("Model ID:") and not line.startswith("Unique ID:"):
                        cam_name = line.rstrip(":")
                        if cam_name not in cam_names:
                            cam_names.append(cam_name)

                if not cam_names:
                    cam_names = ["FaceTime HD Camera"]

                for idx, name in enumerate(cam_names):
                    devices.append({
                        "index": idx,
                        "path": f"device:{idx}",
                        "name": name,
                        "is_phone": UVCScanner._looks_like_phone(name),
                    })
            except Exception:
                devices = [{"index": 0, "path": "device:0", "name": "Default Camera", "is_phone": False}]
        else:
            devices = [{"index": 0, "path": "device:0", "name": "Default Camera", "is_phone": False}]

        UVCScanner._cached_devices = devices
        UVCScanner._last_scan_time = now
        return devices

    @staticmethod
    def _get_linux_device_name(dev_path: Path) -> str:
        try:
            name_file = Path(f"/sys/class/video4linux/{dev_path.name}/name")
            if name_file.exists():
                return name_file.read_text().strip()
        except Exception:
            pass
        return dev_path.name

    @staticmethod
    def _looks_like_phone(name: str) -> bool:
        phone_keywords = [
            "android", "pixel", "samsung", "oneplus", "xiaomi",
            "redmi", "realme", "oppo", "vivo", "motorola",
            "iphone", "ipad", "continuity",
        ]
        lower = name.lower()
        return any(kw in lower for kw in phone_keywords)


# ---------------------------------------------------------------------------
# Mobile Camera Source (extends CameraSource pattern)
# ---------------------------------------------------------------------------

class MobileCameraSource:
    """
    A camera source backed by a USB-connected mobile phone.

    This wraps the connection negotiation and frame capture.
    Once connected, it exposes the same read() interface as CameraSource.
    """

    def __init__(
        self,
        device: USBDevice,
        mode: ConnectionMode = ConnectionMode.AUTO,
        adb: Optional[ADBHelper] = None,
        ipwebcam_port: int = 8080,
        forward_local_port: int = 4747,
    ):
        self.device = device
        self.mode = mode
        self.adb = adb or ADBHelper()
        self.ipwebcam_port = ipwebcam_port
        self.forward_local_port = forward_local_port

        self.cap: Optional[cv2.VideoCapture] = None
        self.connected: bool = False
        self.fps: float = 30.0
        self.width: int = 1280
        self.height: int = 720
        self.frame_count: int = 0
        self.last_frame_time: float = 0.0

    def connect(self) -> bool:
        """Attempt to connect using the configured mode, with AUTO fallback chain."""
        if self.mode == ConnectionMode.AUTO:
            # Try modes in priority order
            for try_mode in [ConnectionMode.UVC_WEBCAM,
                             ConnectionMode.ADB_IPWEBCAM,
                             ConnectionMode.ADB_SCRCPY]:
                if self._connect_mode(try_mode):
                    self.device.connection_mode = try_mode
                    return True
            return False
        else:
            return self._connect_mode(self.mode)

    def _connect_mode(self, mode: ConnectionMode) -> bool:
        """Connect using a specific mode."""
        try:
            if mode == ConnectionMode.UVC_WEBCAM:
                return self._connect_uvc()
            elif mode == ConnectionMode.ADB_IPWEBCAM:
                return self._connect_ipwebcam()
            elif mode == ConnectionMode.ADB_SCRCPY:
                return self._connect_scrcpy()
        except Exception as e:
            logger.error(f"[{self.device.serial}] {mode.value} connection failed: {e}")
            self.device.error_message = str(e)
        return False

    # --- UVC Webcam Mode ---

    def _connect_uvc(self) -> bool:
        """
        Connect to the phone as a standard USB webcam device.
        Requires the phone to be in UVC/Webcam mode (Android 14+ Developer Options
        or iPhone via Continuity Camera on macOS).
        """
        idx = self.device.video_device_index
        if idx is None:
            # Scan for a phone-like UVC device
            uvc_devices = UVCScanner.find_video_devices()
            phone_devs = [d for d in uvc_devices if d.get("is_phone")]
            if phone_devs:
                idx = phone_devs[0]["index"]
            else:
                # On macOS / Linux, device index 0 is the built-in FaceTime HD laptop webcam.
                # Only allow external USB video devices (index > 0). NEVER open index 0 for mobile!
                external_devs = [d for d in uvc_devices if d["index"] > 0]
                if external_devs:
                    idx = external_devs[-1]["index"]
                else:
                    logger.debug(f"[{self.device.serial}] No external UVC mobile devices found (skipping laptop webcam).")
                    return False

        if idx is None or idx == 0:
            logger.debug(f"[{self.device.serial}] Refusing to open device index 0 (laptop webcam) for mobile connection.")
            return False

        # Open video capture
        cap = cv2.VideoCapture(idx)
        if not cap.isOpened():
            logger.debug(f"[{self.device.serial}] UVC device {idx} could not be opened.")
            return False

        self.cap = cap
        self.device.video_device_index = idx
        self._read_cap_props()
        self.connected = True
        logger.info(
            f"[{self.device.serial}] Connected via UVC Webcam "
            f"(device {idx}, {self.width}x{self.height} @ {self.fps:.0f}fps)"
        )
        return True

    # --- ADB + IP Webcam Mode ---

    def _connect_ipwebcam(self) -> bool:
        """
        Connect via ADB port-forward to the IP Webcam app's MJPEG stream.
        The phone must have "IP Webcam" installed and the server started.
        """
        if not self.adb.available:
            return False

        # Set up ADB port forwarding
        ok = self.adb.forward_port(
            self.device.serial,
            self.forward_local_port,
            self.ipwebcam_port
        )
        if not ok:
            return False
        self.device.forwarded_port = self.forward_local_port

        # Open the MJPEG stream via forwarded localhost port
        stream_url = f"http://127.0.0.1:{self.forward_local_port}/video"
        cap = cv2.VideoCapture(stream_url)

        # Give the stream a moment to establish
        time.sleep(1.0)
        if not cap.isOpened():
            logger.debug(
                f"[{self.device.serial}] IP Webcam stream not reachable at {stream_url}. "
                f"Ensure the IP Webcam app is running on the phone."
            )
            self.adb.remove_forward(self.device.serial, self.forward_local_port)
            return False

        self.cap = cap
        self._read_cap_props()
        self.connected = True
        logger.info(
            f"[{self.device.serial}] Connected via ADB + IP Webcam "
            f"({stream_url}, {self.width}x{self.height})"
        )
        return True

    # --- ADB + scrcpy Mode ---

    def _connect_scrcpy(self) -> bool:
        """
        Use scrcpy to mirror the phone's camera display.
        On Linux, scrcpy can output to a v4l2 loopback device.
        On macOS, we capture scrcpy's window or use its built-in
        camera mirror feature (scrcpy >= 2.4).
        """
        scrcpy_path = (
            shutil.which("scrcpy")
            or ("/opt/homebrew/bin/scrcpy" if os.path.exists("/opt/homebrew/bin/scrcpy") else None)
            or ("/usr/local/bin/scrcpy" if os.path.exists("/usr/local/bin/scrcpy") else None)
        )
        if not scrcpy_path:
            logger.debug("scrcpy not found in PATH.")
            return False

        if not self.adb.available:
            return False

        system = platform.system()

        try:
            # scrcpy >= 2.4 supports --video-source=camera
            cmd = [
                scrcpy_path,
                "--serial", self.device.serial,
                "--video-source=camera",
                "--no-audio",
                "--no-control",
                "--max-size=1280",
                "--max-fps=30",
            ]

            if system == "Linux":
                # Output to v4l2 loopback for OpenCV capture
                cmd.extend(["--v4l2-sink=/dev/video20", "--no-window"])

            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

            # Wait for scrcpy to initialise
            time.sleep(3.0)

            if proc.poll() is not None:
                stderr = proc.stderr.read().decode(errors="replace")
                logger.debug(f"scrcpy exited early: {stderr[:300]}")
                return False

            self.device.scrcpy_process = proc

            if system == "Linux":
                # Capture from the v4l2 loopback sink
                cap = cv2.VideoCapture(20)
                if not cap.isOpened():
                    proc.terminate()
                    return False
                self.cap = cap
                self._read_cap_props()
            else:
                # macOS: scrcpy opens a window; capture from that
                # is unreliable. Mark as connected but frames will
                # come from a periodic screenshot.
                self.width = 1280
                self.height = 720
                self.fps = 30.0

            self.connected = True
            logger.info(
                f"[{self.device.serial}] Connected via scrcpy camera mirror "
                f"(pid {proc.pid})"
            )
            return True

        except Exception as e:
            logger.error(f"scrcpy launch error: {e}")
            return False

    # --- Common helpers ---

    def _read_cap_props(self):
        if self.cap:
            fps = self.cap.get(cv2.CAP_PROP_FPS)
            self.fps = fps if fps and fps > 0 and not np.isnan(fps) else 30.0
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 1280
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 720

    def read(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """
        Read the next frame from the phone's camera.
        Returns: (success, frame_or_None, timestamp)
        """
        if not self.connected or self.cap is None:
            if not self.connect():
                return False, None, time.time()

        ret, frame = self.cap.read()
        timestamp = time.time()

        if not ret:
            self.connected = False
            self.device.error_message = "Frame read failed — phone may have disconnected."
            return False, None, timestamp

        self.frame_count += 1
        self.last_frame_time = timestamp
        self.device.last_heartbeat = timestamp
        self.device.is_connected = True
        self.device.error_message = ""
        return True, frame, timestamp

    def release(self):
        """Release the video capture and any child processes."""
        if self.cap:
            self.cap.release()
            self.cap = None

        if self.device.scrcpy_process:
            self.device.scrcpy_process.terminate()
            try:
                self.device.scrcpy_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.device.scrcpy_process.kill()
            self.device.scrcpy_process = None

        if self.device.forwarded_port and self.adb.available:
            self.adb.remove_forward(self.device.serial, self.device.forwarded_port)
            self.device.forwarded_port = None

        self.connected = False
        self.device.is_connected = False
        logger.info(f"[{self.device.serial}] Mobile camera source released.")

    def is_alive(self) -> bool:
        return self.connected and self.cap is not None and self.cap.isOpened()


# ---------------------------------------------------------------------------
# Mobile Connection Manager (singleton coordinator)
# ---------------------------------------------------------------------------

class MobileConnectionManager:
    """
    Manages all USB mobile phone connections.

    Provides:
    - Device discovery and enumeration (ADB + UVC scan)
    - Connection lifecycle management
    - Status reporting for the dashboard
    - Integration hooks for CameraPipelineManager
    """

    def __init__(self):
        self.adb = ADBHelper()
        self.devices: Dict[str, USBDevice] = {}
        self.sources: Dict[str, MobileCameraSource] = {}
        self.web_frames: Dict[str, Tuple[np.ndarray, float]] = {}
        self._next_local_port = 4747

    def update_web_frame(self, camera_id: str, frame: np.ndarray):
        """Update live frame received from a mobile phone browser."""
        self.web_frames[camera_id] = (frame, time.time())

    def get_web_frame(self, camera_id: str) -> Optional[Tuple[np.ndarray, float]]:
        """Get latest frame from web stream buffer."""
        return self.web_frames.get(camera_id)

    def scan(self) -> MobileConnectionStatus:
        """
        Scan for all connected mobile phones via ADB and UVC.
        Returns a status snapshot.
        """
        status = MobileConnectionStatus(
            adb_available=self.adb.available,
            scrcpy_available=bool(shutil.which("scrcpy")),
            platform=platform.system(),
        )

        discovered: Dict[str, USBDevice] = {}

        # 1. ADB devices (Android)
        if self.adb.available:
            for adb_dev in self.adb.list_devices():
                serial = adb_dev["serial"]
                info = self.adb.get_device_info(serial)

                dev = USBDevice(
                    serial=serial,
                    model=info.get("model", adb_dev.get("model", "Android Device")),
                    manufacturer=info.get("manufacturer", ""),
                    os=DeviceOS.ANDROID,
                    os_version=info.get("os_version", ""),
                )
                # Check if already connected
                if serial in self.devices and self.devices[serial].is_connected:
                    dev.is_connected = True
                    dev.connection_mode = self.devices[serial].connection_mode
                discovered[serial] = dev

        # 2. UVC video devices (could be phone in webcam mode)
        for uvc_dev in UVCScanner.find_video_devices():
            dev_key = f"uvc_{uvc_dev['index']}"
            if dev_key not in discovered:
                dev = USBDevice(
                    serial=dev_key,
                    model=uvc_dev["name"],
                    os=DeviceOS.UNKNOWN,
                    video_device_index=uvc_dev["index"],
                )
                if uvc_dev.get("is_phone"):
                    dev.os = DeviceOS.ANDROID
                if dev_key in self.devices and self.devices[dev_key].is_connected:
                    dev.is_connected = True
                discovered[dev_key] = dev

        self.devices = discovered
        status.devices = list(discovered.values())
        return status

    def connect_device(
        self,
        serial: str,
        mode: ConnectionMode = ConnectionMode.AUTO,
        camera_id: Optional[str] = None,
    ) -> Tuple[bool, USBDevice]:
        """
        Connect to a specific device and start capturing frames.
        Returns (success, device).
        """
        if serial not in self.devices:
            # Re-scan to make sure
            self.scan()
        if serial not in self.devices:
            dummy = USBDevice(serial=serial, error_message="Device not found.")
            return False, dummy

        device = self.devices[serial]

        # Allocate a unique local port for IP Webcam forwarding
        local_port = self._next_local_port
        self._next_local_port += 1

        source = MobileCameraSource(
            device=device,
            mode=mode,
            adb=self.adb,
            forward_local_port=local_port,
        )

        success = source.connect()
        if success:
            self.sources[serial] = source
            device.is_connected = True
            logger.info(
                f"Mobile device connected: {device.model} "
                f"({device.serial}) via {device.connection_mode.value}"
            )
        else:
            device.is_connected = False

        return success, device

    def disconnect_device(self, serial: str) -> bool:
        """Disconnect and release a device."""
        if serial in self.sources:
            self.sources[serial].release()
            del self.sources[serial]
        if serial in self.devices:
            self.devices[serial].is_connected = False
        return True

    def get_source(self, serial: str) -> Optional[MobileCameraSource]:
        """Get the active camera source for a connected device."""
        return self.sources.get(serial)

    def get_all_status(self) -> List[dict]:
        """Return JSON-serialisable status of all known devices."""
        return [
            {
                "serial": d.serial,
                "model": d.model,
                "manufacturer": d.manufacturer,
                "os": d.os.value,
                "os_version": d.os_version,
                "connection_mode": d.connection_mode.value,
                "is_connected": d.is_connected,
                "video_device_index": d.video_device_index,
                "forwarded_port": d.forwarded_port,
                "error_message": d.error_message,
                "last_heartbeat": d.last_heartbeat,
            }
            for d in self.devices.values()
        ]

    def disconnect_all(self):
        """Disconnect all devices. Called on shutdown."""
        for serial in list(self.sources.keys()):
            self.disconnect_device(serial)


# Module-level singleton
mobile_manager = MobileConnectionManager()
