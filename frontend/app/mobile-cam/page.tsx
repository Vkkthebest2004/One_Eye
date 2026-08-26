'use client';

import React, { useEffect, useRef, useState } from 'react';
import { createZone } from '@/lib/api';
import { useOneEyeWebSocket } from '@/lib/websocket';

export default function MobileCamPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const overlayCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const markerCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  // WebSocket Live Telemetry for Mobile Overlay
  const { cameraTracks, visualZones, activeAlerts } = useOneEyeWebSocket();

  const [isStreaming, setIsStreaming] = useState(false);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [fps, setFps] = useState<number>(0);
  const [statusMsg, setStatusMsg] = useState('Initializing mobile camera...');
  const [hasTorch, setHasTorch] = useState(false);
  const [isTorchOn, setIsTorchOn] = useState(false);
  const [quality, setQuality] = useState<'720p' | '1080p' | '480p'>('720p');

  // Interactive Visual Danger Marking on Phone
  const [isMarkingDanger, setIsMarkingDanger] = useState(false);
  const [dangerPoints, setDangerPoints] = useState<[number, number][]>([]);
  const [dangerName, setDangerName] = useState('Dangerous Machinery');
  const [isBoxMode, setIsBoxMode] = useState(true);
  const [dangerBoxStart, setDangerBoxStart] = useState<[number, number] | null>(null);
  const [markerSavedMsg, setMarkerSavedMsg] = useState<string | null>(null);

  const [videoDevices, setVideoDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState<string>('');

  const streamRef = useRef<MediaStream | null>(null);
  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(Date.now());

  // Enumerate cameras (populates device list and labels after permission)
  const refreshDevices = async () => {
    try {
      const devices = await navigator.mediaDevices.enumerateDevices();
      const inputs = devices.filter((d) => d.kind === 'videoinput');
      setVideoDevices(inputs);
      return inputs;
    } catch (e) {
      return [];
    }
  };

  // Start Camera Stream (Progressive Lens Cascade for Rear & Front Sensors)
  const startCamera = async (target?: string) => {
    try {
      // 1. Release previous camera hardware cleanly
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => {
          try {
            t.stop();
          } catch (e) {}
        });
        streamRef.current = null;
        // Allow hardware sensor 80ms to release cleanly on mobile OS
        await new Promise((r) => setTimeout(r, 80));
      }

      const mode: 'environment' | 'user' = target === 'user' ? 'user' : 'environment';
      const isSpecificDevice = target && target.length > 20 && target !== 'user' && target !== 'environment';

      // 2. Ordered list of constraint strategies to guarantee rear/front selection without OverconstrainedError
      const candidateConstraints: MediaStreamConstraints[] = [];

      if (isSpecificDevice) {
        candidateConstraints.push(
          { video: { deviceId: { ideal: target }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
          { video: { deviceId: { exact: target } }, audio: false }
        );
      }

      if (mode === 'environment') {
        candidateConstraints.push(
          { video: { facingMode: { exact: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
          { video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
          { video: { facingMode: 'environment' }, audio: false }
        );
      } else {
        candidateConstraints.push(
          { video: { facingMode: { exact: 'user' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
          { video: { facingMode: { ideal: 'user' }, width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
          { video: { facingMode: 'user' }, audio: false }
        );
      }

      // Universal fallbacks
      candidateConstraints.push(
        { video: { width: { ideal: 1280 }, height: { ideal: 720 } }, audio: false },
        { video: true, audio: false }
      );

      let stream: MediaStream | null = null;
      let lastErr: any = null;

      for (const constraints of candidateConstraints) {
        try {
          stream = await navigator.mediaDevices.getUserMedia(constraints);
          if (stream) break;
        } catch (e) {
          lastErr = e;
        }
      }

      if (!stream) {
        throw lastErr || new Error('Unable to access camera sensor');
      }

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        videoRef.current.setAttribute('playsinline', 'true');
        videoRef.current.setAttribute('muted', 'true');
        videoRef.current.muted = true;
        try {
          await videoRef.current.play();
        } catch (e) {
          // autoPlay handles it
        }
      }

      // Update discovered devices & active label
      await refreshDevices();
      const currentTrack = stream.getVideoTracks()[0];
      const settings = currentTrack?.getSettings ? currentTrack.getSettings() : {};
      const activeLabel = currentTrack?.label || (mode === 'user' ? 'Front Selfie Camera' : 'Back Rear Camera (Wide)');

      const isBack =
        settings.facingMode === 'environment' ||
        activeLabel.toLowerCase().includes('back') ||
        activeLabel.toLowerCase().includes('rear') ||
        mode === 'environment';

      setFacingMode(isBack ? 'environment' : 'user');
      setSelectedDeviceId(settings.deviceId || '');

      // Check for torch capability
      const capabilities: any = currentTrack?.getCapabilities ? currentTrack.getCapabilities() : {};
      setHasTorch(!!capabilities.torch);

      setStatusMsg(`Active: ${activeLabel}`);
      setIsStreaming(true);
      connectWebSocket();
    } catch (err: any) {
      console.error('Camera access error:', err);
      setIsStreaming(false);
      setStatusMsg(`Camera Error: ${err.message || 'Permission denied'}`);
    }
  };

  const isSendingRef = useRef(false);
  const wakeLockRef = useRef<any>(null);

  // Acquire Screen Wake Lock to prevent screen sleep/throttling
  const acquireWakeLock = async () => {
    try {
      if ('wakeLock' in navigator) {
        wakeLockRef.current = await (navigator as any).wakeLock.request('screen');
      }
    } catch (e) {
      console.warn('Wake Lock not supported or rejected', e);
    }
  };

  // Connect WebSocket to ONE EYE Backend
  const connectWebSocket = () => {
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) return;
      const host = window.location.hostname || 'localhost';
      const wsUrl = `ws://${host}:8001/api/mobile/ws/stream/CAM_MOBILE`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        setIsStreaming(true);
        setStatusMsg('STREAMING LIVE TO ONE EYE SAFETY ENGINE');
        acquireWakeLock();
      };

      ws.onclose = () => {
        if (streamRef.current) {
          setStatusMsg('Stream disconnected. Reconnecting in 2s...');
          setTimeout(() => {
            if (streamRef.current) connectWebSocket();
          }, 2000);
        } else {
          setIsStreaming(false);
          setStatusMsg('Ready. Tap Enable Camera to start streaming.');
        }
      };

      ws.onerror = () => {
        console.warn('WebSocket stream error');
      };

      wsRef.current = ws;
    } catch (e) {
      console.error('WebSocket connection failed:', e);
    }
  };

  // Frame Capture and Transmission Loop (30-60 FPS with in-flight backpressure)
  useEffect(() => {
    let animationFrameId: number;
    let lastSent = 0;
    const targetFps = quality === '1080p' ? 30 : 30;
    const targetInterval = 1000 / targetFps;

    const sendFrame = () => {
      const now = performance.now();
      if (
        now - lastSent >= targetInterval &&
        isStreaming &&
        !isSendingRef.current &&
        wsRef.current &&
        wsRef.current.readyState === WebSocket.OPEN &&
        videoRef.current &&
        videoRef.current.readyState >= 2
      ) {
        const video = videoRef.current;
        const canvas = canvasRef.current || document.createElement('canvas');
        if (!canvasRef.current) canvasRef.current = canvas;

        const w = video.videoWidth || 1280;
        const h = video.videoHeight || 720;

        // Optimized resolution for high FPS transmission
        const maxDim = quality === '1080p' ? 1280 : 960;
        const scale = w > maxDim ? maxDim / w : 1.0;
        canvas.width = Math.round(w * scale);
        canvas.height = Math.round(h * scale);

        const ctx = canvas.getContext('2d', { alpha: false });
        if (ctx) {
          ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
          isSendingRef.current = true;
          canvas.toBlob(
            (blob) => {
              if (!blob) {
                isSendingRef.current = false;
                return;
              }
              blob
                .arrayBuffer()
                .then((buffer) => {
                  const ws = wsRef.current;
                  if (ws && ws.readyState === WebSocket.OPEN) {
                    try {
                      ws.send(buffer);
                      frameCountRef.current++;
                    } catch (e) {
                      // ignore
                    }
                  }
                })
                .catch(() => null)
                .finally(() => {
                  isSendingRef.current = false;
                });
            },
            'image/jpeg',
            0.60
          );
        }

        lastSent = now;

        // FPS measurement
        const currentTime = Date.now();
        if (currentTime - lastFpsUpdateRef.current >= 1000) {
          setFps(frameCountRef.current);
          frameCountRef.current = 0;
          lastFpsUpdateRef.current = currentTime;
        }
      }

      animationFrameId = requestAnimationFrame(sendFrame);
    };

    animationFrameId = requestAnimationFrame(sendFrame);

    return () => cancelAnimationFrame(animationFrameId);
  }, [isStreaming, quality]);

  // Cleanup on unmount (Do NOT auto-start camera on page load)
  useEffect(() => {
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const toggleCamera = async () => {
    const nextMode = facingMode === 'environment' ? 'user' : 'environment';
    await startCamera(nextMode);
  };

  const toggleTorch = async () => {
    if (!streamRef.current) return;
    const track = streamRef.current.getVideoTracks()[0];
    try {
      await (track as any).applyConstraints({
        advanced: [{ torch: !isTorchOn }],
      });
      setIsTorchOn(!isTorchOn);
    } catch (e) {
      console.warn('Torch not supported', e);
    }
  };

  // Open Interactive Freeze Photo & Danger Marker on Phone
  const handleOpenMarker = () => {
    if (!videoRef.current || !markerCanvasRef.current) return;
    const video = videoRef.current;
    const canvas = markerCanvasRef.current;
    canvas.width = video.videoWidth || 1280;
    canvas.height = video.videoHeight || 720;
    const ctx = canvas.getContext('2d');
    if (ctx) {
      ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    }
    setDangerPoints([]);
    setDangerBoxStart(null);
    setMarkerSavedMsg(null);
    setIsMarkingDanger(true);
  };

  const handleMarkerClick = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = markerCanvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const nx = Math.min(1.0, Math.max(0.0, (e.clientX - rect.left) / rect.width));
    const ny = Math.min(1.0, Math.max(0.0, (e.clientY - rect.top) / rect.height));

    if (isBoxMode) {
      if (!dangerBoxStart) {
        setDangerBoxStart([nx, ny]);
        setDangerPoints([[nx, ny]]);
      } else {
        const [x1, y1] = dangerBoxStart;
        const xMin = Math.min(x1, nx);
        const xMax = Math.max(x1, nx);
        const yMin = Math.min(y1, ny);
        const yMax = Math.max(y1, ny);
        setDangerPoints([
          [xMin, yMin],
          [xMax, yMin],
          [xMax, yMax],
          [xMin, yMax],
        ]);
        setDangerBoxStart(null);
      }
    } else {
      setDangerPoints((prev) => [...prev, [nx, ny]]);
    }
  };

  const handleSaveMobileDangerZone = async () => {
    if (dangerPoints.length < 3) {
      alert('Please mark at least 3 points or complete the box around the dangerous place.');
      return;
    }
    try {
      const zoneId = `ZONE_MOB_${Date.now().toString().slice(-6)}`;
      const keyframeB64 = markerCanvasRef.current ? markerCanvasRef.current.toDataURL('image/jpeg', 0.85) : undefined;
      await createZone({
        id: zoneId,
        camera_id: 'CAM_MOBILE',
        name: dangerName.trim() || 'Visual Danger Perimeter',
        polygon: dangerPoints,
        severity: 95,
        warning_delay_seconds: 0.0,
        critical_delay_seconds: 3.0,
        active: true,
        keyframe_b64: keyframeB64,
      } as any);
      setMarkerSavedMsg('✅ Saved to Visual Memory! Homography Tracking Active.');
      setTimeout(() => {
        setIsMarkingDanger(false);
        setMarkerSavedMsg(null);
      }, 1400);
    } catch (e: any) {
      alert(`Error saving zone: ${e.message || 'Check backend connection'}`);
    }
  };

  // Live Computer Vision & Visual Danger Overlay on Phone Display
  useEffect(() => {
    const canvas = overlayCanvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Match canvas dimensions to client viewport
    const width = canvas.parentElement?.clientWidth || window.innerWidth;
    const height = canvas.parentElement?.clientHeight || window.innerHeight;
    canvas.width = width;
    canvas.height = height;
    ctx.clearRect(0, 0, width, height);

    // 1. Draw dynamically tracked visual danger zones on the phone
    const zones = visualZones['CAM_MOBILE'] || visualZones['CAM_MOB_24151JEG'] || [];
    zones.forEach((z: any) => {
      // ONLY draw if the object is ACTUALLY recognized in view!
      if (!z.is_visible) return;
      const poly = z.polygon || [];
      if (!poly || poly.length < 3) return;

      ctx.save();
      ctx.beginPath();
      poly.forEach(([px, py]: [number, number], idx: number) => {
        const x = px * width;
        const y = py * height;
        if (idx === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.closePath();

      // Pulsating Danger Glow Fill
      ctx.fillStyle = 'rgba(239, 68, 68, 0.25)';
      ctx.fill();
      ctx.lineWidth = 2.5;
      ctx.strokeStyle = '#ef4444';
      ctx.setLineDash([6, 4]);
      ctx.stroke();

      // Zone Banner
      const [firstX, firstY] = poly[0];
      const tagText = `🔒 DANGER ZONE: ${(z.name || 'FORBIDDEN').toUpperCase()}`;
      ctx.font = 'bold 11px monospace';
      const tagW = ctx.measureText(tagText).width + 10;
      ctx.fillStyle = '#b91c1c';
      ctx.fillRect(firstX * width, Math.max(0, firstY * height - 16), tagW, 16);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(tagText, firstX * width + 5, Math.max(12, firstY * height - 4));
      ctx.restore();
    });

    // 2. Draw live detected people and breach status on the phone
    const tracks = cameraTracks['CAM_MOBILE'] || cameraTracks['CAM_MOB_24151JEG'] || [];
    tracks.forEach((track: any) => {
      let x = 0, y = 0, w = 0, h = 0;
      if (track.norm_bbox && track.norm_bbox.length === 4) {
        const [nx1, ny1, nx2, ny2] = track.norm_bbox;
        x = nx1 * width;
        y = ny1 * height;
        w = Math.max(16, (nx2 - nx1) * width);
        h = Math.max(24, (ny2 - ny1) * height);
      }

      const isBreaching = !!track.current_zone_id || (track.current_risk_score ?? 0) >= 60;
      const strokeColor = isBreaching ? '#ef4444' : '#10b981';

      ctx.save();
      ctx.lineWidth = isBreaching ? 3 : 2;
      ctx.strokeStyle = strokeColor;
      ctx.strokeRect(x, y, w, h);

      // Top Tag
      const tagText = isBreaching ? `🚨 IN DANGER ZONE!` : `👤 Person #${track.track_id ?? '01'}`;
      ctx.font = 'bold 11px monospace';
      const tagW = ctx.measureText(tagText).width + 8;
      ctx.fillStyle = strokeColor;
      ctx.fillRect(x, Math.max(0, y - 16), tagW, 16);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(tagText, x + 4, Math.max(12, y - 4));
      ctx.restore();
    });
  }, [cameraTracks, visualZones]);

  return (
    <div className="fixed inset-0 bg-black flex flex-col justify-between text-white font-sans select-none overflow-hidden">
      {/* Hidden Canvas */}
      <canvas ref={canvasRef} className="hidden" />

      {/* Fullscreen Video */}
      <video
        ref={videoRef}
        autoPlay
        playsInline
        muted
        className="absolute inset-0 w-full h-full object-cover"
      />

      {/* Live AI Overlay Canvas on Phone */}
      <canvas
        ref={overlayCanvasRef}
        className="absolute inset-0 w-full h-full object-cover pointer-events-none z-10"
      />

      {/* Top Header Bar */}
      <div className="relative z-10 p-4 bg-gradient-to-b from-black/80 via-black/40 to-transparent flex items-center justify-between">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-blue-600 flex items-center justify-center shadow-lg">
            <span className="material-symbols-outlined text-white text-lg">visibility</span>
          </div>
          <div>
            <h1 className="text-sm font-bold tracking-tight text-white flex items-center gap-1.5">
              ONE EYE <span className="text-[10px] text-blue-400 font-mono">MOBILE NODE</span>
            </h1>
            <p className="text-[11px] text-gray-300 font-mono">CAM_MOBILE // Plant Sector 01</p>
          </div>
        </div>

        {/* Action Button: Mark Danger Area directly on Phone */}
        <div className="flex items-center gap-2">
          {isStreaming && (
            <button
              onClick={handleOpenMarker}
              className="px-3 py-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg text-xs font-mono font-bold shadow-lg flex items-center gap-1 border border-red-400/40 active:scale-95 transition-all"
            >
              <span className="material-symbols-outlined text-sm">security</span>
              📸 Mark Danger
            </button>
          )}

          <div
            className={`px-2.5 py-1 rounded-full text-xs font-mono font-bold flex items-center gap-1.5 shadow-md ${
              isStreaming
                ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/40'
                : 'bg-amber-500/20 text-amber-400 border border-amber-500/40'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                isStreaming ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'
              }`}
            />
            {isStreaming ? `${fps} FPS` : 'CONNECTING'}
          </div>
        </div>
      </div>

      {/* Interactive Freeze Photo Danger Marker Modal on Phone */}
      {isMarkingDanger && (
        <div className="fixed inset-0 z-50 bg-black/95 flex flex-col justify-between p-4 overflow-y-auto">
          <div className="flex justify-between items-center pb-2 border-b border-gray-700">
            <h3 className="text-sm font-bold font-mono text-red-400 flex items-center gap-1.5">
              <span className="material-symbols-outlined text-base">security</span>
              MARK DANGER PLACE // VISUAL MEMORY
            </h3>
            <button
              onClick={() => setIsMarkingDanger(false)}
              className="p-1 rounded-lg bg-gray-800 text-gray-400 hover:text-white"
            >
              <span className="material-symbols-outlined text-lg">close</span>
            </button>
          </div>

          <div className="relative my-3 flex items-center justify-center bg-black rounded-xl overflow-hidden border border-gray-700">
            <canvas
              ref={markerCanvasRef}
              onClick={handleMarkerClick}
              className="w-full max-h-[50vh] object-contain cursor-crosshair"
            />
            {/* SVG Polygon Preview */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {dangerPoints.length >= 2 && (
                <polygon
                  points={dangerPoints.map(([x, y]) => `${x * 100}%,${y * 100}%`).join(' ')}
                  fill="rgba(239, 68, 68, 0.25)"
                  stroke="#ef4444"
                  strokeWidth="3"
                  strokeDasharray="6,4"
                />
              )}
              {dangerPoints.map(([x, y], idx) => (
                <circle
                  key={idx}
                  cx={`${x * 100}%`}
                  cy={`${y * 100}%`}
                  r="6"
                  fill="#ef4444"
                  stroke="#ffffff"
                  strokeWidth="2"
                />
              ))}
            </svg>
          </div>

          {markerSavedMsg ? (
            <div className="p-3 bg-emerald-950/80 border border-emerald-500/50 rounded-xl text-center font-mono text-xs font-bold text-emerald-300">
              {markerSavedMsg}
            </div>
          ) : (
            <div className="flex flex-col gap-2.5 bg-gray-900/90 p-3 rounded-xl border border-gray-700">
              <div className="flex items-center justify-between text-xs font-mono">
                <span className="text-gray-400">
                  {isBoxMode ? 'Tap 2 corners for box' : 'Tap points for polygon'} ({dangerPoints.length} pts)
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => { setIsBoxMode(true); setDangerPoints([]); setDangerBoxStart(null); }}
                    className={`px-2 py-1 rounded text-[11px] font-bold ${isBoxMode ? 'bg-red-600 text-white' : 'bg-gray-800 text-gray-300'}`}
                  >
                    2-Click Box
                  </button>
                  <button
                    onClick={() => { setIsBoxMode(false); setDangerPoints([]); setDangerBoxStart(null); }}
                    className={`px-2 py-1 rounded text-[11px] font-bold ${!isBoxMode ? 'bg-red-600 text-white' : 'bg-gray-800 text-gray-300'}`}
                  >
                    Polygon
                  </button>
                  <button
                    onClick={() => { setDangerPoints([]); setDangerBoxStart(null); }}
                    className="px-2 py-1 bg-gray-800 text-gray-400 hover:text-white rounded text-[11px]"
                  >
                    Clear
                  </button>
                </div>
              </div>

              {/* Quick Presets */}
              <div className="flex flex-wrap gap-1.5">
                {['🚨 Dangerous Machine', '⚠️ High Voltage Area', '🛑 Forbidden Floor Zone'].map((name) => (
                  <button
                    key={name}
                    onClick={() => setDangerName(name)}
                    className={`px-2 py-1 rounded-md text-[10px] font-mono border transition ${
                      dangerName === name
                        ? 'bg-red-600/30 border-red-500 text-red-300 font-bold'
                        : 'bg-gray-800 border-gray-700 text-gray-400'
                    }`}
                  >
                    {name}
                  </button>
                ))}
              </div>

              <button
                onClick={handleSaveMobileDangerZone}
                disabled={dangerPoints.length < 3}
                className="w-full py-2.5 bg-red-600 hover:bg-red-500 disabled:opacity-40 active:scale-95 text-white font-bold text-xs font-mono rounded-lg shadow-lg flex items-center justify-center gap-1.5 transition-all"
              >
                <span className="material-symbols-outlined text-sm">memory</span>
                💾 SAVE TO VISUAL DANGER MEMORY
              </button>
            </div>
          )}
        </div>
      )}

      {/* Center Reticle / Start Button */}
      <div className="relative z-10 flex flex-col items-center justify-center flex-1 p-6">
        {!isStreaming ? (
          <div className="flex flex-col items-center gap-4 bg-black/70 backdrop-blur-md p-6 rounded-2xl border border-white/20 text-center max-w-xs shadow-2xl">
            <div className="w-16 h-16 rounded-full bg-blue-600/30 border border-blue-500 flex items-center justify-center animate-pulse">
              <span className="material-symbols-outlined text-blue-400 text-3xl">videocam</span>
            </div>
            <div>
              <h2 className="text-base font-bold text-white mb-1">Start Camera Broadcast</h2>
              <p className="text-xs text-gray-300">Tap below to grant camera access and stream directly to ONE EYE.</p>
            </div>
            <button
              onClick={() => startCamera('environment')}
              className="w-full py-3 bg-blue-600 hover:bg-blue-500 active:scale-95 text-white font-bold text-sm rounded-xl shadow-lg transition-all flex items-center justify-center gap-2"
            >
              <span className="material-symbols-outlined text-lg">photo_camera</span>
              Enable Camera
            </button>
            <div className="text-[11px] font-mono text-amber-400/90">{statusMsg}</div>
          </div>
        ) : (
          <div className="w-64 h-64 border border-white/20 rounded-2xl relative pointer-events-none">
            <div className="absolute top-0 left-0 w-4 h-4 border-t-2 border-l-2 border-blue-400 -mt-0.5 -ml-0.5" />
            <div className="absolute top-0 right-0 w-4 h-4 border-t-2 border-r-2 border-blue-400 -mt-0.5 -mr-0.5" />
            <div className="absolute bottom-0 left-0 w-4 h-4 border-b-2 border-l-2 border-blue-400 -mb-0.5 -ml-0.5" />
            <div className="absolute bottom-0 right-0 w-4 h-4 border-b-2 border-r-2 border-blue-400 -mb-0.5 -mr-0.5" />
            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-[11px] font-mono text-white/50 bg-black/40 px-2 py-0.5 rounded">
                AI SAFETY SCANNER ACTIVE
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Bottom Controls Bar */}
      <div className="relative z-10 p-5 bg-gradient-to-t from-black/90 via-black/60 to-transparent flex flex-col gap-3">
        <div className="text-center text-xs font-mono text-gray-300">{statusMsg}</div>

        {/* Hardware Camera Sensor Selector Dropdown */}
        {videoDevices.length > 0 && (
          <div className="flex justify-center">
            <select
              value={selectedDeviceId}
              onChange={(e) => startCamera(e.target.value)}
              className="bg-black/70 backdrop-blur text-[11px] font-mono text-cyan-300 border border-cyan-500/40 rounded-lg px-3 py-1.5 outline-none"
            >
              {videoDevices.map((d, idx) => (
                <option key={d.deviceId || idx} value={d.deviceId} className="bg-gray-900 text-white">
                  {d.label || (idx === 0 ? '📷 Primary Rear Camera (Lens 0)' : '🤳 Front Selfie Camera (Lens 1)')}
                </option>
              ))}
            </select>
          </div>
        )}

        <div className="flex items-center justify-around gap-2">
          {/* Direct Lens Switcher: Rear vs Front */}
          <div className="flex bg-white/15 backdrop-blur rounded-xl p-1 border border-white/20">
            <button
              onClick={() => startCamera('environment')}
              className={`px-3 py-2 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition-all ${
                facingMode === 'environment'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-gray-300 hover:text-white'
              }`}
            >
              <span className="material-symbols-outlined text-base">photo_camera</span>
              📷 Rear
            </button>
            <button
              onClick={() => startCamera('user')}
              className={`px-3 py-2 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition-all ${
                facingMode === 'user'
                  ? 'bg-blue-600 text-white shadow-md'
                  : 'text-gray-300 hover:text-white'
              }`}
            >
              <span className="material-symbols-outlined text-base">face</span>
              🤳 Front
            </button>
          </div>

          {/* Quick Flip Cycle */}
          <button
            onClick={toggleCamera}
            className="w-11 h-11 rounded-xl bg-white/15 backdrop-blur border border-white/20 flex items-center justify-center active:scale-95 transition-transform"
            title="Cycle Next Camera Lens"
          >
            <span className="material-symbols-outlined text-white text-xl">flip_camera_android</span>
          </button>

          {/* Resolution Switcher */}
          <div className="flex bg-white/15 backdrop-blur rounded-xl p-1 border border-white/20">
            {(['480p', '720p'] as const).map((r) => (
              <button
                key={r}
                onClick={() => setQuality(r)}
                className={`px-2.5 py-2 rounded-lg text-xs font-mono font-bold transition-all ${
                  quality === r ? 'bg-blue-600 text-white shadow-md' : 'text-gray-300 hover:text-white'
                }`}
              >
                {r}
              </button>
            ))}
          </div>

          {/* Flashlight / Torch */}
          {hasTorch && (
            <button
              onClick={toggleTorch}
              className={`w-11 h-11 rounded-xl backdrop-blur border border-white/20 flex items-center justify-center active:scale-95 transition-transform ${
                isTorchOn ? 'bg-amber-400 text-black shadow-md' : 'bg-white/15 text-white'
              }`}
            >
              <span className="material-symbols-outlined text-xl">
                {isTorchOn ? 'flash_on' : 'flash_off'}
              </span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
