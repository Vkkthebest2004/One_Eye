import React, { useRef, useEffect, useState } from 'react';
import { Maximize2, Minimize2, Eye, ShieldAlert, Layers, Camera as CameraIcon } from 'lucide-react';
import { Camera, Zone, Machine, LiveTrack, LiveDetection } from '@/types';
import { getMediaUrl } from '@/lib/api';

interface LiveCameraGridProps {
  cameras: Camera[];
  zones: Zone[];
  machines: Machine[];
  cameraTracks: Record<string, LiveTrack[]>;
  cameraDetections: Record<string, LiveDetection[]>;
  cameraFps: Record<string, number>;
  onSelectCamera?: (camera: Camera) => void;
}

export const LiveCameraGrid: React.FC<LiveCameraGridProps> = ({
  cameras,
  zones,
  machines,
  cameraTracks,
  cameraDetections,
  cameraFps,
  onSelectCamera,
}) => {
  const [maximizedCamId, setMaximizedCamId] = useState<string | null>(null);
  const [showZones, setShowZones] = useState(true);
  const [showTracks, setShowTracks] = useState(true);
  const [showBBoxes, setShowBBoxes] = useState(true);

  const displayedCameras = maximizedCamId
    ? cameras.filter((c) => c.id === maximizedCamId)
    : cameras;

  return (
    <div className="flex flex-col h-full gap-3">
      {/* Overlay Toggles & Grid Controls */}
      <div className="flex items-center justify-between bg-industrial-900 px-3 py-2 rounded-lg border border-industrial-border">
        <div className="flex items-center gap-2">
          <span className="text-xs font-mono font-semibold text-slate-300 flex items-center gap-1.5">
            <CameraIcon className="w-3.5 h-3.5 text-cyan-400" /> LIVE CAMERA GRID ({cameras.length})
          </span>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <button
            onClick={() => setShowZones(!showZones)}
            className={`px-2 py-1 rounded border font-mono transition ${
              showZones
                ? 'bg-amber-500/20 border-amber-500/50 text-amber-300'
                : 'bg-industrial-800 border-industrial-border text-slate-400'
            }`}
          >
            Zones: {showZones ? 'ON' : 'OFF'}
          </button>

          <button
            onClick={() => setShowTracks(!showTracks)}
            className={`px-2 py-1 rounded border font-mono transition ${
              showTracks
                ? 'bg-cyan-500/20 border-cyan-500/50 text-cyan-300'
                : 'bg-industrial-800 border-industrial-border text-slate-400'
            }`}
          >
            Tracks: {showTracks ? 'ON' : 'OFF'}
          </button>

          <button
            onClick={() => setShowBBoxes(!showBBoxes)}
            className={`px-2 py-1 rounded border font-mono transition ${
              showBBoxes
                ? 'bg-emerald-500/20 border-emerald-500/50 text-emerald-300'
                : 'bg-industrial-800 border-industrial-border text-slate-400'
            }`}
          >
            AI BBoxes: {showBBoxes ? 'ON' : 'OFF'}
          </button>

          {maximizedCamId && (
            <button
              onClick={() => setMaximizedCamId(null)}
              className="flex items-center gap-1 px-2.5 py-1 rounded bg-industrial-700 hover:bg-industrial-600 text-slate-200 border border-slate-500"
            >
              <Minimize2 className="w-3 h-3" /> Show All
            </button>
          )}
        </div>
      </div>

      {/* Cameras Layout */}
      <div
        className={`grid gap-3.5 flex-1 ${
          maximizedCamId
            ? 'grid-cols-1'
            : cameras.length <= 2
            ? 'grid-cols-1 md:grid-cols-2'
            : 'grid-cols-1 md:grid-cols-2'
        }`}
      >
        {displayedCameras.map((camera) => (
          <CameraFeedCard
            key={camera.id}
            camera={camera}
            zones={zones.filter((z) => z.camera_id === camera.id)}
            machines={machines.filter((m) => m.camera_id === camera.id)}
            tracks={cameraTracks[camera.id] || []}
            detections={cameraDetections[camera.id] || []}
            fps={cameraFps[camera.id] || camera.fps || 30.0}
            showZones={showZones}
            showTracks={showTracks}
            showBBoxes={showBBoxes}
            isMaximized={maximizedCamId === camera.id}
            onToggleMaximize={() =>
              setMaximizedCamId(maximizedCamId === camera.id ? null : camera.id)
            }
          />
        ))}
      </div>
    </div>
  );
};

interface CameraFeedCardProps {
  camera: Camera;
  zones: Zone[];
  machines: Machine[];
  tracks: LiveTrack[];
  detections: LiveDetection[];
  fps: number;
  showZones: boolean;
  showTracks: boolean;
  showBBoxes: boolean;
  isMaximized: boolean;
  onToggleMaximize: () => void;
}

