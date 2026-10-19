import React, { useRef, useEffect, useState } from 'react';
import { Camera, LiveTrack, LiveDetection, Zone, Machine } from '@/types';
import { getMediaUrl, useWebcam, useDemoVideo, stopCameraFeed, startCameraFeed, toggleCameraFeed } from '@/lib/api';
import { ZonePolygonEditor } from './ZonePolygonEditor';

interface MonitoringArrayProps {
  cameras: Camera[];
  zones: Zone[];
  machines: Machine[];
  cameraTracks: Record<string, LiveTrack[]>;
  cameraDetections: Record<string, LiveDetection[]>;
  cameraFps: Record<string, number>;
  visualZones?: Record<string, any[]>;
  cameraIntrusions?: Record<string, any[]>;
  onSelectCamera?: (cam: Camera) => void;
  onZonesUpdated?: () => void;
}

export const MonitoringArray: React.FC<MonitoringArrayProps> = ({
  cameras,
  zones,
  machines,
  cameraTracks,
  cameraDetections,
  cameraFps,
  visualZones,
  cameraIntrusions,
  onSelectCamera,
  onZonesUpdated,
}) => {
  const canvasRefs = useRef<Record<string, HTMLCanvasElement | null>>({});
  const [isZoneEditorOpen, setIsZoneEditorOpen] = useState(false);

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

      // 1. Draw Restricted Safety Zones & Visual Homography Anchors
      const dynVisualZones = (visualZones && visualZones[cam.id]) || [];
      const camIntrusions = (cameraIntrusions && cameraIntrusions[cam.id]) || [];
      const camZones = zones.filter((z) => z.camera_id === cam.id || (cam.source_type === 'mobile' && z.camera_id.startsWith('CAM_MOB')));

      camZones.forEach((z) => {
        // Check if dynamic homography tracking is active for this zone
        const tracked = dynVisualZones.find((vz: any) => vz.zone_id === z.id);
        const isMobileCam = cam.source_type === 'mobile' || cam.id.startsWith('CAM_MOB');
        
        if (isMobileCam) {
          // For mobile cameras, ONLY render if the visual anchor is currently recognized in view
          if (!tracked || !tracked.is_visible) {
            return;
          }
        } else if (tracked && !tracked.is_visible) {
          return;
        }

        const poly = (tracked && tracked.polygon && tracked.polygon.length >= 3) ? tracked.polygon : (z.polygon || []);
        if (!poly || poly.length < 3) return;

        // Check if an entity or hand is actively intruding/touching this zone
        const intrusion = camIntrusions.find((it: any) => it.zone_name === z.name || it.zone_id === z.id);
        const isIntruded = !!intrusion;

        ctx.save();
        ctx.beginPath();
        poly.forEach(([px, py]: [number, number], i: number) => {
          const x = px * width;
          const y = py * height;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();

        if (isIntruded) {
          // Intrusion Alert State: Glowing pulsating red
          ctx.fillStyle = 'rgba(239, 68, 68, 0.38)';
          ctx.fill();
          ctx.lineWidth = 2.8;
          ctx.strokeStyle = '#ef4444';
          ctx.setLineDash([]);
          ctx.stroke();

          // Zone Tag Banner
          const [firstX, firstY] = poly[0];
          const tagText = `🚨 Restricted Area Breach: ${z.name}`;
          ctx.font = 'bold 9.5px "Geist Mono", monospace';
          const tagW = ctx.measureText(tagText).width + 10;
          ctx.fillStyle = '#dc2626';
          ctx.fillRect(firstX * width, Math.max(0, firstY * height - 16), tagW, 16);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(tagText, firstX * width + 5, Math.max(11, firstY * height - 4));

          // Draw precision contact points if detected by MediaPipe / Pose
          const contactPoints = intrusion.intrusion_points || intrusion.norm_contact_points || [];
          if (Array.isArray(contactPoints)) {
            contactPoints.forEach(([ix, iy]: [number, number]) => {
              const cx = ix * width;
              const cy = iy * height;
              ctx.beginPath();
              ctx.arc(cx, cy, 5.5, 0, 2 * Math.PI);
              ctx.fillStyle = '#ef4444';
              ctx.fill();
              ctx.lineWidth = 2;
              ctx.strokeStyle = '#ffffff';
              ctx.stroke();
            });
          }
        } else {
          // Marked Restricted Zone
          ctx.fillStyle = 'rgba(245, 158, 11, 0.12)';
          ctx.fill();
          ctx.lineWidth = 1.8;
          ctx.strokeStyle = '#f59e0b';
          ctx.setLineDash([6, 4]);
          ctx.stroke();

          // Zone Tag Banner
          const [firstX, firstY] = poly[0];
          const tagText = tracked ? `🔒 Protected: ${z.name}` : `🔒 Restricted: ${z.name}`;
          ctx.font = 'bold 9px "Geist Mono", monospace';
          const tagW = ctx.measureText(tagText).width + 8;
          ctx.fillStyle = '#d97706';
          ctx.fillRect(firstX * width, Math.max(0, firstY * height - 14), tagW, 14);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(tagText, firstX * width + 4, Math.max(10, firstY * height - 3));
        }

        ctx.restore();
      });

      // 2. Draw Multi-Category Identified Objects (Phones, Electronics, Furniture, Hazards, Tools, Containers, etc.)
      const detections = cameraDetections[cam.id] || [];
      const tracks = cameraTracks[cam.id] || [];

      // Render identified everyday & industrial objects
      detections.forEach((det: any) => {
        const cat = (det.category || 'OBJECT').toUpperCase();
        if (cat === 'PERSON') {
          // If a tracked person already exists at this location, avoid double boxes
          const overlapsTrack = tracks.some((trk: any) => {
            if (!trk.norm_bbox || !det.norm_bbox) return false;
            const [tx1, ty1, tx2, ty2] = trk.norm_bbox;
            const [dx1, dy1, dx2, dy2] = det.norm_bbox;
            const ix1 = Math.max(tx1, dx1), iy1 = Math.max(ty1, dy1);
            const ix2 = Math.min(tx2, dx2), iy2 = Math.min(ty2, dy2);
            if (ix2 > ix1 && iy2 > iy1) {
              const inter = (ix2 - ix1) * (iy2 - iy1);
              const union = (tx2 - tx1) * (ty2 - ty1) + (dx2 - dx1) * (dy2 - dy1) - inter;
              return union > 0 && inter / union > 0.4;
            }
            return false;
          });
          if (overlapsTrack) return;
        }

        // Compute coordinate bounding box
        let x = 0, y = 0, w = 0, h = 0;
        if (det.norm_bbox && det.norm_bbox.length === 4) {
          const [nx1, ny1, nx2, ny2] = det.norm_bbox;
          x = nx1 * width;
          y = ny1 * height;
          w = Math.max(16, (nx2 - nx1) * width);
          h = Math.max(18, (ny2 - ny1) * height);
        } else if (det.bbox && det.bbox.length === 4) {
          const [bx1, by1, bx2, by2] = det.bbox;
          if (bx1 <= 1.0 && bx2 <= 1.0) {
            x = bx1 * width;
            y = by1 * height;
            w = Math.max(16, (bx2 - bx1) * width);
            h = Math.max(18, (by2 - by1) * height);
          } else {
            const scaleX = width / ((cam as any).width || 640);
            const scaleY = height / ((cam as any).height || 480);
            x = bx1 * scaleX;
            y = by1 * scaleY;
            w = Math.max(16, (bx2 - bx1) * scaleX);
            h = Math.max(18, (by2 - by1) * scaleY);
          }
        }

        // Distinct Category Styling
        let color = '#06b6d4'; // default cyan
        let icon = '📦';
        if (cat === 'ELECTRONICS') {
          color = '#06b6d4'; // Cyan
          icon = '📱';
        } else if (cat === 'HAZARD_OBJECT') {
          color = '#f59e0b'; // Amber warning for potential objects, reserving red strictly for restricted zone intrusions
          icon = '⚠️';
        } else if (cat === 'MACHINE') {
          color = '#f59e0b'; // Amber
          icon = '⚙️';
        } else if (cat === 'CONTAINER') {
          color = '#10b981'; // Emerald
          icon = '🎒';
        } else if (cat === 'FURNITURE') {
          color = '#8b5cf6'; // Violet
          icon = '🪑';
        } else if (cat === 'FACE') {
          color = '#ec4899'; // Pink
          icon = '👤';
        } else if (cat === 'PERSON') {
          color = '#3b82f6'; // Blue
          icon = '👷';
        }

        ctx.save();
        // Subtle bounding box tint
        ctx.fillStyle = `${color}14`;
        ctx.fillRect(x, y, w, h);

        // Thin perimeter box
        ctx.lineWidth = 1.2;
        ctx.strokeStyle = `${color}aa`;
        ctx.strokeRect(x, y, w, h);

        // Corner reticles
        const cLen = Math.min(10, Math.max(5, Math.min(w, h) * 0.25));
        ctx.lineWidth = 2;
        ctx.strokeStyle = color;
        // TL
        ctx.beginPath();
        ctx.moveTo(x, y + cLen); ctx.lineTo(x, y); ctx.lineTo(x + cLen, y); ctx.stroke();
        // TR
        ctx.beginPath();
        ctx.moveTo(x + w - cLen, y); ctx.lineTo(x + w, y); ctx.lineTo(x + w, y + cLen); ctx.stroke();
        // BL
        ctx.beginPath();
        ctx.moveTo(x, y + h - cLen); ctx.lineTo(x, y + h); ctx.lineTo(x + cLen, y + h); ctx.stroke();
        // BR
        ctx.beginPath();
        ctx.moveTo(x + w - cLen, y + h); ctx.lineTo(x + w, y + h); ctx.lineTo(x + w, y + h - cLen); ctx.stroke();

        // Header Tag
        const labelName = (det.class_name || cat).toUpperCase();
        const confPct = Math.round((det.confidence || 0.85) * 100);
        const tagText = `${icon} ${labelName} ${confPct}%`;
        ctx.font = 'bold 8.5px "Geist Mono", monospace';
        const tagW = ctx.measureText(tagText).width + 8;
        const tagY = Math.max(13, y - 3);

        ctx.fillStyle = color;
        ctx.fillRect(x, tagY - 12, tagW, 13);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(tagText, x + 4, tagY - 2);

        ctx.restore();
      });

      // 3. Draw Live Worker Tracks & Computer Vision Detection HUDs
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

        // D. Top Floating Telemetry Pill: Worker ID + Status
        const workerId = track.track_id ? track.track_id.toString().padStart(2, '0') : '01';
        const statusText = isCrit ? 'Violation' : isWarn ? 'Alert' : 'Compliant';
        const topTag = `Worker #${workerId} • ${statusText}`;
        ctx.font = 'bold 9.5px "Geist Mono", monospace';
        const topTagW = ctx.measureText(topTag).width + 8;
        const tagY = Math.max(15, y - 4);

        ctx.fillStyle = themeColor;
        ctx.fillRect(x, tagY - 13, topTagW, 14);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(topTag, x + 4, tagY - 3);

        // E. Spatial Head ROI & Helmet Badge (Upper 35%)
        const headH = h * 0.35;
        const hasHelmet = track.has_helmet === true;
        ctx.lineWidth = 1;
        ctx.strokeStyle = hasHelmet ? 'rgba(5, 150, 105, 0.6)' : 'rgba(220, 38, 38, 0.8)';
        ctx.setLineDash([2, 2]);
        ctx.strokeRect(x, y, w, headH);
        ctx.setLineDash([]);

        // PPE Badges below bounding box
        let badgeOffsetY = y + h + 2;
        
        // Helmet Badge
        const helmetText = hasHelmet ? '⛑️ Helmet: OK' : '⚠️ No Helmet';
        ctx.font = 'bold 8.5px "Geist Mono", monospace';
        const helmetW = ctx.measureText(helmetText).width + 6;
        ctx.fillStyle = hasHelmet ? '#059669' : '#dc2626';
        ctx.fillRect(x, badgeOffsetY, helmetW, 12);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(helmetText, x + 3, badgeOffsetY + 9);

        // Vest Badge
        const hasVest = track.has_vest === true;
        const vestText = hasVest ? '🦺 Vest: OK' : '⚠️ No Vest';
        const vestW = ctx.measureText(vestText).width + 6;
        ctx.fillStyle = hasVest ? '#059669' : '#d97706';
        ctx.fillRect(x + helmetW + 2, badgeOffsetY, vestW, 12);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(vestText, x + helmetW + 5, badgeOffsetY + 9);

        // Glasses Badge
        let glassesX = x + helmetW + vestW + 4;
        let glassesY = badgeOffsetY;
        if (helmetW + vestW + 80 > Math.max(w, 210)) {
          badgeOffsetY += 14;
          glassesX = x;
          glassesY = badgeOffsetY;
        }
        const hasGlasses = track.has_glasses === true;
        const glassesText = hasGlasses ? '👓 Glasses: OK' : (track.has_glasses === false ? '⚠️ No Glasses' : '👓 Glasses: --');
        const glassesW = ctx.measureText(glassesText).width + 6;
        ctx.fillStyle = hasGlasses ? '#059669' : (track.has_glasses === false ? '#ea580c' : '#475569');
        ctx.fillRect(glassesX, glassesY, glassesW, 12);
        ctx.fillStyle = '#ffffff';
        ctx.fillText(glassesText, glassesX + 3, glassesY + 9);

        // F. Posture / Fall Detection Tag if fallen or crouched
        if (track.is_fallen || track.fall_state === 'FALL_CONFIRMED') {
          badgeOffsetY += 14;
          const fallText = '🚨 Fall Detected';
          const fallW = ctx.measureText(fallText).width + 8;
          ctx.fillStyle = '#dc2626';
          ctx.fillRect(x, badgeOffsetY, fallW, 14);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(fallText, x + 4, badgeOffsetY + 10);
        }

        // G. Restricted Safety Zone Breach Tag
        if (track.current_zone_id) {
          badgeOffsetY += 14;
          const zoneBreachText = '🚨 In Restricted Zone';
          const zoneW = ctx.measureText(zoneBreachText).width + 8;
          ctx.fillStyle = '#b91c1c';
          ctx.fillRect(x, badgeOffsetY, zoneW, 14);
          ctx.fillStyle = '#ffffff';
          ctx.fillText(zoneBreachText, x + 4, badgeOffsetY + 10);
        }

        // H. Ground Contact Foot-Anchor Reticle
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
  }, [cameras, zones, machines, cameraTracks, cameraDetections, visualZones, cameraIntrusions]);

  const defaultSectors: Record<string, string> = {
    CAM_01: 'SECTOR_A_CORRIDOR',
    CAM_02: 'ASSEMBLY_LINE_B',
    CAM_03: 'HEAVY_MACHINERY_Z1',
    CAM_04: 'LOADING_DOCK_INT',
  };

  const [activeFilter, setActiveFilter] = useState<'all' | 'cctv' | 'mobile'>('all');
  const [allStreamsPaused, setAllStreamsPaused] = useState<boolean>(false);
  const [pausedCameras, setPausedCameras] = useState<Record<string, boolean>>({});
  const [cameraPowerState, setCameraPowerState] = useState<Record<string, 'ONLINE' | 'OFFLINE' | 'ERROR'>>({});
  const [isTogglingPower, setIsTogglingPower] = useState<Record<string, boolean>>({});

  useEffect(() => {
    const initial: Record<string, 'ONLINE' | 'OFFLINE' | 'ERROR'> = {};
    cameras.forEach((c) => {
      initial[c.id] = c.status || 'ONLINE';
    });
    setCameraPowerState((prev) => ({ ...initial, ...prev }));
  }, [cameras]);

  const handleToggleCamera = async (cameraId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const current = cameraPowerState[cameraId] || 'ONLINE';
    const isStopping = current === 'ONLINE';

    setIsTogglingPower((prev) => ({ ...prev, [cameraId]: true }));
    try {
      if (isStopping) {
        await stopCameraFeed(cameraId);
        setCameraPowerState((prev) => ({ ...prev, [cameraId]: 'OFFLINE' }));
        setPausedCameras((prev) => ({ ...prev, [cameraId]: true }));
      } else {
        await startCameraFeed(cameraId);
        setCameraPowerState((prev) => ({ ...prev, [cameraId]: 'ONLINE' }));
        setPausedCameras((prev) => ({ ...prev, [cameraId]: false }));
      }
      if (onZonesUpdated) onZonesUpdated();
    } catch (err) {
      console.error(`Failed to ${isStopping ? 'stop' : 'start'} camera ${cameraId}:`, err);
    } finally {
      setIsTogglingPower((prev) => ({ ...prev, [cameraId]: false }));
    }
  };

  const isAnyCameraOnline = cameras.some(
    (c) => (cameraPowerState[c.id] ?? c.status) !== 'OFFLINE' && !pausedCameras[c.id] && !allStreamsPaused
  );

  const handleToggleAllCameras = async () => {
    const shouldStop = isAnyCameraOnline;
    setAllStreamsPaused(shouldStop);
    const updatedPaused: Record<string, boolean> = {};

    for (const c of cameras) {
      setIsTogglingPower((prev) => ({ ...prev, [c.id]: true }));
      try {
        if (shouldStop) {
          await stopCameraFeed(c.id);
          setCameraPowerState((prev) => ({ ...prev, [c.id]: 'OFFLINE' }));
          updatedPaused[c.id] = true;
        } else {
          await startCameraFeed(c.id);
          setCameraPowerState((prev) => ({ ...prev, [c.id]: 'ONLINE' }));
          updatedPaused[c.id] = false;
        }
      } catch (e) {
        // silent
      } finally {
        setIsTogglingPower((prev) => ({ ...prev, [c.id]: false }));
      }
    }
    setPausedCameras(updatedPaused);
    if (onZonesUpdated) onZonesUpdated();
  };

  const toggleCameraPause = (cameraId: string, e?: React.MouseEvent) => {
    handleToggleCamera(cameraId, e);
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
        <div className="flex items-center gap-2.5">
          <h3 className="font-mono text-xs font-semibold text-slate-200 tracking-wider flex items-center gap-2">
            <span className={`w-2 h-2 rounded-full ${isAnyCameraOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-500'}`} />
            Live Camera Feed
          </h3>
          <span className="px-2 py-0.5 rounded bg-blue-500/10 text-blue-400 border border-blue-500/20 text-[10px] font-mono flex items-center gap-1">
            <span className="material-symbols-outlined text-[12px]">videocam</span>
            FaceTime HD // Primary Channel
          </span>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {/* Mark Restricted Area Button */}
          <button
            onClick={() => setIsZoneEditorOpen(true)}
            className="flex items-center gap-1.5 px-3 py-1 bg-red-600/90 hover:bg-red-600 text-white rounded-md text-xs font-mono font-medium shadow-sm transition-all active:scale-95 border border-red-500/40"
            title="Configure a restricted safety perimeter on the camera feed"
          >
            <span className="material-symbols-outlined text-sm">security</span>
            Set Restricted Zone
          </button>

          {/* Real Camera Hardware Stop / Start Button */}
          <button
            onClick={handleToggleAllCameras}
            className={`flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-mono font-semibold transition-all border shadow-sm ${
              isAnyCameraOnline
                ? 'bg-red-600/90 hover:bg-red-600 text-white border-red-500/50'
                : 'bg-emerald-600/90 hover:bg-emerald-500 text-white border-emerald-500/50'
            }`}
            title={isAnyCameraOnline ? 'Stop Camera Hardware & Pipeline' : 'Start Camera Hardware & Pipeline'}
          >
            <span className="material-symbols-outlined text-sm">
              {isAnyCameraOnline ? 'videocam_off' : 'videocam'}
            </span>
            {isAnyCameraOnline ? 'Stop Camera' : 'Start Camera'}
          </button>
        </div>
      </div>

      {/* Modal: Mark Restricted Area Editor */}
      {isZoneEditorOpen && (
        <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
          <div className="bg-surface border border-outline-variant rounded-xl w-full max-w-5xl shadow-2xl p-5 relative my-8">
            <div className="flex justify-between items-center pb-3 mb-4 border-b border-outline-variant">
              <h3 className="font-label-mono-bold text-sm text-on-surface font-bold flex items-center gap-2">
                <span className="material-symbols-outlined text-red-500">security</span>
                Configure Restricted Safety Zone
              </h3>
              <button
                onClick={() => setIsZoneEditorOpen(false)}
                className="p-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface transition font-bold"
              >
                <span className="material-symbols-outlined text-base">close</span>
              </button>
            </div>

            <ZonePolygonEditor
              cameras={cameras}
              zones={zones}
              onZonesUpdated={() => {
                if (onZonesUpdated) onZonesUpdated();
              }}
            />
          </div>
        </div>
      )}

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
            const isStopped = (cameraPowerState[cam.id] ?? cam.status) === 'OFFLINE' || isPaused;

            return (
              <div
                key={cam.id}
                onClick={() => onSelectCamera && onSelectCamera(cam)}
                className={`level-1-panel rounded-lg overflow-hidden relative group cursor-pointer aspect-[16/10] flex flex-col justify-between ${
                  hasCritical && !isStopped
                    ? 'border-2 border-severity-critical shadow-[0_0_15px_rgba(220,38,38,0.2)] z-10'
                    : ''
                }`}
              >
                {/* Background Live Video Feed */}
                {!isStopped ? (
                  /* eslint-disable-next-line @next/next/no-img-element */
                  <img
                    src={getMediaUrl(`/api/cameras/${cam.id}/stream`)}
                    alt={cam.name}
                    className={`absolute inset-0 w-full h-full object-cover ${
                      hasCritical ? 'contrast-105' : ''
                    }`}
                    onError={(e) => {
                      const target = e.currentTarget;
                      const retries = parseInt(target.getAttribute('data-retries') || '0', 10);
                      if (retries < 15) {
                        target.setAttribute('data-retries', String(retries + 1));
                        setTimeout(() => {
                          target.src = getMediaUrl(`/api/cameras/${cam.id}/stream?retry=${Date.now()}`);
                        }, 1200);
                      }
                    }}
                  />
                ) : (
                  <div className="absolute inset-0 w-full h-full bg-surface-container-highest/95 flex flex-col items-center justify-center gap-3 backdrop-blur-sm z-10 p-4">
                    <div className="w-14 h-14 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center shadow-inner">
                      <span className="material-symbols-outlined text-3xl text-red-400">
                        videocam_off
                      </span>
                    </div>
                    <div className="text-center">
                      <div className="font-label-mono-bold text-xs font-bold text-red-400 uppercase tracking-widest">
                        CAMERA OFFLINE
                      </div>
                      <div className="font-label-mono text-[11px] text-on-surface-variant mt-0.5 max-w-[240px]">
                        Hardware stream suspended. Lens sensor & YOLO inference powered down.
                      </div>
                    </div>
                    <button
                      onClick={(e) => handleToggleCamera(cam.id, e)}
                      disabled={isTogglingPower[cam.id]}
                      className="px-3.5 py-1.5 bg-emerald-500 hover:bg-emerald-400 text-black text-xs font-bold rounded shadow flex items-center gap-1.5 transition font-label-mono-bold active:scale-95"
                    >
                      <span className="material-symbols-outlined text-sm">
                        {isTogglingPower[cam.id] ? 'refresh' : 'videocam'}
                      </span>
                      {isTogglingPower[cam.id] ? 'STARTING...' : 'START CAMERA FEED'}
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
                  className={`absolute inset-0 w-full h-full pointer-events-none z-10 ${isStopped ? 'hidden' : ''}`}
                />

                {/* Camera Gradient Overlay */}
                <div className="absolute inset-0 camera-overlay pointer-events-none" />

                {/* Subtle Amber/Red Border for Alert Camera */}
                {hasCritical && !isStopped && (
                  <div className="absolute inset-0 border-2 border-severity-critical pointer-events-none" />
                )}

                {/* Top Left: Camera ID & Sector */}
                <div className={`absolute top-3 left-3 z-20 backdrop-blur px-2 py-1 rounded flex flex-col shadow-sm ${
                  hasCritical && !isStopped
                    ? 'bg-severity-critical text-white'
                    : 'bg-surface/90 border border-outline-variant text-on-surface'
                }`}>
                  <div className="flex items-center gap-1.5">
                    <span className="font-label-mono-bold text-xs font-bold">{cam.name || 'Webcam'}</span>
                    {(cam.source === '0' || cam.source_type === 'webcam') && !isStopped && (
                      <span className="px-1.5 py-0.2 bg-emerald-500 text-black text-[9px] font-bold rounded">
                        LIVE
                      </span>
                    )}
                  </div>
                  <span className={`font-label-mono text-[10px] ${hasCritical && !isStopped ? 'text-white/90' : 'text-on-surface-variant'}`}>
                    {isStopped ? 'Standby State' : 'Active Monitoring'}
                  </span>
                </div>

                {/* Top Right: Status Badge & Power Toggle */}
                <div className="absolute top-3 right-3 z-20 flex items-center gap-1.5">
                  <button
                    onClick={(e) => handleToggleCamera(cam.id, e)}
                    disabled={isTogglingPower[cam.id]}
                    title={isStopped ? "Power on camera stream" : "Stop camera stream (turns off sensor)"}
                    className={`px-2 py-0.5 rounded text-[11px] font-label-mono-bold font-bold flex items-center gap-1 shadow-sm backdrop-blur transition-all border ${
                      isStopped
                        ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/40 hover:bg-emerald-500/30'
                        : 'bg-red-500/20 text-red-400 border-red-500/40 hover:bg-red-500/30'
                    }`}
                  >
                    <span className="material-symbols-outlined text-xs">
                      {isTogglingPower[cam.id] ? 'sync' : isStopped ? 'videocam' : 'videocam_off'}
                    </span>
                    <span>{isTogglingPower[cam.id] ? '...' : isStopped ? 'START' : 'STOP'}</span>
                  </button>

                  {isStopped ? (
                    <div className="bg-surface/90 backdrop-blur border border-outline-variant px-2 py-0.5 rounded flex items-center gap-1.5 shadow-sm">
                      <span className="w-1.5 h-1.5 rounded-full bg-neutral-500" />
                      <span className="font-label-mono-bold text-xs text-neutral-400 font-bold">OFFLINE</span>
                    </div>
                  ) : hasCritical ? (
                    <div className="bg-severity-critical backdrop-blur px-2.5 py-0.5 rounded flex items-center gap-1.5 shadow-sm">
                      <span className="material-symbols-outlined text-white text-xs" style={{ fontVariationSettings: "'FILL' 1" }}>
                        warning
                      </span>
                      <span className="font-label-mono-bold text-xs text-white tracking-wider font-bold">HAZARD</span>
                    </div>
                  ) : (
                    <div className="bg-surface/90 backdrop-blur border border-severity-safe px-2 py-0.5 rounded flex items-center gap-1.5 shadow-sm">
                      <span className="w-1.5 h-1.5 rounded-full bg-severity-safe" />
                      <span className="font-label-mono-bold text-xs text-severity-safe font-bold">NORMAL</span>
                    </div>
                  )}
                </div>

                {/* Bottom Left: Risk Score Pill if Elevated */}
                {hasCritical && !isStopped && (
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
                    hasCritical && !isStopped
                      ? 'bg-severity-critical/80 text-white border-severity-critical font-bold'
                      : 'bg-surface/90 text-on-surface border-outline-variant/50 font-bold'
                  }`}>
                    FPS: {isStopped ? '0.0' : fps.toFixed(1)}
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
