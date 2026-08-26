'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  getMobileStatus,
  scanMobileDevices,
  getMobileDevices,
  connectMobileDevice,
  disconnectMobileDevice,
  getMobileStreamUrl,
  getHostInfo,
  launchCameraOnPhone,
  openBrowserCamOnPhone,
  startDirectUsbStream,
  connectRtspCamera,
  MobileStatus,
  MobileDevice,
  MobileConnectResponse,
} from '@/lib/api';

// ── Connection Mode Labels ─────────────────────────────────────────────
const MODE_LABELS: Record<string, { label: string; icon: string; desc: string }> = {
  auto:          { label: 'Auto Detect',   icon: 'auto_fix_high', desc: 'Automatically select the best connection method' },
  uvc_webcam:    { label: 'USB Webcam',    icon: 'videocam',      desc: 'Phone in UVC Webcam mode (Android 14+ / iOS 18+)' },
  adb_ipwebcam:  { label: 'IP Webcam',     icon: 'cell_tower',    desc: 'ADB + IP Webcam app on the phone' },
  adb_scrcpy:    { label: 'scrcpy Mirror', icon: 'screen_share',  desc: 'ADB + scrcpy camera mirror' },
};

const OS_ICONS: Record<string, string> = {
  android: 'phone_android',
  ios:     'phone_iphone',
  unknown: 'smartphone',
};

interface MobileConnectionTabProps {
  onDeviceConnected?: () => void;
}

