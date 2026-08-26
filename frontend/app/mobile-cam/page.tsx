'use client';

import React, { useEffect, useRef, useState } from 'react';

export default function MobileCamPage() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  const [isStreaming, setIsStreaming] = useState(false);
  const [facingMode, setFacingMode] = useState<'environment' | 'user'>('environment');
  const [fps, setFps] = useState<number>(0);
  const [statusMsg, setStatusMsg] = useState('Initializing mobile camera...');
  const [hasTorch, setHasTorch] = useState(false);
  const [isTorchOn, setIsTorchOn] = useState(false);
  const [quality, setQuality] = useState<'720p' | '1080p' | '480p'>('720p');

  const streamRef = useRef<MediaStream | null>(null);
  const frameCountRef = useRef(0);
  const lastFpsUpdateRef = useRef(Date.now());

  // Start Camera Stream
  const startCamera = async (mode: 'environment' | 'user') => {
    try {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }

      const resConstraints =
        quality === '1080p'
          ? { width: { ideal: 1920 }, height: { ideal: 1080 } }
          : quality === '720p'
          ? { width: { ideal: 1280 }, height: { ideal: 720 } }
          : { width: { ideal: 640 }, height: { ideal: 480 } };

      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: mode,
          ...resConstraints,
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }

      // Check for torch capability
      const track = stream.getVideoTracks()[0];
      const capabilities: any = track.getCapabilities ? track.getCapabilities() : {};
      setHasTorch(!!capabilities.torch);

      setStatusMsg('Camera connected. Connecting to ONE EYE AI pipeline...');
      connectWebSocket();
    } catch (err: any) {
      console.error('Camera access error:', err);
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
      const configuredWs = process.env.NEXT_PUBLIC_WS_URL;
      const wsBase = configuredWs
        ? configuredWs.replace(/\/ws(?:\/events)?$/, '')
        : `ws://${window.location.hostname || 'localhost'}:8001`;
      const wsUrl = `${wsBase}/api/mobile/ws/stream/CAM_MOBILE`;

      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';

      ws.onopen = () => {
        setIsStreaming(true);
        setStatusMsg('STREAMING LIVE TO ONE EYE SAFETY ENGINE');
        acquireWakeLock();
      };

      ws.onclose = () => {
        setIsStreaming(false);
        setStatusMsg('Stream disconnected. Auto-reconnecting...');
        setTimeout(connectWebSocket, 1000);
      };

      ws.onerror = () => {
        setIsStreaming(false);
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

  // Initial startup
  useEffect(() => {
    startCamera(facingMode);
    return () => {
      if (streamRef.current) {
        streamRef.current.getTracks().forEach((t) => t.stop());
      }
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [facingMode, quality]);

  const toggleCamera = () => {
    setFacingMode((prev) => (prev === 'environment' ? 'user' : 'environment'));
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

        {/* Live Status Badge */}
        <div className="flex items-center gap-2">
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
            {isStreaming ? `${fps} FPS LIVE` : 'CONNECTING'}
          </div>
        </div>
      </div>

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
              onClick={() => startCamera(facingMode)}
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

        <div className="flex items-center justify-around">
          {/* Flip Camera */}
          <button
            onClick={toggleCamera}
            className="w-12 h-12 rounded-full bg-white/10 backdrop-blur border border-white/20 flex items-center justify-center active:scale-95 transition-transform"
          >
            <span className="material-symbols-outlined text-white text-2xl">flip_camera_android</span>
          </button>

          {/* Resolution Switcher */}
          <div className="flex bg-white/10 backdrop-blur rounded-lg p-1 border border-white/20">
            {(['480p', '720p', '1080p'] as const).map((r) => (
              <button
                key={r}
                onClick={() => setQuality(r)}
                className={`px-2.5 py-1 rounded text-xs font-mono font-bold transition-all ${
                  quality === r ? 'bg-blue-600 text-white' : 'text-gray-300 hover:text-white'
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
              className={`w-12 h-12 rounded-full backdrop-blur border border-white/20 flex items-center justify-center active:scale-95 transition-transform ${
                isTorchOn ? 'bg-amber-400 text-black' : 'bg-white/10 text-white'
              }`}
            >
              <span className="material-symbols-outlined text-2xl">
                {isTorchOn ? 'flash_on' : 'flash_off'}
              </span>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
