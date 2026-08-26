import React, { useRef, useEffect, useState } from 'react';
import { Camera, LiveTrack, LiveDetection, Zone, Machine } from '@/types';
import { getMediaUrl } from '@/lib/api';

interface MonitoringArrayProps {
  cameras: Camera[];
  zones: Zone[];
  machines: Machine[];
  cameraTracks: Record<string, LiveTrack[]>;
  cameraDetections: Record<string, LiveDetection[]>;
  cameraFps: Record<string, number>;
  onSelectCamera?: (cam: Camera) => void;
}

export const MonitoringArray: React.FC<MonitoringArrayProps> = ({
  cameras,
  zones,
  machines,
  cameraTracks,
  cameraDetections,
  cameraFps,
  onSelectCamera,
}) => {
  const canvasRefs = useRef<Record<string, HTMLCanvasElement | null>>({});

  // Render synchronized high-fidelity Computer Vision overlays on each camera feed
  useEffect(() => {
    cameras.forEach((cam) => {
      const canvas = canvasRefs.current[cam.id];
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // 1. Draw Restricted Safety Zones (Polygonal Boundaries & Danger Heatmap)
      const camZones = zones.filter((z) => z.camera_id === cam.id);
      camZones.forEach((z) => {
        const poly = z.polygon || [];
        if (!poly || poly.length < 3) return;
        ctx.save();
        ctx.beginPath();
        poly.forEach(([px, py], i) => {
          const x = px * width;
          const y = py * height;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();

        // Glowing semi-transparent zone fill
        ctx.fillStyle = 'rgba(220, 38, 38, 0.12)';
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = '#dc2626';
        ctx.setLineDash([6, 4]);
        ctx.stroke();

        // Zone Tag Banner
        const [firstX, firstY] = poly[0];
        const tagText = `⚠️ RESTRICTED: ${z.name.toUpperCase()}`;
        ctx.font = 'bold 9px "Geist Mono", monospace';
        const tagW = ctx.measureText(tagText).width + 8;
        ctx.fillStyle = '#dc2626';
        ctx.fillRect(firstX * width, Math.max(0, firstY * height - 14), tagW, 14);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(tagText, firstX * width + 4, Math.max(10, firstY * height - 3));
        ctx.restore();
      });

      // 2. Draw Live Worker Tracks & Computer Vision Detection HUDs
      const tracks = cameraTracks[cam.id] || [];
      tracks.forEach((track: any) => {
        let x = 0, y = 0, w = 0, h = 0;

        // Compute coordinate bounding box (Normalized [0, 1] preferred)
        if (track.norm_bbox && track.norm_bbox.length === 4) {
          const [nx1, ny1, nx2, ny2] = track.norm_bbox;
          x = nx1 * width;
          y = ny1 * height;
          w = Math.max(16, (nx2 - nx1) * width);
          h = Math.max(24, (ny2 - ny1) * height);
        } else if (track.bbox && track.bbox.length === 4) {
          const [bx1, by1, bx2, by2] = track.bbox;
          if (bx1 <= 1.0 && bx2 <= 1.0) {
            x = bx1 * width;
            y = by1 * height;
            w = Math.max(16, (bx2 - bx1) * width);
            h = Math.max(24, (by2 - by1) * height);
          } else {
            // Assume 640x480 or 1280x720 relative frame resolution
            const scaleX = width / ((cam as any).width || 640);
            const scaleY = height / ((cam as any).height || 480);
            x = bx1 * scaleX;
            y = by1 * scaleY;
            w = Math.max(16, (bx2 - bx1) * scaleX);
            h = Math.max(24, (by2 - by1) * scaleY);
          }
        }

        const riskScore = track.current_risk_score ?? 10;
        const isCrit = riskScore >= 70 || track.is_fallen;
        const isWarn = riskScore >= 35 && riskScore < 70;
        const themeColor = isCrit ? '#dc2626' : isWarn ? '#d97706' : '#059669';

        ctx.save();

        // A. Subtle Bounding Box Tint
        ctx.fillStyle = isCrit ? 'rgba(220, 38, 38, 0.08)' : isWarn ? 'rgba(217, 119, 6, 0.06)' : 'rgba(5, 150, 105, 0.05)';
        ctx.fillRect(x, y, w, h);

        // B. Thin Perimeter Box
        ctx.lineWidth = 1.2;
        ctx.strokeStyle = isCrit ? 'rgba(220, 38, 38, 0.6)' : isWarn ? 'rgba(217, 119, 6, 0.5)' : 'rgba(5, 150, 105, 0.5)';
        ctx.strokeRect(x, y, w, h);

        // C. Crisp Industrial Corner Reticle Brackets (L-Corners)
        const cornerLen = Math.min(14, Math.max(6, Math.min(w, h) * 0.25));
        ctx.lineWidth = 2.5;
        ctx.strokeStyle = themeColor;

        // Top-Left
        ctx.beginPath();
        ctx.moveTo(x, y + cornerLen);
        ctx.lineTo(x, y);
        ctx.lineTo(x + cornerLen, y);
        ctx.stroke();

        // Top-Right
        ctx.beginPath();
        ctx.moveTo(x + w - cornerLen, y);
        ctx.lineTo(x + w, y);
        ctx.lineTo(x + w, y + cornerLen);
        ctx.stroke();

        // Bottom-Left
        ctx.beginPath();
        ctx.moveTo(x, y + h - cornerLen);
        ctx.lineTo(x, y + h);
        ctx.lineTo(x + cornerLen, y + h);
        ctx.stroke();

        // Bottom-Right
        ctx.beginPath();
        ctx.moveTo(x + w - cornerLen, y + h);
        ctx.lineTo(x + w, y + h);
        ctx.lineTo(x + w, y + h - cornerLen);
        ctx.stroke();

        // D. Top Floating Telemetry Pill: Worker ID + Risk Score
        const workerId = track.track_id ? track.track_id.toString().padStart(2, '0') : '01';
        const topTag = `Worker #${workerId} [Risk: ${Math.round(riskScore)}]`;
        ctx.font = 'bold 9.5px "Geist Mono", monospace';
        const topTagW = ctx.measureText(topTag).width + 8;
        const tagY = Math.max(15, y - 4);

        ctx.fillStyle = themeColor;
        ctx.fillRect(x, tagY - 13, topTagW, 14);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(topTag, x + 4, tagY - 3);

        // E. Spatial Head ROI & Helmet Badge (Upper 35%)
        const headH = h * 0.35;
        const hasHelmet = track.has_helmet !== false;
        ctx.lineWidth = 1;
        ctx.strokeStyle = hasHelmet ? 'rgba(5, 150, 105, 0.6)' : 'rgba(220, 38, 38, 0.8)';
        ctx.setLineDash([2, 2]);
        ctx.strokeRect(x, y, w, headH);
        ctx.setLineDash([]);

        // PPE Badges below bounding box
        let badgeOffsetY = y + h + 2;
        
        // Helmet Badge
        const helmetText = hasHelmet ? '⛑️ HELMET: OK' : '⚠️ NO HELMET';
        ctx.font = 'bold 8.5px "Geist Mono", monospace';
        const helmetW = ctx.measureText(helmetText).width + 6;
        ctx.fillStyle = hasHelmet ? '#059669' : '#dc2626';
        ctx.fillRect(x, badgeOffsetY, helmetW, 12);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(helmetText, x + 3, badgeOffsetY + 9);

        // Vest Badge
        const hasVest = track.has_vest !== false;
        const vestText = hasVest ? '🦺 VEST: OK' : '⚠️ NO VEST';
        const vestW = ctx.measureText(vestText).width + 6;
        ctx.fillStyle = hasVest ? '#059669' : '#d97706';
        ctx.fillRect(x + helmetW + 2, badgeOffsetY, vestW, 12);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(vestText, x + helmetW + 5, badgeOffsetY + 9);

        // F. Posture / Fall Detection Tag if fallen or crouched
        if (track.is_fallen || track.fall_state === 'FALL_CONFIRMED') {
          badgeOffsetY += 14;
          const fallText = '🚨 WORKER FALL DETECTED';
          const fallW = ctx.measureText(fallText).width + 8;
          ctx.fillStyle = '#dc2626';
          ctx.fillRect(x, badgeOffsetY, fallW, 14);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(fallText, x + 4, badgeOffsetY + 10);
        }

        // G. Ground Contact Foot-Anchor Reticle
        const footX = x + w / 2;
        const footY = y + h;
        ctx.beginPath();
        ctx.arc(footX, footY, 3.5, 0, Math.PI * 2);
        ctx.fillStyle = themeColor;
        ctx.fill();
        ctx.strokeStyle = '#ffffff';
        ctx.lineWidth = 1;
        ctx.stroke();

        ctx.restore();
      });
    });
  }, [cameras, zones, machines, cameraTracks, cameraDetections]);

  const defaultSectors: Record<string, string> = {
    CAM_01: 'SECTOR_A_CORRIDOR',
    CAM_02: 'ASSEMBLY_LINE_B',
    CAM_03: 'HEAVY_MACHINERY_Z1',
    CAM_04: 'LOADING_DOCK_INT',
  };

  const [activeFilter, setActiveFilter] = useState<'all' | 'cctv' | 'mobile'>('all');
  const [allStreamsPaused, setAllStreamsPaused] = useState<boolean>(false);
  const [pausedCameras, setPausedCameras] = useState<Record<string, boolean>>({});

  const toggleCameraPause = (cameraId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setPausedCameras((prev) => ({
      ...prev,
      [cameraId]: !prev[cameraId],
    }));
  };

  const toggleAllStreams = () => {
    const next = !allStreamsPaused;
    setAllStreamsPaused(next);
    const updated: Record<string, boolean> = {};
    cameras.forEach((c) => {
      updated[c.id] = next;
    });
    setPausedCameras(updated);
  };

  // Filter cameras
  const filteredCameras = cameras.filter((cam) => {
    if (activeFilter === 'mobile') return cam.source_type === 'mobile' || cam.source.startsWith('mobile');
    if (activeFilter === 'cctv') return cam.source_type !== 'mobile' && !cam.source.startsWith('mobile');
    return true;
  });

  return (
    <div className="flex flex-col gap-unit h-full w-full">
      {/* Monitoring Header & View Filters */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-2 shrink-0">
        <div className="flex items-center gap-2">
          <h3 className="font-label-mono text-xs font-bold text-on-surface-variant uppercase tracking-widest flex items-center gap-2 font-bold">
            <span className={`w-2 h-2 rounded-full ${allStreamsPaused ? 'bg-amber-500' : 'bg-severity-safe animate-pulse'}`} />
            Live AI Perception Array ({filteredCameras.length} Feeds)
          </h3>
          {cameras.some((c) => c.source_type === 'mobile' || c.source.startsWith('mobile')) && (
            <span className="px-2 py-0.5 rounded bg-blue-600/10 text-blue-600 border border-blue-500/30 text-[10px] font-mono font-bold flex items-center gap-1">
              <span className="material-symbols-outlined text-[12px]">smartphone</span>
              MOBILE CAMERA
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={toggleAllStreams}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-label-mono font-bold shadow-sm transition-all border ${
              allStreamsPaused
                ? 'bg-amber-500/20 text-amber-500 border-amber-500/50 hover:bg-amber-500/30'
                : 'bg-surface border-outline-variant text-on-surface hover:border-amber-500 hover:text-amber-500'
            }`}
            title={allStreamsPaused ? 'Click to Resume All Camera Feeds' : 'Click to Pause / Freeze All Camera Feeds'}
          >
            <span className="material-symbols-outlined text-sm">
              {allStreamsPaused ? 'play_arrow' : 'pause'}
            </span>
            {allStreamsPaused ? 'RESUME ALL' : 'PAUSE ALL'}
          </button>

          <button
            onClick={() => setActiveFilter('all')}
            className={`px-2.5 py-1 rounded text-xs font-label-mono shadow-sm transition-all ${
              activeFilter === 'all'
                ? 'bg-primary text-white font-bold'
                : 'bg-surface border border-outline-variant text-on-surface hover:border-primary'
            }`}
          >
            ALL ({cameras.length})
          </button>
          <button
            onClick={() => setActiveFilter('mobile')}
            className={`px-2.5 py-1 rounded text-xs font-label-mono shadow-sm transition-all ${
              activeFilter === 'mobile'
                ? 'bg-primary text-white font-bold'
                : 'bg-surface border border-outline-variant text-on-surface hover:border-primary'
            }`}
          >
            📱 MOBILE ({cameras.filter((c) => c.source_type === 'mobile' || c.source.startsWith('mobile')).length})
          </button>
          <button
            onClick={() => setActiveFilter('cctv')}
            className={`px-2.5 py-1 rounded text-xs font-label-mono shadow-sm transition-all ${
              activeFilter === 'cctv'
                ? 'bg-primary text-white font-bold'
                : 'bg-surface border border-outline-variant text-on-surface hover:border-primary'
            }`}
          >
            CCTV ({cameras.filter((c) => c.source_type !== 'mobile' && !c.source.startsWith('mobile')).length})
          </button>
        </div>
      </div>

      {/* Grid */}
      {filteredCameras.length === 0 ? (
        <div className="level-1-panel rounded-lg p-10 flex flex-col items-center justify-center text-center gap-3 border border-outline-variant bg-surface min-h-[360px]">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant">videocam_off</span>
          <h4 className="font-label-mono-bold text-sm text-on-surface">No Active Video Feeds</h4>
          <p className="font-label-mono text-xs text-on-surface-variant max-w-md">
            Connect your Android mobile camera via USB or configure RTSP/USB camera streams in the Settings tab.
          </p>
        </div>
      ) : (
        <div className={`grid gap-gutter flex-1 ${filteredCameras.length === 1 ? 'grid-cols-1 max-w-4xl mx-auto w-full' : 'grid-cols-1 md:grid-cols-2'}`}>
          {filteredCameras.map((cam) => {
            const fps = cameraFps[cam.id] || (cam.id === 'CAM_03' ? 24.5 : 29.97);
            const tracks = cameraTracks[cam.id] || [];
            const hasCritical = tracks.some((t: any) => (t.current_risk_score || 0) >= 70 || t.is_fallen);
            const maxRisk = tracks.reduce(
              (max: number, t: any) => Math.max(max, t.current_risk_score || 0),
              hasCritical ? 86 : 12
            );
            const isPaused = allStreamsPaused || !!pausedCameras[cam.id];

            return (
              <div
                key={cam.id}
                onClick={() => onSelectCamera && onSelectCamera(cam)}
                className={`level-1-panel rounded-lg overflow-hidden relative group cursor-pointer aspect-[16/10] flex flex-col justify-between ${
                  hasCritical
                    ? 'border-2 border-severity-critical shadow-[0_0_15px_rgba(220,38,38,0.2)] z-10'
                    : ''
                }`}
              >
                {/* Background Live Video Feed */}
                {!isPaused ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={getMediaUrl(`/api/cameras/${cam.id}/stream`)}
                    alt={cam.name}
                    className={`absolute inset-0 w-full h-full object-cover ${
                      hasCritical ? 'contrast-105' : ''
                    }`}
                    onError={(e) => {
                      const target = e.currentTarget;
                      setTimeout(() => {
                        target.src = getMediaUrl(`/api/cameras/${cam.id}/stream?t=${Date.now()}`);
                      }, 1500);
                    }}
                  />
                ) : (
                  <div className="absolute inset-0 w-full h-full bg-surface-container-highest/90 flex flex-col items-center justify-center gap-2 backdrop-blur-sm z-10">
                    <span className="material-symbols-outlined text-4xl text-amber-500 animate-pulse">
                      pause_circle
                    </span>
                    <span className="font-label-mono text-xs font-bold text-amber-500 uppercase tracking-widest">
                      STREAM PAUSED
                    </span>
                    <button
                      onClick={(e) => toggleCameraPause(cam.id, e)}
                      className="px-3 py-1 bg-amber-500 text-black text-xs font-bold rounded shadow hover:bg-amber-400 transition-all flex items-center gap-1 mt-1 font-bold"
                    >
                      <span className="material-symbols-outlined text-sm">play_arrow</span>
                      Resume Feed
                    </button>
                  </div>
                )}

                {/* Real-Time Computer Vision Overlay Canvas */}
                <canvas
                  ref={(el) => {
                    canvasRefs.current[cam.id] = el;
                  }}
                  width={640}
                  height={400}
                  className="absolute inset-0 w-full h-full pointer-events-none z-10"
                />

                {/* Camera Gradient Overlay & Scan Line */}
                <div className="absolute inset-0 camera-overlay pointer-events-none" />
                <div className={`scan-line ${hasCritical ? 'bg-severity-critical/20' : ''}`} />

                {/* Red Flashing for Critical Camera */}
                {hasCritical && (
                  <div className="absolute inset-0 bg-severity-critical/5 animate-pulse pointer-events-none" />
                )}

                {/* Top Left: Camera ID & Sector */}
                <div className={`absolute top-3 left-3 z-20 backdrop-blur px-2 py-1 rounded flex flex-col shadow-sm ${
                  hasCritical
                    ? 'bg-severity-critical/90 border border-severity-critical text-white'
                    : 'bg-surface/90 border border-outline-variant text-on-surface'
                }`}>
                  <span className="font-label-mono-bold text-xs font-bold">{cam.id}</span>
                  <span className={`font-label-mono text-[10px] ${hasCritical ? 'text-white/90' : 'text-on-surface-variant'}`}>
                    {defaultSectors[cam.id] || cam.name.toUpperCase()}
                  </span>
                </div>

                {/* Top Right: Status Badge */}
                <div className="absolute top-3 right-3 z-20">
                  {hasCritical ? (
                    <div className="bg-severity-critical backdrop-blur px-2.5 py-1 rounded flex items-center gap-1.5 animate-bounce shadow-md">
                      <span className="material-symbols-outlined text-white text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>
                        warning
                      </span>
                      <span className="font-label-mono-bold text-xs text-white tracking-wider font-bold">CRITICAL</span>
                    </div>
                  ) : (
                    <div className="bg-surface/90 backdrop-blur border border-severity-safe px-2 py-1 rounded flex items-center gap-1.5 shadow-sm">
                      <span className="w-1.5 h-1.5 rounded-full bg-severity-safe" />
                      <span className="font-label-mono-bold text-xs text-severity-safe font-bold">SAFE</span>
                    </div>
                  )}
                </div>

                {/* Bottom Left: Risk Score Pill if Elevated */}
                {hasCritical && (
                  <div className="absolute bottom-3 left-3 z-20 bg-surface/90 backdrop-blur border border-severity-critical p-1.5 px-2.5 rounded flex flex-col shadow-sm">
                    <span className="font-label-mono text-[9px] text-severity-critical uppercase font-bold">
                      Risk Score
                    </span>
                    <span className="font-data-metric text-xl font-bold text-severity-critical leading-tight font-bold">
                      {Math.round(maxRisk)}
                    </span>
                  </div>
                )}

                {/* Bottom Right: FPS & Telemetry */}
                <div className="absolute bottom-3 right-3 z-20 flex flex-col items-end gap-1 font-label-mono text-[10px]">
                  <span className={`px-1.5 py-0.5 rounded shadow-sm border ${
                    hasCritical
                      ? 'bg-severity-critical/80 text-white border-severity-critical font-bold'
                      : 'bg-surface/90 text-on-surface border-outline-variant/50 font-bold'
                  }`}>
                    FPS: {fps.toFixed(1)}
                  </span>
                </div>

                {/* Hover Stroke */}
                <div className="absolute inset-0 border-2 border-transparent group-hover:border-primary/50 transition-colors pointer-events-none rounded-lg z-20" />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
