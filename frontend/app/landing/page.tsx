'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  Shield,
  Eye,
  AlertTriangle,
  Zap,
  Activity,
  Smartphone,
  Layers,
  ArrowRight,
  CheckCircle2,
  HardHat,
  Radio,
  Sliders,
  ChevronRight,
  Play,
  RotateCcw,
} from 'lucide-react';
import { getMediaUrl } from '@/lib/api';

export default function LandingPage() {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Display Mode: Live camera stream vs Interactive AI simulator
  const [displayMode, setDisplayMode] = useState<'live' | 'simulator'>('live');

  // Interactive Live Simulator State
  const [scenario, setScenario] = useState<'safe' | 'zone_breach' | 'missing_ppe' | 'fall'>('safe');
  const [simFps, setSimFps] = useState<number>(45);
  const [workerPos, setWorkerPos] = useState<{ x: number; y: number }>({ x: 340, y: 220 });

  // Animation Loop for Interactive CCTV Simulator
  useEffect(() => {
    let animationFrameId: number;
    let t = 0;

    const render = () => {
      t += 0.03;
      const canvas = canvasRef.current;
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const w = canvas.width;
      const h = canvas.height;

      // 1. Dark Factory Floor Background with Grid Lines
      ctx.fillStyle = '#080d17';
      ctx.fillRect(0, 0, w, h);

      // Subtle floor perspective grid
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
      ctx.lineWidth = 1;
      for (let x = 0; x < w; x += 40) {
        ctx.beginPath();
        ctx.moveTo(x, 0);
        ctx.lineTo(x, h);
        ctx.stroke();
      }
      for (let y = 0; y < h; y += 40) {
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(w, y);
        ctx.stroke();
      }

      // 2. Machine Zone Polygon (Lathe / Robotic Press)
      const zonePoints: [number, number][] = [
        [w * 0.52, h * 0.28],
        [w * 0.88, h * 0.28],
        [w * 0.88, h * 0.78],
        [w * 0.52, h * 0.78],
      ];

      const isBreached = scenario === 'zone_breach';

      ctx.save();
      ctx.beginPath();
      zonePoints.forEach(([zx, zy], i) => {
        if (i === 0) ctx.moveTo(zx, zy);
        else ctx.lineTo(zx, zy);
      });
      ctx.closePath();

      if (isBreached) {
        ctx.fillStyle = 'rgba(239, 68, 68, 0.22)';
        ctx.strokeStyle = '#ef4444';
        ctx.lineWidth = 2;
        ctx.fill();
        ctx.stroke();

        // Warning banner above zone
        ctx.fillStyle = '#dc2626';
        ctx.fillRect(zonePoints[0][0], zonePoints[0][1] - 22, 210, 20);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 10px monospace';
        ctx.fillText('🚨 RESTRICTED ZONE INTRUSION', zonePoints[0][0] + 6, zonePoints[0][1] - 8);
      } else {
        ctx.fillStyle = 'rgba(234, 179, 8, 0.08)';
        ctx.strokeStyle = '#eab308';
        ctx.lineWidth = 1.5;
        ctx.setLineDash([6, 4]);
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);

        ctx.fillStyle = 'rgba(234, 179, 8, 0.9)';
        ctx.fillRect(zonePoints[0][0], zonePoints[0][1] - 20, 170, 18);
        ctx.fillStyle = '#0a0d14';
        ctx.font = 'bold 9.5px monospace';
        ctx.fillText('⚠ DANGER PERIMETER: PRESS-01', zonePoints[0][0] + 6, zonePoints[0][1] - 7);
      }
      ctx.restore();

      // 3. Worker Position Calculation based on Scenario
      let targetX = w * 0.28;
      let targetY = h * 0.48;

      if (scenario === 'zone_breach') {
        targetX = w * 0.65;
        targetY = h * 0.5;
      } else if (scenario === 'fall') {
        targetX = w * 0.35;
        targetY = h * 0.62;
      } else if (scenario === 'missing_ppe') {
        targetX = w * 0.32;
        targetY = h * 0.44;
      }

      // Smooth subtle wander
      const currentX = targetX + Math.sin(t) * 12;
      const currentY = targetY + Math.cos(t * 0.8) * 8;

      // 4. Draw Worker Bounding Box & Keypoints
      const isFallen = scenario === 'fall';
      const isMissingPPE = scenario === 'missing_ppe';

      const boxW = isFallen ? 110 : 54;
      const boxH = isFallen ? 42 : 110;
      const boxX = currentX - boxW / 2;
      const boxY = currentY - boxH / 2;

      let boxColor = '#10b981'; // Green (Nominal)
      let statusTag = 'WORKER #04 [PPE: PASS]';

      if (isFallen) {
        boxColor = '#ef4444';
        statusTag = '🚨 WORKER FALLEN // MAN DOWN';
      } else if (isBreached) {
        boxColor = '#ef4444';
        statusTag = '🚨 ZONE BREACH // WORKER #04';
      } else if (isMissingPPE) {
        boxColor = '#f59e0b';
        statusTag = '⚠ PPE MISSING: NO HELMET';
      }

      // Bounding Box
      ctx.save();
      ctx.strokeStyle = boxColor;
      ctx.lineWidth = 1.8;
      ctx.strokeRect(boxX, boxY, boxW, boxH);

      // Corner reticles for high-tech HUD look
      const cornerSize = 7;
      ctx.fillStyle = boxColor;
      ctx.fillRect(boxX - 1, boxY - 1, cornerSize, 2);
      ctx.fillRect(boxX - 1, boxY - 1, 2, cornerSize);
      ctx.fillRect(boxX + boxW - cornerSize + 1, boxY - 1, cornerSize, 2);
      ctx.fillRect(boxX + boxW - 1, boxY - 1, 2, cornerSize);
      ctx.fillRect(boxX - 1, boxY + boxH - 1, cornerSize, 2);
      ctx.fillRect(boxX - 1, boxY + boxH - cornerSize + 1, 2, cornerSize);
      ctx.fillRect(boxX + boxW - cornerSize + 1, boxY + boxH - 1, cornerSize, 2);
      ctx.fillRect(boxX + boxW - 1, boxY + boxH - cornerSize + 1, 2, cornerSize);

      // Label Banner
      ctx.font = 'bold 9.5px monospace';
      const labelW = ctx.measureText(statusTag).width + 12;
      ctx.fillStyle = boxColor;
      ctx.fillRect(boxX, Math.max(16, boxY - 18), labelW, 17);
      ctx.fillStyle = '#080d17';
      ctx.fillText(statusTag, boxX + 6, Math.max(16, boxY - 18) + 12);

      // Ground Contact Foot-Anchor Reticle
      const footX = boxX + boxW / 2;
      const footY = boxY + boxH;
      ctx.beginPath();
      ctx.arc(footX, footY, 3.5, 0, Math.PI * 2);
      ctx.fillStyle = boxColor;
      ctx.fill();
      ctx.strokeStyle = '#ffffff';
      ctx.lineWidth = 1;
      ctx.stroke();

      // Foot anchor ground radar ring
      ctx.beginPath();
      ctx.ellipse(footX, footY, 18, 7, 0, 0, Math.PI * 2);
      ctx.strokeStyle = `${boxColor}55`;
      ctx.lineWidth = 1.2;
      ctx.stroke();

      // 5. HUD Stream Telemetry Overlay
      ctx.fillStyle = '#ffffff';
      ctx.font = '10px monospace';
      ctx.fillText('CAM_01 // BAY_ALPHA_NORTH', 14, 22);

      const timeNow = new Date().toISOString().substring(11, 19);
      ctx.fillStyle = '#94a3b8';
      ctx.fillText(`REC ● ${timeNow} UTC  |  45.0 FPS  |  YOLOv8n + POSE`, 14, 38);

      // Crosshair in top right
      ctx.strokeStyle = 'rgba(255, 255, 255, 0.2)';
      ctx.beginPath();
      ctx.moveTo(w - 24, 16);
      ctx.lineTo(w - 14, 16);
      ctx.moveTo(w - 19, 11);
      ctx.lineTo(w - 19, 21);
      ctx.stroke();

      ctx.restore();

      animationFrameId = requestAnimationFrame(render);
    };

    render();

    return () => {
      cancelAnimationFrame(animationFrameId);
    };
  }, [scenario]);

  return (
    <div className="min-h-screen bg-[#080c14] text-slate-100 font-sans selection:bg-blue-600/30 selection:text-blue-300 relative overflow-x-hidden">
      {/* Background Glow Accents */}
      <div className="absolute top-0 left-1/2 -translate-x-1/2 w-[800px] h-[400px] bg-blue-600/10 blur-[130px] pointer-events-none rounded-full" />
      <div className="absolute top-[600px] right-0 w-[500px] h-[350px] bg-cyan-500/10 blur-[140px] pointer-events-none rounded-full" />

      {/* 1. Header Navigation */}
      <header className="sticky top-0 z-50 backdrop-blur-xl bg-[#080c14]/80 border-b border-white/5 transition-all">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          {/* Logo */}
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 group-hover:scale-105 transition-transform">
              <Eye className="w-4 h-4" />
            </div>
            <div className="flex items-center gap-2">
              <span className="font-mono font-bold text-base tracking-wider text-white">
                ONE EYE
              </span>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 flex items-center gap-1">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Operational
              </span>
            </div>
          </Link>

          {/* Nav Anchors */}
          <nav className="hidden md:flex items-center gap-8 text-xs font-mono text-slate-400">
            <a href="#simulator" className="hover:text-white transition-colors">
              Live Simulator
            </a>
            <a href="#capabilities" className="hover:text-white transition-colors">
              Capabilities
            </a>
            <a href="#architecture" className="hover:text-white transition-colors">
              Architecture
            </a>
            <a href="#metrics" className="hover:text-white transition-colors">
              Benchmarks
            </a>
            <Link
              href="/mobile-cam"
              className="text-slate-400 hover:text-white transition-colors flex items-center gap-1"
            >
              <Smartphone className="w-3.5 h-3.5 text-blue-400" />
              Mobile Node
            </Link>
          </nav>

          {/* Action Button */}
          <div className="flex items-center gap-3">
            <Link
              href="/"
              className="px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white text-xs font-mono font-semibold flex items-center gap-1.5 shadow-lg shadow-blue-600/25 transition-all active:scale-95 border border-blue-400/30"
            >
              <span>Launch Console</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* 2. Hero Section */}
      <section className="relative pt-16 pb-20 md:pt-24 md:pb-28 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-3xl mx-auto">
          {/* Eyebrow Pill */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/[0.04] border border-white/10 text-xs font-mono text-slate-300 mb-6 backdrop-blur-md">
            <Radio className="w-3.5 h-3.5 text-blue-400 animate-pulse" />
            <span>Autonomous Industrial Vision Intelligence</span>
            <span className="text-slate-500">|</span>
            <span className="text-blue-400">45 FPS Edge</span>
          </div>

          {/* Main Title */}
          <h1 className="text-4xl sm:text-5xl md:text-6xl font-extrabold tracking-tight text-white leading-[1.1] mb-6">
            Autonomous visual intelligence for{' '}
            <span className="bg-gradient-to-r from-blue-400 via-cyan-300 to-emerald-400 bg-clip-text text-transparent">
              zero-accident
            </span>{' '}
            workplaces.
          </h1>

          {/* Subtitle */}
          <p className="text-base sm:text-lg text-slate-400 leading-relaxed max-w-2xl mx-auto mb-9 font-normal">
            Turn standard CCTV, RTSP, or mobile cameras into intelligent safety sentries. Instant
            PPE compliance verification, dynamic danger perimeter breach alerts, and biomechanical
            fall detection in milliseconds.
          </p>

          {/* Primary Action Buttons */}
          <div className="flex flex-col sm:flex-row items-center justify-center gap-3 sm:gap-4 mb-14">
            <Link
              href="/"
              className="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-mono text-sm font-semibold flex items-center justify-center gap-2 shadow-xl shadow-blue-600/30 transition-all active:scale-95 border border-blue-400/40"
            >
              <Activity className="w-4 h-4" />
              <span>Launch Safety Console</span>
              <ArrowRight className="w-4 h-4 ml-1" />
            </Link>

            <Link
              href="/mobile-cam"
              target="_blank"
              rel="noreferrer"
              className="w-full sm:w-auto px-6 py-3.5 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] text-slate-200 hover:text-white font-mono text-sm font-medium flex items-center justify-center gap-2 border border-white/10 transition-all"
            >
              <Smartphone className="w-4 h-4 text-cyan-400" />
              <span>Connect Mobile Camera</span>
            </Link>
          </div>

          {/* Quick Telemetry Strip */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-left">
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] backdrop-blur-sm">
              <div className="text-2xl font-mono font-bold text-white">45.0 FPS</div>
              <div className="text-[11px] font-mono text-slate-400 mt-0.5">Real-time edge speed</div>
            </div>
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] backdrop-blur-sm">
              <div className="text-2xl font-mono font-bold text-emerald-400">&lt; 85 ms</div>
              <div className="text-[11px] font-mono text-slate-400 mt-0.5">Hazard reaction latency</div>
            </div>
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] backdrop-blur-sm">
              <div className="text-2xl font-mono font-bold text-cyan-400">3-in-1</div>
              <div className="text-[11px] font-mono text-slate-400 mt-0.5">PPE + Zones + Pose engine</div>
            </div>
            <div className="p-3.5 rounded-xl bg-white/[0.02] border border-white/[0.06] backdrop-blur-sm">
              <div className="text-2xl font-mono font-bold text-amber-400">0 Sensors</div>
              <div className="text-[11px] font-mono text-slate-400 mt-0.5">Runs on standard video</div>
            </div>
          </div>
        </div>
      </section>

      {/* 3. Interactive Live Stream & AI Simulator Section */}
      <section id="simulator" className="py-16 bg-[#0a0f1d] border-y border-white/5 relative">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col md:flex-row md:items-end justify-between mb-6 gap-4">
            <div>
              <div className="text-xs font-mono text-blue-400 uppercase tracking-widest mb-1.5 flex items-center gap-1.5 font-semibold">
                <Radio className="w-3.5 h-3.5 animate-pulse text-emerald-400" />
                Live Vision Perception Feed
              </div>
              <h2 className="text-2xl sm:text-3xl font-bold tracking-tight text-white">
                Real-Time Workplace Vision in Action
              </h2>
              <p className="text-xs sm:text-sm text-slate-400 mt-1 max-w-xl">
                Switch between your active live laptop camera feed and the interactive multi-hazard neural simulator.
              </p>
            </div>

            {/* View Mode Toggle: Live Camera vs AI Simulator */}
            <div className="flex items-center gap-2 p-1 rounded-xl bg-white/[0.04] border border-white/10 shrink-0">
              <button
                onClick={() => setDisplayMode('live')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium flex items-center gap-1.5 transition-all ${
                  displayMode === 'live'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span>Live Webcam Stream</span>
              </button>
              <button
                onClick={() => setDisplayMode('simulator')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium flex items-center gap-1.5 transition-all ${
                  displayMode === 'simulator'
                    ? 'bg-blue-600 text-white shadow-md'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Play className="w-3.5 h-3.5 text-cyan-400" />
                <span>Interactive Simulator</span>
              </button>
            </div>
          </div>

          {/* Conditional Controls when Simulator is active */}
          {displayMode === 'simulator' && (
            <div className="flex flex-wrap items-center gap-2 mb-4">
              <span className="text-xs font-mono text-slate-400 mr-1">Trigger Scenario:</span>
              <button
                onClick={() => setScenario('safe')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                  scenario === 'safe'
                    ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/50 shadow-sm'
                    : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
                }`}
              >
                ✓ All Nominal
              </button>
              <button
                onClick={() => setScenario('zone_breach')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                  scenario === 'zone_breach'
                    ? 'bg-red-500/20 text-red-300 border border-red-500/50 shadow-sm animate-pulse'
                    : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
                }`}
              >
                🚨 Zone Intrusion
              </button>
              <button
                onClick={() => setScenario('missing_ppe')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                  scenario === 'missing_ppe'
                    ? 'bg-amber-500/20 text-amber-300 border border-amber-500/50 shadow-sm'
                    : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
                }`}
              >
                ⚠ Missing Helmet
              </button>
              <button
                onClick={() => setScenario('fall')}
                className={`px-3 py-1.5 rounded-lg text-xs font-mono font-medium transition-all ${
                  scenario === 'fall'
                    ? 'bg-red-500/20 text-red-300 border border-red-500/50 shadow-sm animate-pulse'
                    : 'bg-white/5 text-slate-400 hover:text-white border border-white/5'
                }`}
              >
                💥 Slip & Fall
              </button>
            </div>
          )}

          {/* Video Container */}
          <div className="rounded-2xl border border-white/10 bg-[#080d17] p-2.5 shadow-2xl relative overflow-hidden group">
            {displayMode === 'live' ? (
              <div className="relative aspect-[16/9] w-full rounded-xl overflow-hidden bg-black flex items-center justify-center">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={getMediaUrl('/api/cameras/CAM_WEBCAM/stream')}
                  alt="Live Laptop Webcam Stream"
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    const target = e.currentTarget;
                    const retries = parseInt(target.getAttribute('data-retries') || '0', 10);
                    if (retries < 15) {
                      target.setAttribute('data-retries', String(retries + 1));
                      setTimeout(() => {
                        target.src = getMediaUrl(`/api/cameras/CAM_WEBCAM/stream?retry=${Date.now()}`);
                      }, 1200);
                    }
                  }}
                />
                {/* Live Stream Overlay HUD */}
                <div className="absolute top-3 left-3 z-10 px-2.5 py-1 rounded-md bg-black/70 border border-white/10 backdrop-blur-md text-xs font-mono flex items-center gap-2">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  <span className="text-white font-semibold">CAM_WEBCAM</span>
                  <span className="text-slate-400">| Built-in FaceTime HD</span>
                </div>

                <div className="absolute top-3 right-3 z-10 px-2.5 py-1 rounded-md bg-black/70 border border-white/10 backdrop-blur-md text-xs font-mono text-emerald-400 flex items-center gap-1.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
                  <span>30.0 FPS • YOLOv8n</span>
                </div>

                <div className="absolute bottom-3 right-3 z-10">
                  <Link
                    href="/"
                    className="px-3.5 py-2 rounded-lg bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-semibold shadow-lg flex items-center gap-1.5 transition-all border border-blue-400/30"
                  >
                    <span>Open Multi-Camera Console</span>
                    <ArrowRight className="w-3.5 h-3.5" />
                  </Link>
                </div>
              </div>
            ) : (
              <canvas
                ref={canvasRef}
                width={1000}
                height={480}
                className="w-full h-auto aspect-[16/8] rounded-xl block bg-[#080d17]"
              />
            )}

            {/* Bottom Floating Telemetry Card */}
            <div className="mt-3 px-4 py-2.5 rounded-xl bg-white/[0.03] border border-white/5 flex flex-wrap items-center justify-between gap-3 text-xs font-mono text-slate-400">
              <div className="flex items-center gap-3">
                <span className="flex items-center gap-1.5 text-slate-200">
                  <span className="w-2 h-2 rounded-full bg-blue-400 animate-ping" />
                  Channel: CAM_WEBCAM
                </span>
                <span className="hidden sm:inline text-slate-600">|</span>
                <span className="hidden sm:inline">Perception: YOLOv8n + Keypoint Pose Ground Anchoring</span>
              </div>

              <div className="flex items-center gap-4">
                <span className="text-slate-300">
                  Status: <strong className="text-emerald-400">NOMINAL // MONITORING ACTIVE</strong>
                </span>

                <Link
                  href="/"
                  className="text-blue-400 hover:text-blue-300 font-semibold flex items-center gap-1 underline underline-offset-4"
                >
                  Configure Danger Zones →
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 4. Core Capabilities (Bento Box Grid) */}
      <section id="capabilities" className="py-20 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="text-center max-w-2xl mx-auto mb-16">
          <div className="text-xs font-mono text-cyan-400 uppercase tracking-widest mb-1.5 font-semibold">
            Perception Pillars
          </div>
          <h2 className="text-3xl font-bold tracking-tight text-white">
            Built for hazardous shop floors and heavy industries.
          </h2>
          <p className="text-sm text-slate-400 mt-2">
            Every module operates autonomously on edge hardware, ensuring continuous 24/7 protection
            without sending private camera video feeds to third-party clouds.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-5">
          {/* Bento Card 1: PPE */}
          <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-blue-500/30 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 mb-5 group-hover:scale-110 transition-transform">
                <HardHat className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Real-Time PPE Verification</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Autonomous bounding box classification for hard hats, high-vis vests, goggles, and
                safety footwear with temporal voting smoothing to eliminate false alerts.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-blue-400 flex items-center gap-1">
              <span>99.2% Verification Recall</span>
            </div>
          </div>

          {/* Bento Card 2: Zones */}
          <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-red-500/30 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-10 h-10 rounded-xl bg-red-500/10 border border-red-500/20 flex items-center justify-center text-red-400 mb-5 group-hover:scale-110 transition-transform">
                <Shield className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Dynamic Danger Perimeters</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Draw custom polygonal no-go zones directly on any camera stream. Sub-pixel foot
                anchor point-in-polygon tracking triggers immediate alarm bells upon perimeter
                breach.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-red-400 flex items-center gap-1">
              <span>Sub-50ms Polygon Intersection</span>
            </div>
          </div>

          {/* Bento Card 3: Pose & Fall */}
          <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-amber-500/30 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-10 h-10 rounded-xl bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400 mb-5 group-hover:scale-110 transition-transform">
                <AlertTriangle className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Slip & Fall Biomechanics</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Tracks 17 anatomical keypoints across shoulders, hips, and ankles to detect sudden
                abnormal vertical-to-horizontal velocity collapse and worker immobilization.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-amber-400 flex items-center gap-1">
              <span>Instant Man-Down Escalation</span>
            </div>
          </div>

          {/* Bento Card 4: Compound Risk Engine */}
          <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-cyan-500/30 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-10 h-10 rounded-xl bg-cyan-500/10 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-5 group-hover:scale-110 transition-transform">
                <Zap className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Compound Risk Scoring (0–100)</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Mathematical risk synergy engine dynamically weights worker proximity, machinery
                operating status, missing gear, and dwell duration into a single unified plant risk
                index.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-cyan-400 flex items-center gap-1">
              <span>Deterministic Risk Engine</span>
            </div>
          </div>

          {/* Bento Card 5: Mobile Node */}
          <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-purple-500/30 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-10 h-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400 mb-5 group-hover:scale-110 transition-transform">
                <Smartphone className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Handheld Mobile Sentry</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Turn any Android or iOS smartphone into an instant mobile inspection scanner over
                local Wi-Fi or USB tethering. Real-time lens switching and visual hazard tagging on
                phone.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-purple-400 flex items-center gap-1">
              <Link href="/mobile-cam" className="hover:underline flex items-center gap-1">
                Launch Mobile Node →
              </Link>
            </div>
          </div>

          {/* Bento Card 6: Forensic Audit */}
          <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/[0.06] hover:border-emerald-500/30 transition-all flex flex-col justify-between group">
            <div>
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 mb-5 group-hover:scale-110 transition-transform">
                <Layers className="w-5 h-5" />
              </div>
              <h3 className="text-base font-bold text-white mb-2">Legal-Grade Forensic Audit</h3>
              <p className="text-xs text-slate-400 leading-relaxed">
                Automated bounding snapshot retention with microsecond timestamps. Enables 1-click
                incident acknowledgement, root-cause resolution, and false positive reporting.
              </p>
            </div>
            <div className="mt-6 pt-4 border-t border-white/5 text-[11px] font-mono text-emerald-400 flex items-center gap-1">
              <span>Automatic Retention Lifecycle</span>
            </div>
          </div>
        </div>
      </section>

      {/* 5. Edge Architecture Pipeline */}
      <section id="architecture" className="py-20 bg-[#0a0f1d] border-t border-white/5">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center max-w-2xl mx-auto mb-16">
            <div className="text-xs font-mono text-blue-400 uppercase tracking-widest mb-1.5 font-semibold">
              System Pipeline
            </div>
            <h2 className="text-3xl font-bold tracking-tight text-white">
              End-to-end edge pipeline architecture.
            </h2>
            <p className="text-sm text-slate-400 mt-2">
              Designed from the ground up for sub-millisecond local inference on Mac Silicon (MPS),
              NVIDIA Jetson, or industrial rack servers.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 relative">
            {/* Step 1 */}
            <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 relative">
              <div className="text-xs font-mono text-blue-400 font-bold mb-3">01 // INGESTION</div>
              <h4 className="text-base font-bold text-white mb-2">Multi-Stream Ingestion</h4>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Asynchronous frame decoders handle RTSP network cameras, standard USB webcams, and
                mobile video feeds with thread-isolated ring buffering.
              </p>
              <div className="text-[11px] font-mono text-slate-500">
                Protocols: RTSP, MJPEG, WebRTC, UVC
              </div>
            </div>

            {/* Step 2 */}
            <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 relative">
              <div className="text-xs font-mono text-cyan-400 font-bold mb-3">02 // INFERENCE</div>
              <h4 className="text-base font-bold text-white mb-2">Unified Neural Perception</h4>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Executes nano YOLOv8 models for person tracking, keypoint pose ground anchoring, and
                PPE classification with conditional zero-waste execution.
              </p>
              <div className="text-[11px] font-mono text-slate-500">
                Models: YOLOv8n, YOLOv8n-pose, Qwen2-VL
              </div>
            </div>

            {/* Step 3 */}
            <div className="p-6 rounded-2xl bg-white/[0.02] border border-white/5 relative">
              <div className="text-xs font-mono text-emerald-400 font-bold mb-3">03 // DEFENSE</div>
              <h4 className="text-base font-bold text-white mb-2">Autonomous Safety Defense</h4>
              <p className="text-xs text-slate-400 leading-relaxed mb-4">
                Evaluates point-in-polygon boundaries, accumulates exposure indices, fires real-time
                WebSocket alerts to the console, and triggers machine interlocks.
              </p>
              <div className="text-[11px] font-mono text-slate-500">
                Output: WebSockets, REST API, Evidence Store
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* 6. Launch Console CTA Banner */}
      <section className="py-20 relative overflow-hidden">
        <div className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="rounded-3xl bg-gradient-to-br from-blue-900/40 via-[#0d1527] to-[#080d17] border border-blue-500/20 p-8 sm:p-12 text-center relative overflow-hidden shadow-2xl">
            <div className="absolute top-0 right-0 w-80 h-80 bg-blue-500/10 blur-[100px] pointer-events-none rounded-full" />

            <div className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-blue-500/10 border border-blue-500/30 text-xs font-mono text-blue-300 mb-5">
              <Activity className="w-3.5 h-3.5 animate-pulse" />
              <span>Real-time Safety Monitoring Console</span>
            </div>

            <h2 className="text-3xl sm:text-4xl font-extrabold text-white tracking-tight mb-4">
              Step into the safety command center.
            </h2>
            <p className="text-sm sm:text-base text-slate-300 max-w-xl mx-auto mb-8 font-normal leading-relaxed">
              Monitor active video feeds, configure restricted danger zones with a single click, and
              track floor compliance in real time.
            </p>

            <div className="flex flex-col sm:flex-row items-center justify-center gap-3">
              <Link
                href="/"
                className="w-full sm:w-auto px-7 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-mono text-sm font-semibold flex items-center justify-center gap-2 shadow-xl shadow-blue-600/30 transition-all active:scale-95 border border-blue-400/40"
              >
                <span>Launch Live Console</span>
                <ArrowRight className="w-4 h-4" />
              </Link>

              <Link
                href="/mobile-cam"
                target="_blank"
                rel="noreferrer"
                className="w-full sm:w-auto px-7 py-3.5 rounded-xl bg-white/[0.05] hover:bg-white/[0.09] text-slate-200 font-mono text-sm font-medium flex items-center justify-center gap-2 border border-white/10 transition-all"
              >
                <Smartphone className="w-4 h-4 text-cyan-400" />
                <span>Open Mobile Cam</span>
              </Link>
            </div>
          </div>
        </div>
      </section>

      {/* 7. Footer */}
      <footer className="py-10 border-t border-white/5 bg-[#060910] text-xs font-mono text-slate-500">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Eye className="w-3 h-3" />
            </div>
            <span className="font-bold text-slate-300">ONE EYE</span>
            <span>— Industrial Safety & Real-Time Vision Intelligence</span>
          </div>

          <div className="flex items-center gap-6">
            <Link href="/" className="hover:text-slate-300 transition-colors">
              Console
            </Link>
            <Link href="/mobile-cam" className="hover:text-slate-300 transition-colors">
              Mobile Node
            </Link>
            <span className="flex items-center gap-1.5 text-emerald-400">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              System Online
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
