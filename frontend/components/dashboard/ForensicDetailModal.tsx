import React, { useState } from 'react';
import { SafetyEvent } from '@/types';
import { getMediaUrl } from '@/lib/api';
import { ShieldAlert, AlertTriangle, CheckCircle2, Flame, HardHat, Compass, Clock, User, MapPin, X } from 'lucide-react';

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
  const isAck = event.status === 'ACKNOWLEDGED';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 md:p-6 bg-black/75 backdrop-blur-sm animate-fade-in">
      <div className="bg-surface level-1-panel rounded-xl w-full max-w-4xl max-h-[92vh] overflow-hidden flex flex-col shadow-2xl border border-outline-variant">
        
        {/* Modal Header */}
        <div className={`px-4 py-3.5 border-b border-outline-variant flex items-center justify-between shrink-0 ${
          isCrit ? 'bg-error-container/25' : 'bg-surface-container-low'
        }`}>
          <div className="flex items-center gap-3 min-w-0">
            <span className={`material-symbols-outlined text-2xl shrink-0 ${isCrit ? 'text-error' : 'text-primary'}`}>
              {isCrit ? 'warning' : 'info'}
            </span>
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <h2 className="font-headline-md text-base font-bold text-on-surface truncate">
                  {event.primary_hazard.replace(/_/g, ' ')}
                </h2>
                <span className={`px-2 py-0.5 rounded font-label-mono-bold text-[10px] uppercase shrink-0 ${
                  isCrit
                    ? 'bg-error text-white font-bold'
                    : isHi
                    ? 'bg-severity-warning text-black font-bold'
                    : 'bg-primary text-white font-bold'
                }`}>
                  {event.severity}
                </span>
                {isAck && (
                  <span className="px-1.5 py-0.5 rounded bg-primary/15 text-primary text-[10px] font-mono font-bold shrink-0">
                    ACKNOWLEDGED
                  </span>
                )}
              </div>
              <p className="font-label-mono text-xs text-on-surface-variant truncate mt-0.5">
                Incident ID: {event.id} • Camera: {event.camera_id} • Subject: {event.worker_id > 0 ? `Worker #${event.worker_id.toString().padStart(2, '0')}` : 'Plant-Wide'}
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-surface-variant text-on-surface-variant hover:text-on-surface transition shrink-0 ml-2"
            title="Close Modal"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body: Scrollable with Custom Scrollbar */}
        <div className="p-4 md:p-6 overflow-y-auto custom-scrollbar flex-1 min-h-0 grid grid-cols-1 md:grid-cols-12 gap-5 font-label-mono text-xs">
          
          {/* Left: Forensic Snapshot (7 cols) */}
          <div className="md:col-span-7 flex flex-col gap-3">
            <h3 className="font-bold text-on-surface uppercase tracking-wider text-[11px] flex items-center gap-1.5">
              <span className="material-symbols-outlined text-sm text-primary">camera</span>
              Forensic Evidence Snapshot
            </h3>
            <div className="relative aspect-[16/10] bg-surface-container-low rounded-lg border border-outline-variant overflow-hidden shadow-inner">
              <img
                src={getMediaUrl(event.evidence_path)}
                alt="Forensic Snapshot"
                className="w-full h-full object-cover"
                onError={(e) => {
                  e.currentTarget.src = 'https://www.gstatic.com/labs-code/stitch/stitch-placeholder-300x300.svg';
                }}
              />
              <div className="absolute top-2 left-2 bg-black/80 backdrop-blur px-2.5 py-1 rounded text-[10px] text-white font-bold tracking-wider">
                EVIDENCE RECORD: {event.id}
              </div>
            </div>
            <div className="flex justify-between items-center text-[11px] text-on-surface-variant px-1">
              <span>Timestamp: {new Date(event.started_at).toLocaleTimeString()}</span>
              <span>Dwell Exposure: {event.exposure_seconds ? `${event.exposure_seconds.toFixed(1)}s` : '0.0s'}</span>
            </div>
          </div>

          {/* Right: Metrics & Rule Logic (5 cols) */}
          <div className="md:col-span-5 flex flex-col gap-3.5">
            
            {/* Risk Breakdown Box */}
            <div className="p-3.5 bg-surface-container-low rounded-lg border border-outline-variant space-y-2">
              <div className="flex justify-between items-center">
                <span className="font-bold text-on-surface uppercase text-[11px]">Compound Risk Score</span>
                <span className={`font-data-metric text-xl font-bold ${
                  isCrit ? 'text-severity-critical' : isHi ? 'text-severity-warning' : 'text-primary'
                }`}>
                  {event.risk_score} / 100
                </span>
              </div>
              <div className="w-full bg-surface-container h-2 rounded overflow-hidden">
                <div
                  className={`h-full rounded transition-all duration-500 ${isCrit ? 'bg-severity-critical' : 'bg-severity-warning'}`}
                  style={{ width: `${Math.min(100, Math.max(5, event.risk_score))}%` }}
                />
              </div>
            </div>

            {/* Rule Triggered */}
            <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant space-y-1">
              <span className="font-bold text-primary uppercase text-[10px] tracking-wider">Rule Logic Triggered:</span>
              <p className="text-on-surface text-xs leading-relaxed font-sans">
                {event.rule_triggered || 'Compound hazard threshold exceeded based on spatial proximity and duration exposure.'}
              </p>
            </div>

            {/* Recommended Action */}
            <div className="p-3 bg-surface-container-low rounded-lg border border-outline-variant space-y-1">
              <span className="font-bold text-severity-safe uppercase text-[10px] tracking-wider">Recommended Operator Action:</span>
              <p className="text-on-surface text-xs leading-relaxed font-sans">
                {event.recommended_action || 'Immediately halt machinery and instruct personnel to step outside restricted perimeter.'}
              </p>
            </div>

            {/* False Positive / Audit Section */}
            {showFpInput ? (
              <div className="space-y-2 pt-1">
                <textarea
                  value={fpNotes}
                  onChange={(e) => setFpNotes(e.target.value)}
                  placeholder="Enter operator audit notes for false positive..."
                  className="w-full p-2.5 bg-surface border border-outline-variant rounded-lg text-xs text-on-surface focus:outline-none focus:border-primary"
                  rows={2}
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => {
                      onMarkFalsePositive(event.id, fpNotes);
                      onClose();
                    }}
                    className="flex-1 py-1.5 bg-severity-warning text-black font-bold rounded-lg text-xs hover:bg-severity-warning/90 transition"
                  >
                    Confirm False Alarm
                  </button>
                  <button
                    onClick={() => setShowFpInput(false)}
                    className="px-3 py-1.5 bg-surface border border-outline-variant rounded-lg text-xs text-on-surface hover:bg-surface-variant transition"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowFpInput(true)}
                className="text-[11px] text-on-surface-variant hover:text-severity-warning text-left underline self-start pt-1"
              >
                Mark as False Alarm / AI Noise
              </button>
            )}

          </div>

        </div>

        {/* Modal Footer: Action Buttons */}
        <div className="px-4 py-3 border-t border-outline-variant bg-surface-container-low flex justify-end gap-2.5 shrink-0">
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-surface border border-outline-variant text-on-surface font-label-mono text-xs hover:bg-surface-container transition"
          >
            Close
          </button>
          {!isAck ? (
            <button
              onClick={() => {
                onAcknowledge(event.id);
              }}
              className="px-4 py-1.5 rounded-lg bg-primary text-white font-label-mono-bold text-xs hover:bg-primary/90 transition shadow-sm font-bold"
            >
              Acknowledge Incident
            </button>
          ) : null}
          <button
            onClick={() => {
              onResolve(event.id);
              onClose();
            }}
            className="px-4 py-1.5 rounded-lg bg-severity-safe text-white font-label-mono-bold text-xs hover:bg-severity-safe/90 transition shadow-sm font-bold"
          >
            Resolve &amp; Close
          </button>
        </div>

      </div>
    </div>
  );
};
