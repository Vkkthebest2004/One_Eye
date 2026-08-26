import React, { useState, useRef } from 'react';
import { Camera, Zone } from '@/types';
import { getMediaUrl, createZone, deleteZone } from '@/lib/api';
import { ShieldAlert, Plus, Trash2, CheckCircle2, RotateCcw, Save } from 'lucide-react';

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
  const [zoneName, setZoneName] = useState('Machine Danger Perimeter');
  const [severity, setSeverity] = useState(80);
  const [warningDelay, setWarningDelay] = useState(0.5);
  const [isSaving, setIsSaving] = useState(false);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);

  const containerRef = useRef<HTMLDivElement | null>(null);

  // Filter existing zones for selected camera
  const cameraZones = zones.filter((z) => z.camera_id === selectedCamId);

  // Handle clicking on video container to add polygon point (Normalized 0.0 to 1.0)
  const handleCanvasClick = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const clickY = e.clientY - rect.top;

    const normX = Math.max(0.0, Math.min(1.0, clickX / rect.width));
    const normY = Math.max(0.0, Math.min(1.0, clickY / rect.height));

    setPoints((prev) => [...prev, [parseFloat(normX.toFixed(4)), parseFloat(normY.toFixed(4))]]);
  };

  const handleReset = () => {
    setPoints([]);
    setStatusMsg(null);
  };

  const handleSaveZone = async () => {
    if (points.length < 3) {
      setStatusMsg('Please click at least 3 points on the camera to form a polygon.');
      return;
    }
    setIsSaving(true);
    setStatusMsg(null);
    try {
      const zoneId = `ZONE_${Date.now().toString().slice(-6)}`;
      await createZone({
        id: zoneId,
        name: zoneName,
        camera_id: selectedCamId,
        polygon: points,
        severity: severity,
        warning_delay_seconds: warningDelay,
        critical_delay_seconds: 5.0,
        active: true,
      });
      setPoints([]);
      setStatusMsg(`Zone '${zoneName}' saved successfully!`);
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

  return (
    <div className="flex flex-col gap-5 level-1-panel rounded-lg p-panel-padding bg-surface border border-outline-variant">
      {/* Header & Camera Selector */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-3 border-b border-outline-variant pb-3">
        <div>
          <h3 className="font-label-mono text-sm font-bold text-on-surface uppercase tracking-wider flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-severity-critical" />
            2D No-Entry Polygon Boundary Editor
          </h3>
          <p className="font-label-mono text-xs text-on-surface-variant mt-0.5">
            Click points directly on the camera preview to draw restricted safety zones.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="font-label-mono text-xs text-on-surface-variant font-bold">Camera:</span>
          <select
            value={selectedCamId}
            onChange={(e) => {
              setSelectedCamId(e.target.value);
              setPoints([]);
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
        <div className="lg:col-span-8 flex flex-col gap-2">
          <div
            ref={containerRef}
            onClick={handleCanvasClick}
            className="relative aspect-[16/10] bg-black rounded-lg overflow-hidden border-2 border-outline-variant cursor-crosshair group shadow-inner"
          >
            {/* Live Camera Feed */}
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={getMediaUrl(`/api/cameras/${selectedCamId}/stream`)}
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
              {/* 1. Existing Saved Zones for this Camera */}
              {cameraZones.map((z) => {
                if (!z.polygon || z.polygon.length < 3) return null;
                const pointsStr = z.polygon
                  .map(([px, py]) => `${px * 100}%,${py * 100}%`)
                  .join(' ');

                return (
                  <g key={z.id}>
                    <polygon
                      points={pointsStr}
                      fill="rgba(220, 38, 38, 0.20)"
                      stroke="#dc2626"
                      strokeWidth="2"
                      strokeDasharray="6,4"
                    />
                    <text
                      x={`${z.polygon[0][0] * 100}%`}
                      y={`${z.polygon[0][1] * 100}%`}
                      fill="#ffffff"
                      fontSize="10"
                      fontWeight="bold"
                      fontFamily="monospace"
                      dy="-6"
                      className="bg-black/80 px-1"
                    >
                      {z.name}
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
                      fill="rgba(37, 99, 235, 0.25)"
                      stroke="#2563eb"
                      strokeWidth="2"
                      strokeDasharray="4,4"
                    />
                  )}

                  {/* Connecting Polyline if < 3 points */}
                  {points.length < 3 && (
                    <polyline
                      points={points.map(([px, py]) => `${px * 100}%,${py * 100}%`).join(' ')}
                      fill="none"
                      stroke="#2563eb"
                      strokeWidth="2"
                      strokeDasharray="4,4"
                    />
                  )}

                  {/* Vertex Points */}
                  {points.map(([px, py], idx) => (
                    <circle
                      key={idx}
                      cx={`${px * 100}%`}
                      cy={`${py * 100}%`}
                      r="5"
                      fill={idx === 0 ? '#dc2626' : '#2563eb'}
                      stroke="#ffffff"
                      strokeWidth="2"
                    />
                  ))}
                </>
              )}
            </svg>

            {/* Instruction Badge */}
            <div className="absolute top-2 left-2 bg-black/75 backdrop-blur px-2.5 py-1 rounded text-[11px] font-mono text-white pointer-events-none flex items-center gap-1.5 shadow">
              <span className="w-2 h-2 rounded-full bg-primary animate-ping" />
              {points.length === 0
                ? 'Click on video feed to place polygon vertex points'
                : `Points: ${points.length} placed (Click to add more)`}
            </div>
          </div>

          <div className="flex justify-between items-center text-xs font-label-mono text-on-surface-variant px-1">
            <span>Points placed: {points.length}</span>
            {points.length > 0 && (
              <button
                onClick={handleReset}
                className="text-error hover:underline flex items-center gap-1 text-xs"
              >
                <RotateCcw className="w-3 h-3" /> Clear Points
              </button>
            )}
          </div>
        </div>

        {/* Right: Zone Configuration Form & List (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="bg-surface-container-low rounded-lg p-3.5 border border-outline-variant flex flex-col gap-3 font-label-mono text-xs">
            <h4 className="font-bold text-on-surface uppercase text-[11px]">New Zone Parameters</h4>

            <div>
              <label className="text-[10px] text-on-surface-variant block mb-1">Zone Name</label>
              <input
                type="text"
                value={zoneName}
                onChange={(e) => setZoneName(e.target.value)}
                placeholder="e.g. Hydraulic Press Zone"
                className="w-full p-2 rounded bg-surface border border-outline-variant text-on-surface text-xs focus:outline-none focus:border-primary font-bold"
              />
            </div>

            <div className="grid grid-cols-2 gap-2">
              <div>
                <label className="text-[10px] text-on-surface-variant block mb-1">Severity</label>
                <select
                  value={severity}
                  onChange={(e) => setSeverity(parseInt(e.target.value) || 80)}
                  className="w-full p-2 rounded bg-surface border border-outline-variant text-on-surface text-xs focus:outline-none"
                >
                  <option value={80}>80 (Critical)</option>
                  <option value={60}>60 (High)</option>
                  <option value={40}>40 (Medium)</option>
                </select>
              </div>

              <div>
                <label className="text-[10px] text-on-surface-variant block mb-1">Trigger Dwell</label>
                <select
                  value={warningDelay}
                  onChange={(e) => setWarningDelay(parseFloat(e.target.value) || 0.5)}
                  className="w-full p-2 rounded bg-surface border border-outline-variant text-on-surface text-xs focus:outline-none"
                >
                  <option value={0.0}>Instant (0.0s)</option>
                  <option value={0.5}>0.5 Seconds</option>
                  <option value={1.0}>1.0 Seconds</option>
                  <option value={2.0}>2.0 Seconds</option>
                </select>
              </div>
            </div>

            {statusMsg && (
              <div className="p-2 rounded bg-primary/10 border border-primary/30 text-primary text-[11px]">
                {statusMsg}
              </div>
            )}

            <button
              onClick={handleSaveZone}
              disabled={isSaving || points.length < 3}
              className={`w-full py-2 rounded font-label-mono-bold text-xs flex items-center justify-center gap-1.5 transition shadow-sm font-bold ${
                points.length >= 3
                  ? 'bg-primary hover:bg-primary/90 text-white cursor-pointer'
                  : 'bg-surface-container text-on-surface-variant opacity-50 cursor-not-allowed'
              }`}
            >
              <Save className="w-3.5 h-3.5" />
              Save No-Entry Zone
            </button>
          </div>

          {/* Active Saved Zones for Camera */}
          <div className="bg-surface-container-low rounded-lg p-3.5 border border-outline-variant flex flex-col gap-2 font-label-mono text-xs">
            <h4 className="font-bold text-on-surface uppercase text-[11px] flex justify-between items-center">
              <span>Configured Zones ({cameraZones.length})</span>
            </h4>

            {cameraZones.length === 0 ? (
              <p className="text-on-surface-variant text-[11px]">No restricted zones saved for this camera.</p>
            ) : (
              <div className="space-y-1.5 max-h-48 overflow-y-auto custom-scrollbar pr-1">
                {cameraZones.map((z) => (
                  <div
                    key={z.id}
                    className="flex items-center justify-between p-2 rounded bg-surface border border-outline-variant hover:border-primary/50 transition"
                  >
                    <div>
                      <div className="font-bold text-on-surface text-xs">{z.name}</div>
                      <div className="text-[10px] text-on-surface-variant">
                        {z.polygon?.length || 0} vertices • {z.severity}/100 Severity
                      </div>
                    </div>

                    <button
                      onClick={() => handleDeleteZone(z.id)}
                      className="p-1 text-error hover:bg-error-container/20 rounded transition"
                      title="Delete Zone"
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