const CameraFeedCard: React.FC<CameraFeedCardProps> = ({
  camera,
  zones,
  machines,
  tracks,
  detections,
  fps,
  showZones,
  showTracks,
  showBBoxes,
  isMaximized,
  onToggleMaximize,
}) => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  // Video source resolution
  const videoSrc = getMediaUrl(camera.source);

  // Render Canvas Overlays
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    const scaleX = canvas.width / 1280.0;
    const scaleY = canvas.height / 720.0;

    // 1. Draw Zones
    if (showZones && zones.length > 0) {
      zones.forEach((z) => {
        if (!z.polygon || z.polygon.length < 3) return;
        ctx.beginPath();
        const startX = z.polygon[0][0] * scaleX;
        const startY = z.polygon[0][1] * scaleY;
        ctx.moveTo(startX, startY);

        for (let i = 1; i < z.polygon.length; i++) {
          ctx.lineTo(z.polygon[i][0] * scaleX, z.polygon[i][1] * scaleY);
        }
        ctx.closePath();

        // Shaded interior
        ctx.fillStyle = 'rgba(255, 138, 0, 0.15)';
        ctx.fill();

        // Border
        ctx.strokeStyle = '#ff8a00';
        ctx.lineWidth = 2;
        ctx.setLineDash([6, 4]);
        ctx.stroke();
        ctx.setLineDash([]);

        // Zone Tag
        ctx.fillStyle = '#ff8a00';
        ctx.font = 'bold 11px monospace';
        ctx.fillText(`ZONE: ${z.name.toUpperCase()}`, startX + 8, startY + 18);
      });
    }

    // 2. Draw Machines & Danger Circles
    if (showZones && machines.length > 0) {
      machines.forEach((m) => {
        if (!m.geometry || m.geometry.length < 4) return;
        const [mx, my, mw, mh] = m.geometry;
        const cx = (mx + mw / 2) * scaleX;
        const cy = (my + mh / 2) * scaleY;

        ctx.strokeStyle = '#00e5a3';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(mx * scaleX, my * scaleY, mw * scaleX, mh * scaleY);

        // Machine Tag
        ctx.fillStyle = '#00e5a3';
        ctx.font = '10px monospace';
        ctx.fillText(m.name, mx * scaleX + 4, my * scaleY - 4);
      });
    }

    // 3. Draw Active Worker Tracks & Bounding Boxes
    if (showBBoxes) {
      tracks.forEach((trk) => {
        if (!trk.bbox || trk.bbox.length < 4) return;
        const [bx1, by1, bx2, by2] = trk.bbox;
        const x1 = bx1 * scaleX;
        const y1 = by1 * scaleY;
        const w = (bx2 - bx1) * scaleX;
        const h = (by2 - by1) * scaleY;

        // Determine color based on risk / status
        const isCritical = trk.current_risk_score >= 80 || trk.is_fallen;
        const isHigh = trk.current_risk_score >= 60;
        const isMedium = trk.current_risk_score >= 30;

        const mainColor = isCritical ? '#ff334b' : isHigh ? '#ff8a00' : isMedium ? '#ffcc00' : '#00e5a3';

        // Draw Bounding Box
        ctx.strokeStyle = mainColor;
        ctx.lineWidth = 2.5;
        ctx.strokeRect(x1, y1, w, h);

        // Corner accents
        const cornerSize = 8;
        ctx.lineWidth = 3.5;
        ctx.beginPath();
        ctx.moveTo(x1, y1 + cornerSize); ctx.lineTo(x1, y1); ctx.lineTo(x1 + cornerSize, y1);
        ctx.moveTo(x1 + w - cornerSize, y1); ctx.lineTo(x1 + w, y1); ctx.lineTo(x1 + w, y1 + cornerSize);
        ctx.moveTo(x1, y1 + h - cornerSize); ctx.lineTo(x1, y1 + h); ctx.lineTo(x1 + cornerSize, y1 + h);
        ctx.moveTo(x1 + w - cornerSize, y1 + h); ctx.lineTo(x1 + w, y1 + h); ctx.lineTo(x1 + w, y1 + h - cornerSize);
        ctx.stroke();

        // Draw Worker Header Pill
        const headerText = `${trk.label} | RISK ${trk.current_risk_score}`;
        ctx.font = 'bold 11px monospace';
        const textWidth = ctx.measureText(headerText).width;

        ctx.fillStyle = mainColor;
        ctx.fillRect(x1, Math.max(16, y1 - 18), textWidth + 12, 18);

        ctx.fillStyle = '#000000';
        ctx.fillText(headerText, x1 + 6, Math.max(16, y1 - 5));

        // Draw PPE / Status pills below
        let badgeY = y1 + h + 14;
        if (trk.has_helmet === false) {
          ctx.fillStyle = '#ff334b';
          ctx.fillRect(x1, badgeY - 10, 85, 14);
          ctx.fillStyle = '#ffffff';
          ctx.font = 'bold 9px monospace';
          ctx.fillText('NO HELMET', x1 + 4, badgeY);
          badgeY += 16;
        }

        if (trk.closest_machine_distance_m !== null && trk.closest_machine_distance_m !== undefined) {
          const distColor = trk.closest_machine_distance_m < 1.5 ? '#ff334b' : '#00e5a3';
          ctx.fillStyle = 'rgba(0,0,0,0.7)';
          ctx.fillRect(x1, badgeY - 10, 85, 14);
          ctx.fillStyle = distColor;
          ctx.font = 'bold 9px monospace';
          ctx.fillText(`DIST: ${trk.closest_machine_distance_m}m`, x1 + 4, badgeY);
        }

        // Draw foot contact point
        ctx.beginPath();
        ctx.arc(trk.foot_anchor[0] * scaleX, trk.foot_anchor[1] * scaleY, 4, 0, Math.PI * 2);
        ctx.fillStyle = mainColor;
        ctx.fill();

        // Draw trajectory trail
        if (showTracks && trk.trajectory && trk.trajectory.length > 1) {
          ctx.beginPath();
          ctx.moveTo(trk.trajectory[0][0] * scaleX, trk.trajectory[0][1] * scaleY);
          for (let p = 1; p < trk.trajectory.length; p++) {
            ctx.lineTo(trk.trajectory[p][0] * scaleX, trk.trajectory[p][1] * scaleY);
          }
          ctx.strokeStyle = `${mainColor}66`; // 40% alpha
          ctx.lineWidth = 1.5;
          ctx.stroke();
        }
      });
    }
  }, [tracks, detections, zones, machines, showZones, showTracks, showBBoxes, camera]);

  const hasCritical = tracks.some((t) => t.current_risk_score >= 80 || t.is_fallen);

  return (
    <div
      className={`relative flex flex-col bg-industrial-900 rounded-xl overflow-hidden border transition-all duration-300 ${
        hasCritical
          ? 'border-hazard-critical shadow-lg glow-critical ring-1 ring-hazard-critical/50'
          : 'border-industrial-border hover:border-slate-600'
      } ${isMaximized ? 'h-[75vh]' : 'h-[360px]'}`}
    >
      {/* Top Feed Header Bar */}
      <div className="absolute top-0 left-0 right-0 z-20 flex items-center justify-between px-3 py-2 bg-gradient-to-b from-black/85 via-black/50 to-transparent pointer-events-none">
        <div className="flex items-center gap-2 pointer-events-auto">
          <span className="px-2 py-0.5 rounded bg-industrial-950/80 border border-slate-700 text-cyan-400 font-mono font-bold text-xs">
            {camera.id}
          </span>
          <span className="text-xs font-semibold text-slate-200 truncate max-w-[200px]">
            {camera.name}
          </span>
          {camera.is_calibrated && (
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-emerald-500/20 text-emerald-300 border border-emerald-500/40">
              METRIC CALIBRATED
            </span>
          )}
        </div>

        <div className="flex items-center gap-2 pointer-events-auto">
          <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-black/70 border border-slate-700 text-[11px] font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
            <span className="text-slate-300">{Math.round(fps)} FPS</span>
          </div>

          <button
            onClick={onToggleMaximize}
            className="p-1 rounded bg-black/70 border border-slate-700 text-slate-300 hover:text-white hover:bg-industrial-700"
            title={isMaximized ? 'Restore View' : 'Maximize Feed'}
          >
            {isMaximized ? <Minimize2 className="w-3.5 h-3.5" /> : <Maximize2 className="w-3.5 h-3.5" />}
          </button>
        </div>
      </div>

      {/* Video Stream + HTML5 Canvas Overlay */}
      <div className="relative flex-1 bg-black flex items-center justify-center overflow-hidden">
        <video
          ref={videoRef}
          src={videoSrc}
          autoPlay
          loop
          muted
          playsInline
          className="absolute inset-0 w-full h-full object-fill"
        />

        <canvas
          ref={canvasRef}
          width={1280}
          height={720}
          className="absolute inset-0 w-full h-full pointer-events-none object-fill z-10"
        />

        {/* Scanline CRT overlay effect */}
        <div className="absolute inset-0 bg-gradient-to-b from-transparent via-cyan-500/[0.02] to-transparent pointer-events-none animate-scanline" />
      </div>

      {/* Bottom Telemetry Strip */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-industrial-950 border-t border-industrial-border/60 text-[11px] font-mono text-slate-400">
        <div className="flex items-center gap-3">
          <span>Active Tracks: <strong className="text-slate-200">{tracks.length}</strong></span>
          <span>Zones: <strong className="text-slate-200">{zones.length}</strong></span>
        </div>
        <div className="flex items-center gap-2">
          {hasCritical ? (
            <span className="text-hazard-critical font-bold flex items-center gap-1 animate-pulse">
              <ShieldAlert className="w-3 h-3" /> CRITICAL BREACH
            </span>
          ) : (
            <span className="text-emerald-400 font-semibold">STATUS: NOMINAL</span>
          )}
        </div>
      </div>
    </div>
  );
};
