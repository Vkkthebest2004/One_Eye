import React, { useState, useRef } from 'react';
import { Settings, Compass, CheckCircle2, AlertCircle, RefreshCw, Layers } from 'lucide-react';
import { Camera } from '@/types';
import { computeCalibration } from '@/lib/api';

interface CalibrationToolProps {
  cameras: Camera[];
  onCalibrationSaved: () => void;
}

export const CalibrationTool: React.FC<CalibrationToolProps> = ({ cameras, onCalibrationSaved }) => {
  const [selectedCamId, setSelectedCamId] = useState<string>(cameras[0]?.id || 'CAM_01');
  const [points, setPoints] = useState<Array<{ px: number; py: number; wx: number; wy: number }>>([
    { px: 200, py: 250, wx: 0.0, wy: 0.0 },
    { px: 580, py: 250, wx: 6.0, wy: 0.0 },
    { px: 640, py: 620, wx: 6.0, wy: 8.0 },
    { px: 150, py: 620, wx: 0.0, wy: 8.0 },
  ]);
  const [isCalibrating, setIsCalibrating] = useState(false);
  const [resultMsg, setResultMsg] = useState<string | null>(null);
  const [matrixResult, setMatrixResult] = useState<number[][] | null>(null);

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
      setMatrixResult(res.matrix);
      onCalibrationSaved();
    } catch (e: any) {
      setResultMsg(`Calibration Error: ${e.message}`);
    } finally {
      setIsCalibrating(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 p-1">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-industrial-900 p-4 rounded-xl border border-industrial-border">
        <div>
          <h2 className="text-base font-mono font-bold text-white flex items-center gap-2">
            <Compass className="w-5 h-5 text-cyan-400" />
            CAMERA 3x3 PLANAR HOMOGRAPHY CALIBRATION
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Calibrate 4 ground-plane floor points to transform camera pixels into real-world metric distances (meters)
          </p>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs font-mono text-slate-400">Select Camera:</span>
          <select
            value={selectedCamId}
            onChange={(e) => setSelectedCamId(e.target.value)}
            className="bg-industrial-950 px-3 py-1.5 rounded border border-industrial-border text-xs font-mono text-cyan-300 font-bold focus:outline-none"
          >
            {cameras.map((c) => (
              <option key={c.id} value={c.id}>
                {c.id} — {c.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        
        {/* Left: 4 Reference Points Input Table */}
        <div className="lg:col-span-7 bg-industrial-900 p-5 rounded-xl border border-industrial-border flex flex-col gap-4">
          <div className="flex items-center justify-between">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
              Ground Plane Calibration Coordinates
            </h3>
            <span className="text-[11px] font-mono text-amber-400">4 Points Required</span>
          </div>

          <div className="space-y-3">
            {points.map((pt, idx) => (
              <div
                key={idx}
                className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 p-3 bg-industrial-950 rounded-lg border border-industrial-border text-xs font-mono"
              >
                <div className="flex items-center gap-2 font-bold text-cyan-400">
                  <span className="w-5 h-5 rounded-full bg-cyan-950 border border-cyan-500 flex items-center justify-center text-[10px]">
                    P{idx + 1}
                  </span>
                  <span>Pixel: [{pt.px}px, {pt.py}px]</span>
                </div>

                <div className="flex items-center gap-3">
                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">World X (m):</span>
                    <input
                      type="number"
                      step="0.5"
                      value={pt.wx}
                      onChange={(e) => handlePointChange(idx, 'wx', parseFloat(e.target.value) || 0)}
                      className="w-20 px-2 py-1 rounded bg-industrial-900 border border-industrial-border text-white text-right focus:outline-none focus:border-cyan-500"
                    />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <span className="text-slate-400">World Y (m):</span>
                    <input
                      type="number"
                      step="0.5"
                      value={pt.wy}
                      onChange={(e) => handlePointChange(idx, 'wy', parseFloat(e.target.value) || 0)}
                      className="w-20 px-2 py-1 rounded bg-industrial-900 border border-industrial-border text-white text-right focus:outline-none focus:border-cyan-500"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={handleCompute}
            disabled={isCalibrating}
            className="w-full flex items-center justify-center gap-2 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-mono font-bold text-xs shadow-lg transition"
          >
            <RefreshCw className={`w-4 h-4 ${isCalibrating ? 'animate-spin' : ''}`} />
            Compute & Apply 3x3 Homography Matrix
          </button>

          {resultMsg && (
            <div className={`p-3 rounded-lg border text-xs font-mono flex items-start gap-2 ${
              resultMsg.includes('Error')
                ? 'bg-red-500/15 border-red-500/40 text-red-300'
                : 'bg-emerald-500/15 border-emerald-500/40 text-emerald-300'
            }`}>
              <CheckCircle2 className="w-4 h-4 shrink-0 mt-0.5" />
              <span>{resultMsg}</span>
            </div>
          )}
        </div>

        {/* Right: Matrix & Mode Explanation */}
        <div className="lg:col-span-5 flex flex-col gap-4">
          
          <div className="bg-industrial-900 p-5 rounded-xl border border-industrial-border flex flex-col gap-3">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <Layers className="w-4 h-4 text-cyan-400" />
              Computed 3x3 Transformation Matrix (H)
            </h3>

            {matrixResult ? (
              <div className="p-3 bg-industrial-950 rounded-lg border border-industrial-border font-mono text-[11px] text-cyan-300 space-y-1">
                {matrixResult.map((row, rIdx) => (
                  <div key={rIdx} className="flex justify-between">
                    {row.map((val, cIdx) => (
                      <span key={cIdx} className="w-24 text-right">{val.toFixed(5)}</span>
                    ))}
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 bg-industrial-950 rounded-lg border border-dashed border-industrial-border text-center text-xs font-mono text-slate-500">
                Click "Compute & Apply" to calculate H matrix.
              </div>
            )}
          </div>

          <div className="bg-industrial-850 p-4 rounded-xl border border-industrial-border text-xs leading-relaxed text-slate-300">
            <span className="font-mono font-bold text-cyan-400 uppercase block mb-1">
              PROXIMITY ENGINE GUARANTEE:
            </span>
            <p>
              When a camera is calibrated, worker-to-machine distances are mathematically resolved in ground-floor meters via <code>pixel_to_world(x, y)</code>. If uncalibrated, the safety engine explicitly reports <code>PIXEL_DISTANCE_MODE</code> to prevent false claims of metric precision.
            </p>
          </div>

        </div>

      </div>
    </div>
  );
};
