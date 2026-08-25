import React, { useState } from 'react';
import { Camera, Zone, Machine } from '@/types';
import { computeCalibration } from '@/lib/api';

interface SettingsTabProps {
  cameras: Camera[];
  zones: Zone[];
  machines: Machine[];
  onConfigSaved: () => void;
}

export const SettingsTab: React.FC<SettingsTabProps> = ({
  cameras,
  zones,
  machines,
  onConfigSaved,
}) => {
  const [selectedCamId, setSelectedCamId] = useState<string>(cameras[0]?.id || 'CAM_01');
  const [points, setPoints] = useState<Array<{ px: number; py: number; wx: number; wy: number }>>([
    { px: 200, py: 250, wx: 0.0, wy: 0.0 },
    { px: 580, py: 250, wx: 6.0, wy: 0.0 },
    { px: 640, py: 620, wx: 6.0, wy: 8.0 },
    { px: 150, py: 620, wx: 0.0, wy: 8.0 },
  ]);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [resultMsg, setResultMsg] = useState<string | null>(null);

  const handlePointChange = (index: number, field: 'wx' | 'wy', val: number) => {
    const updated = [...points];
    updated[index][field] = val;
    setPoints(updated);
  };

  const handleCompute = async () => {
    setIsCalibrating(true);
    setResultMsg(null);
    try {
      const imgPts = points.map((p) => [p.px, p.py]);
      const worldPts = points.map((p) => [p.wx, p.wy]);
      const res = await computeCalibration(selectedCamId, imgPts, worldPts);
      setResultMsg(res.message);
      onConfigSaved();
    } catch (e: any) {
      setResultMsg(`Calibration Error: ${e.message}`);
    } finally {
      setIsCalibrating(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="font-headline-md text-xl font-bold text-on-surface mb-1">
            System Configuration &amp; Calibration
          </h1>
          <p className="font-label-mono text-xs text-on-surface-variant">
            Camera planar homography calibration, spatial boundaries, and hardware interlock triggers.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter">
        {/* Left: 4-Point Homography Tool (8 cols) */}
        <div className="lg:col-span-8 level-1-panel rounded-lg p-panel-padding flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="font-label-mono text-xs font-bold text-on-surface uppercase tracking-wider">
              3x3 Planar Homography Ground Calibration
            </h3>
            <div className="flex items-center gap-2">
              <span className="font-label-mono text-xs text-on-surface-variant">Camera:</span>
              <select
                value={selectedCamId}
                onChange={(e) => setSelectedCamId(e.target.value)}
                className="bg-surface px-2.5 py-1 rounded border border-outline-variant font-label-mono text-xs text-on-surface focus:outline-none"
              >
                {cameras.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.id} — {c.name}
                  </option>
                ))}
              </select>
            </div>
          </div>

          <div className="space-y-2">
            {points.map((pt, idx) => (
              <div
                key={idx}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-2.5 bg-surface-container-low rounded border border-outline-variant font-label-mono text-xs"
              >
                <div className="flex items-center gap-2 font-bold text-primary">
                  <span className="w-5 h-5 rounded bg-primary text-white flex items-center justify-center text-[10px]">
                    P{idx + 1}
                  </span>
                  <span>Pixel: [{pt.px}px, {pt.py}px]</span>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-on-surface-variant">World X (m):</span>
                    <input
                      type="number"
                      step="0.5"
                      value={pt.wx}
                      onChange={(e) => handlePointChange(idx, 'wx', parseFloat(e.target.value) || 0)}
                      className="w-20 px-2 py-1 rounded bg-surface border border-outline-variant text-on-surface text-right focus:outline-none focus:border-primary"
                    />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-on-surface-variant">World Y (m):</span>
                    <input
                      type="number"
                      step="0.5"
                      value={pt.wy}
                      onChange={(e) => handlePointChange(idx, 'wy', parseFloat(e.target.value) || 0)}
                      className="w-20 px-2 py-1 rounded bg-surface border border-outline-variant text-on-surface text-right focus:outline-none focus:border-primary"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={handleCompute}
            disabled={isCalibrating}
            className="w-full flex items-center justify-center gap-2 py-2 rounded-DEFAULT bg-primary hover:bg-primary/90 text-white font-label-mono-bold text-xs shadow-sm transition"
          >
            <span className={`material-symbols-outlined text-sm ${isCalibrating ? 'animate-spin' : ''}`}>
              sync
            </span>
            Compute &amp; Apply 3x3 Homography Matrix
          </button>

          {resultMsg && (
            <div className={`p-2.5 rounded border text-xs font-label-mono flex items-center gap-2 ${
              resultMsg.includes('Error')
                ? 'bg-error-container text-error border-error/30'
                : 'bg-severity-safe/10 text-severity-safe border-severity-safe/30'
            }`}>
              <span className="material-symbols-outlined text-sm">
                {resultMsg.includes('Error') ? 'error' : 'check_circle'}
              </span>
              <span>{resultMsg}</span>
            </div>
          )}
        </div>

        {/* Right: Camera & System Info (4 cols) */}
        <div className="lg:col-span-4 flex flex-col gap-4">
          <div className="level-1-panel rounded-lg p-panel-padding flex flex-col gap-3 font-label-mono text-xs">
            <h3 className="font-bold text-on-surface uppercase tracking-wider">
              Connected Video Sources
            </h3>
            <div className="space-y-2">
              {cameras.map((c) => (
                <div key={c.id} className="p-2 bg-surface-container-low rounded border border-outline-variant flex justify-between items-center">
                  <div>
                    <div className="font-bold text-primary">{c.id}</div>
                    <div className="text-[10px] text-on-surface-variant">{c.name}</div>
                  </div>
                  <span className="px-1.5 py-0.5 rounded bg-severity-safe/10 text-severity-safe text-[10px] font-bold">
                    ONLINE
                  </span>
                </div>
              ))}
            </div>
          </div>

          <div className="level-1-panel rounded-lg p-panel-padding flex flex-col gap-2 font-label-mono text-xs">
            <span className="font-bold text-primary uppercase">Precision Notice</span>
            <p className="text-on-surface-variant leading-relaxed">
              When calibrated, distances are measured in ground-floor meters via <code>pixel_to_world(x,y)</code>. When uncalibrated, <code>PIXEL_DISTANCE_MODE</code> is automatically reported to maintain strict honesty.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
