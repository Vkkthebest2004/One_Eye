import React, { useState } from 'react';
import { SafetyEvent } from '@/types';

interface ForensicDetailModalProps {
  event: SafetyEvent | null;
  onClose: () => void;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
  onMarkFalsePositive: (id: string, notes: string) => void;
}

export const ForensicDetailModal: React.FC<ForensicDetailModalProps> = ({
  event,
  onClose,
  onAcknowledge,
  onResolve,
  onMarkFalsePositive,
}) => {
  const [fpNotes, setFpNotes] = useState('');
  const [showFpInput, setShowFpInput] = useState(false);

  if (!event) return null;

  const isCrit = event.severity === 'CRITICAL';
  const isHi = event.severity === 'HIGH';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
      <div className="bg-surface level-1-panel rounded-lg w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col shadow-2xl">
        
        {/* Modal Header */}
        <div className={`p-4 border-b border-outline-variant flex items-center justify-between ${
          isCrit ? 'bg-error-container/20' : 'bg-surface-container-low'
        }`}>
          <div className="flex items-center gap-3">
            <span className={`material-symbols-outlined text-2xl ${isCrit ? 'text-error' : 'text-primary'}`}>
              {isCrit ? 'warning' : 'info'}
            </span>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-headline-md text-base font-bold text-on-surface">
                  {event.primary_hazard.replace(/_/g, ' ')}
                </h2>
                <span className={`px-2 py-0.5 rounded font-label-mono-bold text-[10px] ${
                  isCrit
                    ? 'bg-error text-white'
                    : isHi
                    ? 'bg-severity-warning text-white'
                    : 'bg-primary text-white'
                }`}>
                  {event.severity}
                </span>
              </div>
              <p className="font-label-mono text-xs text-on-surface-variant">
                Incident ID: {event.id} • Camera: {event.camera_id} • Target: Worker #{event.worker_id.toString().padStart(2, '0')}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded hover:bg-surface-variant text-on-surface-variant transition"
          >
            <span className="material-symbols-outlined text-xl">close</span>
          </button>
        </div>

        {/* Modal Body */}
        <div className="p-5 overflow-y-auto grid grid-cols-1 md:grid-cols-12 gap-5 font-label-mono text-xs">
          
          {/* Left: Forensic Snapshot (7 cols) */}
          <div className="md:col-span-7 flex flex-col gap-3">
            <h3 className="font-bold text-on-surface uppercase tracking-wider">
              Forensic Evidence Snapshot
            </h3>
            <div className="relative aspect-[16/10] bg-surface-container-low rounded border border-outline-variant overflow-hidden">
              <img
                src={`http://localhost:8001${event.evidence_path}`}
                alt="Forensic Snapshot"
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.src = 'https://www.gstatic.com/labs-code/stitch/stitch-placeholder-300x300.svg';
                }}
              />
              <div className="absolute top-2 left-2 bg-black/70 backdrop-blur px-2 py-0.5 rounded text-[10px] text-white font-bold">
                EVIDENCE ID: {event.id}
              </div>
            </div>
            <p className="text-[11px] text-on-surface-variant">
              Timestamp: {new Date(event.started_at).toISOString()} • Exposure: {event.exposure_seconds.toFixed(1)}s
            </p>
          </div>

          {/* Right: Metrics & Risk Assessment (5 cols) */}
          <div className="md:col-span-5 flex flex-col gap-4">
            
            {/* Risk Breakdown Box */}
            <div className="p-3 bg-surface-container-low rounded border border-outline-variant space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-bold text-on-surface uppercase">Compound Risk Score</span>
                <span className={`font-data-metric text-xl font-bold ${
                  isCrit ? 'text-severity-critical' : isHi ? 'text-severity-warning' : 'text-primary'
                }`}>
                  {event.risk_score} / 100
                </span>
              </div>
              <div className="w-full bg-surface-container h-1.5 rounded overflow-hidden">
                <div
                  className={`h-full ${isCrit ? 'bg-severity-critical' : 'bg-severity-warning'}`}
                  style={{ width: `${event.risk_score}%` }}
                />
              </div>
            </div>

            {/* Rule Triggered */}
            <div className="p-3 bg-surface-container-low rounded border border-outline-variant space-y-1">
              <span className="font-bold text-primary uppercase text-[11px]">Rule Logic Triggered:</span>
              <p className="text-on-surface text-xs leading-relaxed font-sans">
                {event.rule_triggered || 'Compound hazard threshold exceeded based on spatial proximity and duration exposure.'}
              </p>
            </div>

            {/* Recommended Action */}
            <div className="p-3 bg-surface-container-low rounded border border-outline-variant space-y-1">
              <span className="font-bold text-severity-safe uppercase text-[11px]">Recommended Operator Action:</span>
              <p className="text-on-surface text-xs leading-relaxed font-sans">
                {event.recommended_action || 'Immediately halt machinery and instruct personnel to step outside restricted perimeter.'}
              </p>
            </div>

            {/* False Positive Section */}
            {showFpInput ? (
              <div className="space-y-2 pt-2">
                <textarea
                  value={fpNotes}
                  onChange={(e) => setFpNotes(e.target.value)}
                  placeholder="Enter audit notes for false positive..."
                  className="w-full p-2 bg-surface border border-outline-variant rounded text-xs text-on-surface focus:outline-none focus:border-primary"
                  rows={2}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => onMarkFalsePositive(event.id, fpNotes)}
                    className="flex-1 py-1.5 bg-severity-warning text-white rounded font-label-mono-bold text-xs"
                  >
                    Confirm False Positive
                  </button>
                  <button
                    onClick={() => setShowFpInput(false)}
                    className="px-3 py-1.5 bg-surface border border-outline-variant rounded text-xs"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowFpInput(true)}
                className="text-[11px] text-on-surface-variant hover:text-severity-warning text-left underline"
              >
                Mark as False Positive / AI Noise
              </button>
            )}

          </div>

        </div>

        {/* Modal Footer */}
        <div className="p-3 border-t border-outline-variant bg-surface-container-low flex justify-end gap-2">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded bg-surface border border-outline-variant text-on-surface font-label-mono text-xs hover:bg-surface-container transition"
          >
            Close
          </button>
          <button
            onClick={() => onAcknowledge(event.id)}
            className="px-4 py-1.5 rounded bg-primary text-white font-label-mono-bold text-xs hover:bg-primary/90 transition"
          >
            Acknowledge Incident
          </button>
          <button
            onClick={() => onResolve(event.id)}
            className="px-4 py-1.5 rounded bg-severity-safe text-white font-label-mono-bold text-xs hover:bg-severity-safe/90 transition"
          >
            Resolve &amp; Close
          </button>
        </div>

      </div>
    </div>
  );
};