// ── Component ──────────────────────────────────────────────────────────
export const MobileConnectionTab: React.FC<MobileConnectionTabProps> = ({ onDeviceConnected }) => {
  const [status, setStatus] = useState<MobileStatus | null>(null);
  const [devices, setDevices] = useState<MobileDevice[]>([]);
  const [isScanning, setIsScanning] = useState(false);
  const [connectingSerial, setConnectingSerial] = useState<string | null>(null);
  const [selectedMode, setSelectedMode] = useState<string>('auto');
  const [toast, setToast] = useState<{ type: 'success' | 'error' | 'info'; msg: string } | null>(null);
  const [previewSerial, setPreviewSerial] = useState<string | null>(null);

  const [hostInfo, setHostInfo] = useState<{ local_ip: string; web_cam_url: string; api_url: string } | null>(null);
  const [isLaunching, setIsLaunching] = useState(false);
  const [autoScanEnabled, setAutoScanEnabled] = useState(false);
  const scanAbortRef = useRef(false);

  const [rtspUrl, setRtspUrl] = useState('rtsp://192.168.1.105:8554/live');
  const [isConnectingRtsp, setIsConnectingRtsp] = useState(false);

  const handleConnectRtsp = async () => {
    if (!rtspUrl.trim()) {
      setToast({ type: 'error', msg: 'Please enter a valid RTSP or HTTP IP Camera URL.' });
      return;
    }
    setIsConnectingRtsp(true);
    try {
      await connectRtspCamera(rtspUrl.trim(), 'CAM_MOB_24151JEG', 'Pixel 6a (RTSP Stream)');
      setToast({ type: 'success', msg: `Connected to RTSP stream: ${rtspUrl}` });
      if (onDeviceConnected) onDeviceConnected();
    } catch (e: any) {
      setToast({ type: 'error', msg: `RTSP Connection Error: ${e.message}` });
    } finally {
      setIsConnectingRtsp(false);
    }
  };

  // Fetch status, devices & host info on initial mount
  useEffect(() => {
    const fetchInitial = async () => {
      try {
        const [st, devs, host] = await Promise.all([
          getMobileStatus(),
          scanMobileDevices(),
          getHostInfo(),
        ]);
        setStatus(st);
        if (devs && devs.length > 0) {
          setDevices(devs);
          const connected = devs.find((d) => d.is_connected);
          if (connected && !previewSerial) {
            setPreviewSerial(connected.serial);
          }
        }
        setHostInfo(host);
      } catch (e) {
        // silent
      }
    };
    fetchInitial();
  }, []);

  // Recurring polling only when autoScanEnabled is true
  useEffect(() => {
    if (!autoScanEnabled) return;
    const interval = setInterval(async () => {
      try {
        const [st, devs] = await Promise.all([
          getMobileStatus(),
          getMobileDevices(),
        ]);
        setStatus(st);
        if (devs && devs.length > 0) {
          setDevices(devs);
        }
      } catch (e) {
        // silent
      }
    }, 4000);
    return () => clearInterval(interval);
  }, [autoScanEnabled]);

  // Auto-dismiss toast
  useEffect(() => {
    if (toast) {
      const t = setTimeout(() => setToast(null), 5000);
      return () => clearTimeout(t);
    }
  }, [toast]);

  const handleScan = useCallback(async () => {
    setIsScanning(true);
    scanAbortRef.current = false;
    try {
      const devs = await scanMobileDevices();
      if (scanAbortRef.current) return;
      setDevices(devs);
      const freshStatus = await getMobileStatus();
      setStatus(freshStatus);
      setToast({ type: 'info', msg: `Scan complete — ${devs.length} device(s) found.` });
    } catch (e: any) {
      if (!scanAbortRef.current) {
        setToast({ type: 'error', msg: `Scan failed: ${e.message}` });
      }
    } finally {
      setIsScanning(false);
    }
  }, []);

  const handleStopScan = () => {
    scanAbortRef.current = true;
    setIsScanning(false);
    setAutoScanEnabled(false);
    setToast({ type: 'info', msg: 'Device scanning paused.' });
  };

  const handleLaunchCamera = async (serial?: string) => {
    setIsLaunching(true);
    try {
      const res = await launchCameraOnPhone(serial);
      setToast({ type: 'success', msg: res.message || 'Camera app launched on phone!' });
    } catch (e: any) {
      setToast({ type: 'error', msg: `Could not launch camera: ${e.message}` });
    } finally {
      setIsLaunching(false);
    }
  };

  const handleOpenBrowserCam = async (serial?: string) => {
    setIsLaunching(true);
    try {
      const res = await openBrowserCamOnPhone(serial);
      setToast({ type: 'success', msg: `Broadcaster opened on phone screen: ${res.url}` });
    } catch (e: any) {
      setToast({ type: 'error', msg: `Could not open browser on phone: ${e.message}` });
    } finally {
      setIsLaunching(false);
    }
  };

  const handleConnect = useCallback(async (serial: string) => {
    setConnectingSerial(serial);
    try {
      const res: MobileConnectResponse = await connectMobileDevice(serial, selectedMode);
      if (res.success) {
        setToast({ type: 'success', msg: `Connected ${res.model} to ONE EYE CCTV array via ${MODE_LABELS[res.connection_mode]?.label || res.connection_mode}` });
        // Refresh device list
        const devs = await scanMobileDevices();
        setDevices(devs);
        const freshStatus = await getMobileStatus();
        setStatus(freshStatus);
        if (onDeviceConnected) onDeviceConnected();
      } else {
        setToast({ type: 'error', msg: res.error_message || 'Connection failed.' });
      }
    } catch (e: any) {
      setToast({ type: 'error', msg: `Connect error: ${e.message}` });
    } finally {
      setConnectingSerial(null);
    }
  }, [selectedMode, onDeviceConnected]);

  const handleDisconnect = useCallback(async (serial: string) => {
    try {
      await disconnectMobileDevice(serial);
      setPreviewSerial(null);
      const devs = await scanMobileDevices();
      setDevices(devs);
      const freshStatus = await getMobileStatus();
      setStatus(freshStatus);
      if (onDeviceConnected) onDeviceConnected();
      setToast({ type: 'info', msg: 'Device disconnected.' });
    } catch (e: any) {
      setToast({ type: 'error', msg: `Disconnect error: ${e.message}` });
    }
  }, [onDeviceConnected]);

  const handleStartDirectUsbWebStream = async (serial?: string) => {
    setIsLaunching(true);
    try {
      const res = await startDirectUsbStream(serial);
      setToast({
        type: 'success',
        msg: '🚀 Direct USB Web Stream initiated! ADB reverse active & browser opened on phone.',
      });
      if (onDeviceConnected) onDeviceConnected();
    } catch (e: any) {
      setToast({ type: 'error', msg: `Direct USB Stream error: ${e.message}` });
    } finally {
      setIsLaunching(false);
    }
  };

  return (
    <div className="w-full space-y-5">
      {/* ── Toast ──────────────────────────────────────────────────── */}
      {toast && (
        <div
          className={`flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-all duration-300 ${
            toast.type === 'success'
              ? 'bg-severity-safe/10 text-severity-safe border border-severity-safe/30'
              : toast.type === 'error'
              ? 'bg-severity-critical/10 text-severity-critical border border-severity-critical/30'
              : 'bg-primary/10 text-primary border border-primary/30'
          }`}
        >
          <span className="material-symbols-outlined text-lg">
            {toast.type === 'success' ? 'check_circle' : toast.type === 'error' ? 'error' : 'info'}
          </span>
          <span className="flex-1">{toast.msg}</span>
          <button onClick={() => setToast(null)} className="hover:opacity-70 transition-opacity">
            <span className="material-symbols-outlined text-base">close</span>
          </button>
        </div>
      )}

      {/* ── Instant Mobile Web Camera Banner with Direct USB ──── */}
      <div className="bg-gradient-to-r from-blue-900/40 via-surface-container to-blue-950/40 border border-primary/40 rounded-xl p-5 shadow-sm">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-primary text-white flex items-center justify-center shadow-md">
              <span className="material-symbols-outlined text-2xl">usb</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-on-surface">Direct USB Web Stream Mode</h3>
                <span className="px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-600 font-mono text-[10px] font-bold">
                  PLUG &amp; PLAY
                </span>
              </div>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Streams 30 FPS video directly over the physical USB cable via ADB reverse tunneling (Zero Wi-Fi needed).
              </p>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-2 w-full md:w-auto">
            {/* 1-Click Launch Direct USB Stream */}
            <button
              onClick={() => handleStartDirectUsbWebStream()}
              disabled={isLaunching}
              className="flex-1 md:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 bg-emerald-600 hover:bg-emerald-500 active:scale-95 text-white text-xs font-mono font-bold rounded-lg shadow-sm transition-all"
              title="Reverse tunnel ports 3001 & 8001 and open camera broadcast on connected phone"
            >
              <span className="material-symbols-outlined text-sm">bolt</span>
              {isLaunching ? 'CONNECTING USB...' : 'LAUNCH DIRECT USB STREAM'}
            </button>

            <a
              href={hostInfo?.web_cam_url || '/mobile-cam'}
              target="_blank"
              rel="noreferrer"
              className="flex-1 md:flex-initial flex items-center justify-center gap-2 px-4 py-2.5 bg-primary text-white text-xs font-mono font-bold rounded-lg shadow-sm hover:bg-primary/90 transition-all"
            >
              <span className="material-symbols-outlined text-sm">open_in_new</span>
              Open Web Cam
            </a>
          </div>
        </div>
      </div>

      {/* ── Standard RTSP / IP Camera Stream Card ──── */}
      <div className="bg-gradient-to-r from-indigo-950/40 via-surface-container to-indigo-900/30 border border-indigo-500/40 rounded-xl p-5 shadow-sm">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div className="flex items-center gap-3.5">
            <div className="w-12 h-12 rounded-xl bg-indigo-600 text-white flex items-center justify-center shadow-md">
              <span className="material-symbols-outlined text-2xl">videocam</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="text-base font-bold text-on-surface">RTSP / IP Camera Stream Feed</h3>
                <span className="px-2 py-0.5 rounded bg-indigo-500/20 text-indigo-400 font-mono text-[10px] font-bold">
                  STANDARD RTSP (H.264)
                </span>
              </div>
              <p className="text-xs text-on-surface-variant mt-0.5">
                Ingest live camera video via standard RTSP / HTTP URL (Larix Broadcaster, IP Webcam Android App, or CCTV).
              </p>
            </div>
          </div>
        </div>

        <div className="mt-4 flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <span className="absolute left-3 top-1/2 -translate-y-1/2 material-symbols-outlined text-gray-400 text-lg">
              link
            </span>
            <input
              type="text"
              value={rtspUrl}
              onChange={(e) => setRtspUrl(e.target.value)}
              placeholder="rtsp://192.168.1.105:8554/live or http://192.168.1.105:8080/video"
              className="w-full pl-10 pr-4 py-2.5 bg-surface-container-high border border-outline/30 rounded-lg text-xs font-mono text-on-surface focus:outline-none focus:border-indigo-400 transition-all"
            />
          </div>
          <button
            onClick={handleConnectRtsp}
            disabled={isConnectingRtsp}
            className="w-full sm:w-auto flex items-center justify-center gap-2 px-5 py-2.5 bg-indigo-600 hover:bg-indigo-500 active:scale-95 text-white text-xs font-mono font-bold rounded-lg shadow-sm transition-all whitespace-nowrap"
          >
            <span className="material-symbols-outlined text-sm">
              {isConnectingRtsp ? 'sync' : 'cell_tower'}
            </span>
            {isConnectingRtsp ? 'CONNECTING RTSP...' : 'CONNECT RTSP CAMERA'}
          </button>
        </div>
      </div>

      {/* ── System Status Card ─────────────────────────────────────── */}
      <div className="level-1-panel rounded-xl p-5">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4 mb-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <span className="material-symbols-outlined text-primary">usb</span>
            </div>
            <div>
              <h2 className="text-base font-semibold text-on-surface">USB Mobile Bridge</h2>
              <p className="text-xs text-on-surface-variant">Connect a phone camera as a safety monitoring feed</p>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {/* Auto Scan Toggle Button */}
            <button
              onClick={() => {
                const next = !autoScanEnabled;
                setAutoScanEnabled(next);
                setToast({
                  type: 'info',
                  msg: next ? 'Auto-scan enabled (polling every 4s).' : 'Auto-scan paused.',
                });
              }}
              className={`flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-lg border transition-all ${
                autoScanEnabled
                  ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40'
                  : 'bg-surface-container-high text-on-surface-variant border-outline-variant hover:text-on-surface'
              }`}
            >
              <span className="material-symbols-outlined text-base">
                {autoScanEnabled ? 'pause_circle' : 'play_circle'}
              </span>
              Auto-Poll: {autoScanEnabled ? 'ON' : 'PAUSED'}
            </button>

            {/* Auto Open Camera on phone */}
            <button
              onClick={() => handleLaunchCamera()}
              disabled={isLaunching || !status?.adb_available}
              className="flex items-center gap-1.5 px-3 py-2 bg-surface-container-high text-on-surface text-xs font-semibold rounded-lg hover:bg-surface-variant border border-outline-variant disabled:opacity-40 transition-all"
              title="Send ADB command to open native camera on connected phone"
            >
              <span className="material-symbols-outlined text-base text-primary">photo_camera</span>
              Auto-Open Camera App
            </button>

            {/* Scan or Stop Button */}
            {isScanning ? (
              <button
                onClick={handleStopScan}
                className="flex items-center gap-2 px-4 py-2 bg-severity-critical text-white text-sm font-medium rounded-lg hover:bg-severity-critical/90 shadow-md transition-all animate-pulse"
              >
                <span className="material-symbols-outlined text-lg">stop_circle</span>
                Stop Scanning
              </button>
            ) : (
              <button
                onClick={handleScan}
                className="flex items-center gap-2 px-4 py-2 bg-primary text-on-primary text-sm font-medium rounded-lg hover:bg-primary/90 transition-all duration-200"
              >
                <span className="material-symbols-outlined text-lg">search</span>
                Scan for Devices
              </button>
            )}
          </div>
        </div>

        {/* Status Chips */}
        <div className="flex flex-wrap gap-3">
          <StatusChip
            icon="adb"
            label="ADB"
            value={status?.adb_available ? 'Available' : 'Not Found'}
            ok={status?.adb_available ?? false}
          />
          <StatusChip
            icon="screen_share"
            label="scrcpy"
            value={status?.scrcpy_available ? 'Available' : 'Not Found'}
            ok={status?.scrcpy_available ?? false}
          />
          <StatusChip
            icon="computer"
            label="Platform"
            value={status?.platform || '—'}
            ok={true}
          />
          <StatusChip
            icon="devices"
            label="Devices"
            value={`${status?.connected_count ?? 0} / ${status?.device_count ?? 0}`}
            ok={(status?.connected_count ?? 0) > 0}
          />
        </div>
      </div>

      {/* ── Connection Mode Selector ───────────────────────────────── */}
      <div className="level-1-panel rounded-xl p-5">
        <h3 className="text-sm font-semibold text-on-surface mb-3 flex items-center gap-2">
          <span className="material-symbols-outlined text-base text-on-surface-variant">settings</span>
          Connection Mode
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {Object.entries(MODE_LABELS).map(([key, { label, icon, desc }]) => (
            <button
              key={key}
              onClick={() => setSelectedMode(key)}
              className={`relative p-4 rounded-lg border text-left transition-all duration-200 ${
                selectedMode === key
                  ? 'bg-primary/5 border-primary/40 ring-1 ring-primary/30'
                  : 'bg-surface-container-lowest border-outline-variant hover:bg-surface-container-low'
              }`}
            >
              <div className="flex items-center gap-2.5 mb-1.5">
                <span className={`material-symbols-outlined text-lg ${
                  selectedMode === key ? 'text-primary' : 'text-on-surface-variant'
                }`}>{icon}</span>
                <span className={`text-sm font-medium ${
                  selectedMode === key ? 'text-primary' : 'text-on-surface'
                }`}>{label}</span>
              </div>
              <p className="text-xs text-on-surface-variant leading-relaxed">{desc}</p>
              {selectedMode === key && (
                <span className="absolute top-3 right-3 material-symbols-outlined text-primary text-base">
                  check_circle
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* ── Device List ────────────────────────────────────────────── */}
      <div className="level-1-panel rounded-xl p-5">
        <h3 className="text-sm font-semibold text-on-surface mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-base text-on-surface-variant">smartphone</span>
          Discovered Devices
          {devices.length > 0 && (
            <span className="ml-1 text-xs font-normal text-on-surface-variant">
              ({devices.length})
            </span>
          )}
        </h3>

        {devices.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-on-surface-variant">
            <span className="material-symbols-outlined text-5xl mb-3 opacity-40">phone_disabled</span>
            <p className="text-sm font-medium mb-1">No devices detected</p>
            <p className="text-xs opacity-70 max-w-sm text-center leading-relaxed">
              Connect an Android phone via USB with USB Debugging enabled, or put your phone in USB Webcam mode. Then click &ldquo;Scan for Devices&rdquo;.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {devices.map((dev) => (
              <DeviceCard
                key={dev.serial}
                device={dev}
                isConnecting={connectingSerial === dev.serial}
                onConnect={() => handleConnect(dev.serial)}
                onDisconnect={() => handleDisconnect(dev.serial)}
                onPreview={() => setPreviewSerial(dev.serial === previewSerial ? null : dev.serial)}
                isPreviewOpen={previewSerial === dev.serial}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Live Preview ───────────────────────────────────────────── */}
      {previewSerial && (
        <div className="level-1-panel rounded-xl p-5">
          <div className="flex items-center justify-between mb-3">
            <h3 className="text-sm font-semibold text-on-surface flex items-center gap-2">
              <span className="material-symbols-outlined text-base text-severity-safe">videocam</span>
              Live Preview — {previewSerial}
              <span className="flex items-center gap-1.5 ml-3">
                <span className="w-2 h-2 rounded-full bg-severity-safe animate-pulse" />
                <span className="text-xs text-severity-safe font-mono">LIVE</span>
              </span>
            </h3>
            <button
              onClick={() => setPreviewSerial(null)}
              className="text-on-surface-variant hover:text-on-surface transition-colors"
            >
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          </div>
          <div className="relative bg-dark-surface rounded-lg overflow-hidden" style={{ aspectRatio: '16/9' }}>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={getMobileStreamUrl(previewSerial, 15)}
              alt="Mobile camera live feed"
              className="w-full h-full object-contain"
            />
            <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/70 to-transparent h-16 flex items-end px-4 pb-3">
              <span className="text-white text-xs font-mono opacity-80">
                MJPEG • 15 FPS • {previewSerial}
              </span>
            </div>
          </div>
        </div>
      )}

      {/* ── Setup Guide ────────────────────────────────────────────── */}
      <div className="level-1-panel rounded-xl p-5">
        <h3 className="text-sm font-semibold text-on-surface mb-4 flex items-center gap-2">
          <span className="material-symbols-outlined text-base text-on-surface-variant">help_outline</span>
          Setup Guide
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <GuideCard
            step={1}
            title="USB Webcam Mode"
            icon="videocam"
            lines={[
              'Android 14+: Settings → Developer Options → USB Preferences → Webcam',
              'iOS 18+: Connect via USB — auto-detected as Continuity Camera',
              'Appears as a standard video device — no additional software needed',
            ]}
          />
          <GuideCard
            step={2}
            title="ADB + IP Webcam"
            icon="cell_tower"
            lines={[
              'Install "IP Webcam" from Google Play on your Android phone',
              'Start the IP Webcam server on the phone',
              'Connect phone via USB and enable USB Debugging',
              'Install ADB on this machine (brew install android-platform-tools)',
            ]}
          />
          <GuideCard
            step={3}
            title="ADB + scrcpy"
            icon="screen_share"
            lines={[
              'Install scrcpy: brew install scrcpy',
              'Requires scrcpy ≥ 2.4 for --video-source=camera',
              'Phone must have USB Debugging enabled',
              'Works on Android 10+ with ADB authorized',
            ]}
          />
        </div>
      </div>
    </div>
  );
};

// ── Sub-Components ─────────────────────────────────────────────────────

const StatusChip: React.FC<{
  icon: string;
  label: string;
  value: string;
  ok: boolean;
}> = ({ icon, label, value, ok }) => (
  <div className={`flex items-center gap-2 px-3 py-2 rounded-lg text-xs font-medium border ${
    ok
      ? 'bg-severity-safe/5 text-severity-safe border-severity-safe/20'
      : 'bg-surface-container text-on-surface-variant border-outline-variant'
  }`}>
    <span className="material-symbols-outlined text-base">{icon}</span>
    <span className="opacity-70">{label}:</span>
    <span className="font-mono">{value}</span>
  </div>
);

const DeviceCard: React.FC<{
  device: MobileDevice;
  isConnecting: boolean;
  onConnect: () => void;
  onDisconnect: () => void;
  onPreview: () => void;
  isPreviewOpen: boolean;
}> = ({ device, isConnecting, onConnect, onDisconnect, onPreview, isPreviewOpen }) => (
  <div className={`flex items-center gap-4 p-4 rounded-lg border transition-all duration-200 ${
    device.is_connected
      ? 'bg-severity-safe/5 border-severity-safe/25'
      : 'bg-surface-container-lowest border-outline-variant hover:bg-surface-container-low'
  }`}>
    {/* Device Icon */}
    <div className={`w-11 h-11 rounded-lg flex items-center justify-center flex-shrink-0 ${
      device.is_connected ? 'bg-severity-safe/10' : 'bg-surface-container-high'
    }`}>
      <span className={`material-symbols-outlined text-2xl ${
        device.is_connected ? 'text-severity-safe' : 'text-on-surface-variant'
      }`}>
        {OS_ICONS[device.os] || 'smartphone'}
      </span>
    </div>

    {/* Device Info */}
    <div className="flex-1 min-w-0">
      <div className="flex items-center gap-2 mb-0.5">
        <span className="text-sm font-semibold text-on-surface truncate">{device.model}</span>
        {device.is_connected && (
          <span className="flex items-center gap-1 text-xs text-severity-safe">
            <span className="w-1.5 h-1.5 rounded-full bg-severity-safe animate-pulse" />
            ONLINE
          </span>
        )}
      </div>
      <div className="flex items-center gap-3 text-xs text-on-surface-variant">
        <span className="font-mono">{device.serial}</span>
        {device.manufacturer && <span>• {device.manufacturer}</span>}
        {device.os_version && <span>• v{device.os_version}</span>}
        {device.connection_mode !== 'auto' && device.is_connected && (
          <span className="text-primary font-medium">
            via {MODE_LABELS[device.connection_mode]?.label || device.connection_mode}
          </span>
        )}
      </div>
      {device.error_message && (
        <p className="text-xs text-severity-critical mt-1">{device.error_message}</p>
      )}
    </div>

    {/* Actions */}
    <div className="flex items-center gap-2 flex-shrink-0">
      {device.is_connected ? (
        <>
          <button
            onClick={onPreview}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-md text-xs font-medium transition-all duration-200 ${
              isPreviewOpen
                ? 'bg-primary text-on-primary'
                : 'bg-primary/10 text-primary hover:bg-primary/20'
            }`}
          >
            <span className="material-symbols-outlined text-sm">
              {isPreviewOpen ? 'visibility_off' : 'visibility'}
            </span>
            {isPreviewOpen ? 'Hide' : 'Preview'}
          </button>
          <button
            onClick={onDisconnect}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-severity-critical/10 text-severity-critical text-xs font-medium hover:bg-severity-critical/20 transition-all duration-200"
          >
            <span className="material-symbols-outlined text-sm">link_off</span>
            Disconnect
          </button>
        </>
      ) : (
        <button
          onClick={onConnect}
          disabled={isConnecting}
          className="flex items-center gap-1.5 px-4 py-2 rounded-md bg-primary text-on-primary text-xs font-medium hover:bg-primary/90 disabled:opacity-50 disabled:cursor-not-allowed transition-all duration-200"
        >
          <span className={`material-symbols-outlined text-sm ${isConnecting ? 'animate-spin' : ''}`}>
            {isConnecting ? 'progress_activity' : 'link'}
          </span>
          {isConnecting ? 'Connecting...' : 'Connect'}
        </button>
      )}
    </div>
  </div>
);

const GuideCard: React.FC<{
  step: number;
  title: string;
  icon: string;
  lines: string[];
}> = ({ step, title, icon, lines }) => (
  <div className="bg-surface-container-lowest rounded-lg border border-outline-variant p-4">
    <div className="flex items-center gap-2.5 mb-3">
      <div className="w-7 h-7 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-bold">
        {step}
      </div>
      <span className="material-symbols-outlined text-lg text-on-surface-variant">{icon}</span>
      <span className="text-sm font-semibold text-on-surface">{title}</span>
    </div>
    <ul className="space-y-1.5">
      {lines.map((line, i) => (
        <li key={i} className="flex items-start gap-2 text-xs text-on-surface-variant leading-relaxed">
          <span className="material-symbols-outlined text-xs mt-0.5 text-primary/60 flex-shrink-0">
            chevron_right
          </span>
          {line}
        </li>
      ))}
    </ul>
  </div>
);

export default MobileConnectionTab;
