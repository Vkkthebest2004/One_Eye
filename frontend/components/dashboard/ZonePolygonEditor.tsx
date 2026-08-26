import React, { useState, useRef } from 'react';
import { Camera, Zone } from '@/types';
import { getMediaUrl, createZone, deleteZone } from '@/lib/api';
import { ShieldAlert, Plus, Trash2, CheckCircle2, RotateCcw, Save, Camera as CameraIcon, Play, Square, Pentagon, AlertTriangle } from 'lucide-react';

interface ZonePolygonEditorProps {
  cameras: Camera[];
  zones: Zone[];
  onZonesUpdated: () => void;
}

export const ZonePolygonEditor: React.FC<ZonePolygonEditorProps> = ({
  cameras,
  zones,
  onZonesUpdated,
}) => {
  const [selectedCamId, setSelectedCamId] = useState<string>(cameras[0]?.id || 'CAM_01');
  const [points, setPoints] = useState<Array<[number, number]>>([]);
  const [zoneName, setZoneName] = useState('Forbidden Hazard Area');
  const [severity, setSeverity] = useState(95);
  const [warningDelay, setWarningDelay] = useState(0.0);
  const [drawMode, setDrawMode] = useState<'polygon' | 'box'>('polygon');
  const [boxStart, setBoxStart] = useState<[number, number] | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [frozenSnapshot, setFrozenSnapshot] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);
  const imgRef = useRef<HTMLImageElement | null>(null);

  // Filter existing zones for selected camera
  const cameraZones = zones.filter((z) => z.camera_id === selectedCamId);

  // Capture current live frame into a frozen photo snapshot
  const handleCaptureSnapshot = () => {
    if (!containerRef.current) return;
    try {
      const canvas = document.createElement('canvas');
      const rect = containerRef.current.getBoundingClientRect();
      canvas.width = rect.width || 640;
      canvas.height = rect.height || 360;
      const ctx = canvas.getContext('2d');
      if (ctx && imgRef.current) {
        ctx.drawImage(imgRef.current, 0, 0, canvas.width, canvas.height);
        const dataUrl = canvas.toDataURL('image/jpeg', 0.9);
        setFrozenSnapshot(dataUrl);
        setStatusMsg('📸 Live frame frozen. Click on the photo to mark the forbidden area.');
        return;
      }
    } catch (e) {
      // Fallback
    }
    // Fallback URL timestamp
    setFrozenSnapshot(getMediaUrl(`/api/cameras/${selectedCamId}/stream?freeze=${Date.now()}`));
    setStatusMsg('📸 Live frame frozen. Click on the photo to mark the forbidden area.');
  };

  const handleResumeLive = () => {
    setFrozenSnapshot(null);
    setStatusMsg(null);
  };

  // Handle clicking on photo / canvas to mark points
  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const normX = Math.max(0.0, Math.min(1.0, clickX / rect.width));
    const normY = Math.max(0.0, Math.min(1.0, clickY / rect.height));
    const newPoint: [number, number] = [parseFloat(normX.toFixed(4)), parseFloat(normY.toFixed(4))];

    if (drawMode === 'box') {
      if (!boxStart) {
        setBoxStart(newPoint);
        setPoints([newPoint]);
        setStatusMsg('Click the opposite corner to complete the box.');
      } else {
        const [x1, y1] = boxStart;
        const [x2, y2] = newPoint;
        const minX = Math.min(x1, x2);
        const maxX = Math.max(x1, x2);
        const minY = Math.min(y1, y2);
        const maxY = Math.max(y1, y2);

        const boxPolygon: Array<[number, number]> = [
          [minX, minY],
          [maxX, minY],
          [maxX, maxY],
          [minX, maxY],
        ];
        setPoints(boxPolygon);
        setBoxStart(null);
        setStatusMsg('Forbidden box marked! Click "Save Forbidden Zone" below.');
      }
    } else {
      // Polygon mode
      setPoints((prev) => [...prev, newPoint]);
      setStatusMsg(`Point ${points.length + 1} added. Place at least 3 points to enclose the area.`);
    }
  };

  const handleReset = () => {
    setPoints([]);
    setBoxStart(null);
    setStatusMsg(null);
  };

  const handleSaveZone = async () => {
    if (points.length < 3) {
      setStatusMsg('Please place at least 3 points to enclose the forbidden area.');
      return;
    }
    setIsSaving(true);
    setStatusMsg(null);
    try {
      const zoneId = `ZONE_${Date.now().toString().slice(-6)}`;
      await createZone({
        id: zoneId,
        name: zoneName.trim() || 'Forbidden Zone',
        camera_id: selectedCamId,
        polygon: points,
        severity: severity,
        warning_delay_seconds: warningDelay,
        critical_delay_seconds: 3.0,
        active: true,
      });
      setPoints([]);
      setBoxStart(null);
      setFrozenSnapshot(null);
      setStatusMsg(`✅ Forbidden zone '${zoneName}' saved & activated!`);
      onZonesUpdated();
    } catch (e: any) {
      setStatusMsg(`Failed to save zone: ${e.message}`);
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteZone = async (zoneId: string) => {
    try {
      await deleteZone(zoneId);
      onZonesUpdated();
    } catch (e: any) {
      console.error('Failed to delete zone:', e);
    }
  };

  const presetNames = [
    '🚨 Forbidden Area',
    '⚠️ Hazardous Machine Perimeter',
    '⚡ High Voltage Restricted',
    '🛑 No-Entry Floor Area',
  ];

  return (
    <div className="flex flex-col gap-5 level-1-panel rounded-lg p-panel-padding bg-surface border border-outline-variant">
      {/* Header & Camera Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-outline-variant pb-3">
        <div>
          <h3 className="font-label-mono text-sm font-bold text-on-surface uppercase tracking-wider flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-severity-critical" />
            Forbidden Safety Area Marker
          </h3>
          <p className="font-label-mono text-xs text-on-surface-variant mt-0.5">
            Freeze a frame, mark any forbidden danger perimeter, and trigger real-time alerts when a person enters.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-label-mono text-xs text-on-surface-variant font-bold">Camera Feed:</span>
          <select
            value={selectedCamId}
            onChange={(e) => {
              setSelectedCamId(e.target.value);
              setPoints([]);
              setFrozenSnapshot(null);
            }}
            className="bg-surface-container-low px-3 py-1.5 rounded-lg border border-outline-variant font-label-mono text-xs text-on-surface focus:outline-none focus:border-primary font-bold"
          >
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.id} — {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Interactive Video Canvas with SVG Polygon (8 cols) */}
        <div className="lg:col-span-8 flex flex-col gap-3">
          {/* Controls Bar above Canvas */}
          <div className="flex flex-wrap items-center justify-between gap-2">
            {/* Drawing Mode Selector */}
            <div className="flex items-center gap-1.5 bg-surface-container-low p-1 rounded-lg border border-outline-variant">
              <button
                type="button"
                onClick={() => {
                  setDrawMode('polygon');
                  setBoxStart(null);
                }}
                className={`px-2.5 py-1 rounded text-xs font-mono font-bold flex items-center gap-1 transition ${
                  drawMode === 'polygon'
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <Pentagon className="w-3.5 h-3.5" />
                Multi-Point Polygon
              </button>
              <button
                type="button"
                onClick={() => {
                  setDrawMode('box');
                  setPoints([]);
                  setBoxStart(null);
                }}
                className={`px-2.5 py-1 rounded text-xs font-mono font-bold flex items-center gap-1 transition ${
                  drawMode === 'box'
                    ? 'bg-primary text-white shadow-sm'
                    : 'text-on-surface-variant hover:text-on-surface'
                }`}
              >
                <Square className="w-3.5 h-3.5" />
                2-Click Box
              </button>
            </div>

            {/* Freeze Snapshot / Resume Live Toggle */}
            <div className="flex items-center gap-2">
              {!frozenSnapshot ? (
                <button
                  type="button"
                  onClick={handleCaptureSnapshot}
                  className="px-3 py-1.5 bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/40 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition"
                >
                  <CameraIcon className="w-3.5 h-3.5" />
                  📸 Freeze Frame Photo
                </button>
              ) : (
                <button
                  type="button"
                  onClick={handleResumeLive}
                  className="px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/40 rounded-lg text-xs font-mono font-bold flex items-center gap-1.5 transition"
                >
                  <Play className="w-3.5 h-3.5" />
                  ▶ Live Video Feed
                </button>
              )}
            </div>
          </div>

          <div
            ref={containerRef}
            onClick={handleCanvasClick}
            className={`relative aspect-[16/10] bg-black rounded-lg overflow-hidden border-2 cursor-crosshair group shadow-inner ${
              frozenSnapshot ? 'border-amber-400' : 'border-outline-variant'
            }`}
          >
            {/* Live Camera Feed / Frozen Snapshot */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              ref={imgRef}
              crossOrigin="anonymous"
              src={frozenSnapshot || getMediaUrl(`/api/cameras/${selectedCamId}/stream`)}
              alt="Camera Preview"
              className="absolute inset-0 w-full h-full object-cover pointer-events-none select-none"
              onError={(e) => {
                const target = e.currentTarget;
                setTimeout(() => {
                  target.src = getMediaUrl(`/api/cameras/${selectedCamId}/stream?t=${Date.now()}`);
                }, 2000);
              }}
            />

            {/* SVG Polygon Overlay */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none">
              {/* 1. Existing Saved Forbidden Zones */}
              {cameraZones.map((z) => {
                if (!z.polygon || z.polygon.length < 3) return null;
                const pointsStr = z.polygon
                  .map(([px, py]) => `${px * 100}%,${py * 100}%`)
                  .join(' ');

                return (
                  <g key={z.id}>
                    <polygon
                      points={pointsStr}
                      fill="rgba(220, 38, 38, 0.25)"
                      stroke="#dc2626"
                      strokeWidth="2.5"
                      strokeDasharray="6,4"
                    />
                    <text
                      x={`${z.polygon[0][0] * 100}%`}
                      y={`${z.polygon[0][1] * 100}%`}
                      fill="#ffffff"
                      fontSize="11"
                      fontWeight="bold"
                      fontFamily="monospace"
                      dy="-8"
                      className="bg-black/90 px-1"
                    >
                      🚨 FORBIDDEN: {z.name.toUpperCase()}
                    </text>
                  </g>
                );
              })}

              {/* 2. Currently Active Drawn Polygon Preview */}
              {points.length > 0 && (
                <>
                  {points.length >= 3 && (
                    <polygon
                      points={points.map(([px, py]) => `${px * 100}%,${py * 100}%`).join(' ')}
                      fill="rgba(239, 68, 68, 0.35)"
                      stroke="#ef4444"
                      strokeWidth="2.5"
                      strokeDasharray="4,4"
                    />
                  )}

                  {/* Connecting Polyline if < 3 points */}
                  {points.length < 3 && (
                    <polyline
                      points={points.map(([px, py]) => `${px * 100}%,${py * 100}%`).join(' ')}
                      fill="none"
                      stroke="#ef4444"
                      strokeWidth="2.5"
                      strokeDasharray="4,4"
                    />
                  )}

                  {/* Vertex Points */}
                  {points.map(([px, py], idx) => (
                    <circle
                      key={idx}
                      cx={`${px * 100}%`}
                      cy={`${py * 100}%`}
                      r="6"
                      fill="#ef4444"
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                  ))}
                </>
              )}
            </svg>

            {/* Instruction Badge */}
            <div className="absolute top-2 left-2 bg-black/80 backdrop-blur px-2.5 py-1.5 rounded-lg text-xs font-mono text-white pointer-events-none flex items-center gap-2 shadow">
              <span className={`w-2.5 h-2.5 rounded-full ${frozenSnapshot ? 'bg-amber-400' : 'bg-primary animate-pulse'}`} />
              {frozenSnapshot ? (
                <span className="text-amber-300 font-bold">📸 Photo Frozen — Click to mark points</span>
              ) : points.length === 0 ? (
                drawMode === 'box'
                  ? 'Click corner 1, then click corner 2 to draw a forbidden box'
                  : 'Click points on video feed to mark forbidden boundary'
              ) : (
                `Marked ${points.length} points (Click more or tap Save below)`
              )}
            </div>
          </div>

          <div className="flex justify-between items-center text-xs font-label-mono text-on-surface-variant px-1">
            <span>Points placed: <strong className="text-on-surface">{points.length}</strong></span>
            {points.length > 0 && (
              <button
                type="button"
                onClick={handleReset}
                className="text-error hover:underline flex items-center gap-1 text-xs font-bold"
              >
                <RotateCcw className="w-3 h-3" /> Clear Points
              </button>
            )}
          </div>
        </div>

        {/* Right: Zone Configuration Form & List (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="bg-surface-container-low rounded-lg p-3.5 border border-outline-variant flex flex-col gap-3 font-label-mono text-xs">
            <h4 className="font-bold text-on-surface uppercase text-[11px] flex items-center gap-1.5">
              <AlertTriangle className="w-3.5 h-3.5 text-amber-400" />
              Forbidden Area Parameters
            </h4>

            {/* Quick Name Presets */}
            <div>
              <label className="text-[10px] text-on-surface-variant block mb-1 font-bold">Quick Presets</label>
              <div className="flex flex-wrap gap-1">
                {presetNames.map((p) => (
                  <button
                    key={p}
                    type="button"
                    onClick={() => setZoneName(p.replace(/^[^\w]+/, '').trim())}
                    className="px-2 py-0.5 rounded bg-surface border border-outline-variant hover:border-primary text-[10px] text-on-surface"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </div>

            <div>
              <label className="text-[10px] text-on-surface-variant block mb-1">Zone Label Name</label>
              <input
                type="text"
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                placeholder="e.g. Forbidden Safety Perimeter"
                className="w-full p-2 rounded bg-surface border border-outline-variant text-on-surface text-xs focus:outline-none focus:border-primary font-bold"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-on-surface-variant block mb-1">Alert Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(parseInt(e.target.value) || 95)}
                  className="w-full p-2 rounded bg-surface border border-outline-variant text-on-surface text-xs focus:outline-none"
                >
                  <option value={95}>95 (Critical Siren)</option>
                  <option value={80}>80 (High Alert)</option>
                  <option value={50}>50 (Warning)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-on-surface-variant block mb-1">Breach Alarm Delay</label>
                <select
                  value={warningDelay}
                  onChange={(e) => setWarningDelay(parseFloat(e.target.value) || 0.0)}
                  className="w-full p-2 rounded bg-surface border border-outline-variant text-on-surface text-xs focus:outline-none"
                >
                  <option value={0.0}>⚡ Instant Alarm (0.0s)</option>
                  <option value={0.5}>0.5 Seconds</option>
                  <option value={1.0}>1.0 Seconds</option>
                </select>
              </div>
            </div>

            {statusMsg && (
              <div className="p-2.5 rounded bg-primary/10 border border-primary/30 text-primary text-[11px] font-bold">
                {statusMsg}
              </div>
            )}

            <button
              type="button"
              onClick={handleSaveZone}
              disabled={isSaving || points.length < 3}
              className={`w-full py-2.5 rounded font-label-mono-bold text-xs flex items-center justify-center gap-1.5 transition shadow-sm font-bold ${
                points.length >= 3
                  ? 'bg-red-600 hover:bg-red-500 text-white cursor-pointer shadow-lg'
                  : 'bg-surface-container text-on-surface-variant opacity-50 cursor-not-allowed'
              }`}
            >
              <Save className="w-3.5 h-3.5" />
              Save Forbidden Zone & Activate Alerts
            </button>
          </div>

          {/* Active Saved Zones for Camera */}
          <div className="bg-surface-container-low rounded-lg p-3.5 border border-outline-variant flex flex-col gap-2 font-label-mono text-xs">
            <h4 className="font-bold text-on-surface uppercase text-[11px] flex justify-between items-center">
              <span>Active Forbidden Zones ({cameraZones.length})</span>
            </h4>

            {cameraZones.length === 0 ? (
              <p className="text-on-surface-variant text-[11px]">No restricted zones active for this camera.</p>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar pr-1">
                {cameraZones.map((z) => (
                  <div
                    key={z.id}
                    className="flex items-center justify-between p-2 rounded bg-surface border border-outline-variant hover:border-red-500/50 transition"
                  >
                    <div>
                      <div className="font-bold text-on-surface text-xs text-red-400">🚨 {z.name}</div>
                      <div className="text-[10px] text-on-surface-variant">
                        {z.polygon?.length || 0} vertices • {z.severity}/100 Severity • Active
                      </div>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleDeleteZone(z.id)}
                      className="p-1 text-error hover:bg-error-container/20 rounded transition"
                      title="Delete Forbidden Zone"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
