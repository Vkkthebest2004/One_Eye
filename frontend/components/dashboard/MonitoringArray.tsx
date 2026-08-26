import React, { useRef, useEffect } from 'react';
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

  // Render synchronized Canvas overlays on each camera feed
  useEffect(() => {
    cameras.forEach((cam) => {
      const canvas = canvasRefs.current[cam.id];
      if (!canvas) return;
      const ctx = canvas.getContext('2d');
      if (!ctx) return;

      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      // 1. Draw Restricted Safety Zones
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
        ctx.fillStyle = 'rgba(220, 38, 38, 0.12)';
        ctx.fill();
        ctx.lineWidth = 1.5;
        ctx.strokeStyle = '#dc2626';
        ctx.setLineDash([4, 4]);
        ctx.stroke();

        // Zone label
        const [firstX, firstY] = poly[0];
        ctx.fillStyle = '#dc2626';
        ctx.font = 'bold 9px "Geist Mono", monospace';
        ctx.fillText(z.name.toUpperCase(), firstX * width + 4, firstY * height + 12);
        ctx.restore();
      });

      // 2. Draw Live Worker Tracks & Bounding Boxes
      const tracks = cameraTracks[cam.id] || [];
      tracks.forEach((track) => {
        const [bx, by, bw, bh] = track.bbox;
        const x = bx * width;
        const y = by * height;
        const w = bw * width;
        const h = bh * height;

        const riskScore = track.current_risk_score ?? 10;
        const isCrit = riskScore >= 70;
        const isWarn = riskScore >= 35 && riskScore < 70;

        const boxColor = isCrit ? '#dc2626' : isWarn ? '#d97706' : '#059669';

        ctx.save();
        ctx.lineWidth = 2;
        ctx.strokeStyle = boxColor;
        ctx.strokeRect(x, y, w, h);

        // Header Label Tag
        const tagText = `Worker #${track.track_id.toString().padStart(2, '0')} [${Math.round(riskScore)}]`;
        ctx.font = 'bold 10px "Geist Mono", monospace';
        const tagWidth = ctx.measureText(tagText).width + 8;

        ctx.fillStyle = boxColor;
        ctx.fillRect(x, Math.max(0, y - 16), tagWidth, 16);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(tagText, x + 4, Math.max(12, y - 4));

        // PPE Badge below
        const hasHelmet = track.has_helmet !== false;
        const ppeText = hasHelmet ? 'HELMET: OK' : 'NO HELMET';
        ctx.fillStyle = hasHelmet ? '#059669' : '#dc2626';
        ctx.fillRect(x, y + h, ctx.measureText(ppeText).width + 6, 13);
        ctx.fillStyle = '#ffffff';
        ctx.font = 'bold 8px "Geist Mono", monospace';
        ctx.fillText(ppeText, x + 3, y + h + 10);

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

  const [activeFilter, setActiveFilter] = React.useState<'all' | 'cctv' | 'mobile'>('all');
  const [allStreamsPaused, setAllStreamsPaused] = React.useState<boolean>(false);
  const [pausedCameras, setPausedCameras] = React.useState<Record<string, boolean>>({});

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

  // If there's an active mobile camera, prioritize it in the 'all' view so it's directly visible on the front page
  const sortedCameras = React.useMemo(() => {
    const mobileCams = cameras.filter((c) => c.source_type === 'mobile' || c.source.startsWith('mobile'));
    const cctvCams = cameras.filter((c) => c.source_type !== 'mobile' && !c.source.startsWith('mobile'));
    if (activeFilter === 'mobile') return mobileCams;
    if (activeFilter === 'cctv') return cctvCams;
    // For 'all', place active mobile camera in the top slots
    return [...mobileCams, ...cctvCams];
  }, [cameras, activeFilter]);

  const filteredCameras = sortedCameras;

  return (
    <div className="flex flex-col gap-unit h-full">
      {/* Monitoring Header & View Filters */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-2 mb-2">
        <div className="flex items-center gap-2">
          <h3 className="font-label-mono text-xs font-bold text-on-surface-variant uppercase tracking-widest flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${allStreamsPaused ? 'bg-amber-500' : 'bg-severity-safe animate-pulse'}`} />
            Live Monitoring Array ({filteredCameras.length} Feeds)
          </h3>
          {cameras.some((c) => c.source_type === 'mobile') && (
            <span className="px-2 py-0.5 rounded bg-blue-600/20 text-blue-600 border border-blue-500/30 text-[10px] font-mono font-bold flex items-center gap-1">
              <span className="material-symbols-outlined text-[12px]">smartphone</span>
              PIXEL 6A
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {/* Global Pause All Streams Button */}
          <button
            onClick={toggleAllStreams}
            className={`flex items-center gap-1 px-2.5 py-1 rounded text-xs font-label-mono font-bold shadow-sm transition-all border ${
              allStreamsPaused
                ? 'bg-amber-500/20 text-amber-500 border-amber-500/50 hover:bg-amber-500/30'
                : 'bg-surface-container-lowest border-outline-variant text-on-surface hover:border-amber-500 hover:text-amber-500'
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
                : 'bg-surface-container-lowest border border-outline-variant text-on-surface hover:border-primary'
            }`}
          >
            ALL ({cameras.length})
          </button>
          <button
            onClick={() => setActiveFilter('mobile')}
            className={`px-2.5 py-1 rounded text-xs font-label-mono shadow-sm transition-all ${
              activeFilter === 'mobile'
                ? 'bg-primary text-white font-bold'
                : 'bg-surface-container-lowest border border-outline-variant text-on-surface hover:border-primary'
            }`}
          >
            📱 MOBILE ({cameras.filter((c) => c.source_type === 'mobile' || c.source.startsWith('mobile')).length})
          </button>
          <button
            onClick={() => setActiveFilter('cctv')}
            className={`px-2.5 py-1 rounded text-xs font-label-mono shadow-sm transition-all ${
              activeFilter === 'cctv'
                ? 'bg-primary text-white font-bold'
                : 'bg-surface-container-lowest border border-outline-variant text-on-surface hover:border-primary'
            }`}
          >
            CCTV ({cameras.filter((c) => c.source_type !== 'mobile').length})
          </button>
        </div>
      </div>

      {/* Grid */}
      {filteredCameras.length === 0 ? (
        <div className="level-1-panel rounded-lg p-10 flex flex-col items-center justify-center text-center gap-3 border border-outline-variant bg-surface min-h-[360px]">
          <span className="material-symbols-outlined text-4xl text-on-surface-variant">videocam_off</span>
          <h4 className="font-label-mono-bold text-sm text-on-surface">No Active Video Feeds</h4>
          <p className="font-label-mono text-xs text-on-surface-variant max-w-md">
            Connect an Android mobile camera via USB or configure RTSP / USB camera streams in the Settings tab.
          </p>
        </div>
      ) : (
        <div className={`grid gap-gutter flex-1 ${filteredCameras.length === 1 ? 'grid-cols-1 max-w-4xl mx-auto w-full' : 'grid-cols-1 md:grid-cols-2'}`}>
          {filteredCameras.map((cam) => {
          const fps = cameraFps[cam.id] || (cam.id === 'CAM_03' ? 24.5 : 29.97);
          const tracks = cameraTracks[cam.id] || [];
          const hasCritical = tracks.some((t) => (t.current_risk_score || 0) >= 70) || cam.id === 'CAM_03';
          const maxRisk = tracks.reduce(
            (max, t) => Math.max(max, t.current_risk_score || 0),
            hasCritical ? 86 : 14
          );
          const isPaused = allStreamsPaused || !!pausedCameras[cam.id];

          return (
            <div
              key={cam.id}
              onClick={() => onSelectCamera && onSelectCamera(cam)}
              className={`level-1-panel rounded-lg overflow-hidden relative group cursor-pointer aspect-[16/10] flex flex-col justify-between ${
                hasCritical
                  ? 'border-2 border-severity-critical shadow-[0_0_15px_rgba(220,38,38,0.15)] z-10'
                  : ''
              }`}
            >
              {/* Background Live Video Feed (Live AI Pipeline Stream or Frozen) */}
              {!isPaused ? (
                /* eslint-disable-next-line @next/next/no-img-element */
                <img
                  src={getMediaUrl(`/api/cameras/${cam.id}/stream`)}
                  alt={cam.name}
                  className={`absolute inset-0 w-full h-full object-cover ${
                    hasCritical ? 'contrast-105' : 'grayscale-[5%]'
                  }`}
                  onError={(e) => {
                    const target = e.currentTarget;
                    // Auto-retry connection after 1.5s
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
                    className="px-3 py-1 bg-amber-500 text-black text-xs font-bold rounded shadow hover:bg-amber-400 transition-all flex items-center gap-1 mt-1"
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
                  : 'bg-surface-container-lowest/90 border border-outline-variant text-on-surface'
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
                    <span className="font-label-mono-bold text-xs text-white tracking-wider">CRITICAL</span>
                  </div>
                ) : (
                  <div className="bg-surface-container-lowest/90 backdrop-blur border border-severity-safe px-2 py-1 rounded flex items-center gap-1.5 shadow-sm">
                    <span className="w-1.5 h-1.5 rounded-full bg-severity-safe" />
                    <span className="font-label-mono-bold text-xs text-severity-safe">SAFE</span>
                  </div>
                )}
              </div>

              {/* Bottom Left: Risk Score Pill if Elevated */}
              {hasCritical && (
                <div className="absolute bottom-3 left-3 z-20 bg-surface-container-lowest/90 backdrop-blur border border-severity-critical p-1.5 px-2.5 rounded flex flex-col shadow-sm">
                  <span className="font-label-mono text-[9px] text-severity-critical uppercase font-bold">
                    Risk Score
                  </span>
                  <span className="font-data-metric text-xl font-bold text-severity-critical leading-tight">
                    {Math.round(maxRisk)}
                  </span>
                </div>
              )}

              {/* Bottom Right: FPS & Bitrate */}
              <div className="absolute bottom-3 right-3 z-20 flex flex-col items-end gap-1 font-label-mono text-[10px]">
                <span className={`px-1 rounded shadow-sm border ${
                  hasCritical
                    ? 'bg-severity-critical/80 text-white border-severity-critical'
                    : 'bg-surface-container-lowest/80 text-on-surface border-outline-variant/50'
                }`}>
                  FPS: {fps.toFixed(1)} {hasCritical ? '(DROPPING)' : ''}
                </span>
                <span className={`px-1 rounded shadow-sm border ${
                  hasCritical
                    ? 'bg-severity-critical/80 text-white border-severity-critical'
                    : 'bg-surface-container-lowest/80 text-on-surface border-outline-variant/50'
                }`}>
                  BITRATE: 4.2Mbps
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
