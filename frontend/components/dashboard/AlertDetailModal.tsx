import React, { useState } from 'react';
import { X, ShieldAlert, CheckCircle2, AlertTriangle, User, MapPin, Clock, Compass, FileText, Check, AlertOctagon, ZoomIn } from 'lucide-react';
import { SafetyEvent } from '@/types';
import { getMediaUrl } from '@/lib/api';

interface AlertDetailModalProps {
  event: SafetyEvent | null;
  onClose: () => void;
  onAcknowledge: (id: string) => Promise<void>;
  onResolve: (id: string) => Promise<void>;
  onMarkFalsePositive: (id: string, notes: string) => Promise<void>;
}

export const AlertDetailModal: React.FC<AlertDetailModalProps> = ({
  event,
  onClose,
  onAcknowledge,
  onResolve,
  onMarkFalsePositive,
}) => {
  const [notes, setNotes] = useState('');
  const [isZoomed, setIsZoomed] = useState(false);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  if (!event) return null;

  const isCritical = event.severity === 'CRITICAL';
  const isHigh = event.severity === 'HIGH';
  const evidenceUrl = event.evidence_path ? getMediaUrl(event.evidence_path) : null;

  const handleAction = async (action: 'ack' | 'resolve' | 'fp') => {
    setLoadingAction(action);
    try {
      if (action === 'ack') await onAcknowledge(event.id);
      else if (action === 'resolve') await onResolve(event.id);
      else if (action === 'fp') await onMarkFalsePositive(event.id, notes);
      onClose();
    } catch (e) {
      console.error('Error performing action:', e);
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-sm animate-in fade-in">
      <div className="relative w-full max-w-4xl max-h-[90vh] flex flex-col bg-industrial-900 border border-industrial-border rounded-xl shadow-2xl overflow-hidden">
        
        {/* Modal Header */}
        <div className={`flex items-center justify-between px-6 py-4 border-b ${
          isCritical
            ? 'bg-hazard-critical/15 border-hazard-critical/40 text-hazard-critical'
            : isHigh
            ? 'bg-hazard-high/15 border-hazard-high/40 text-hazard-high'
            : 'bg-industrial-850 border-industrial-border text-slate-200'
        }`}>
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-black/40 border border-current">
              <ShieldAlert className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="font-mono font-bold text-base tracking-wider uppercase text-white">
                  {event.primary_hazard.replace(/_/g, ' ')}
                </h2>
                <span className="text-xs font-mono px-2 py-0.5 rounded bg-black/50 border border-current font-bold">
                  {event.severity}
                </span>
                <span className="text-xs font-mono text-slate-300">
                  {event.id}
                </span>
              </div>
              <p className="text-xs text-slate-300 mt-0.5">
                Investigate Forensic Evidence & Safety Recommendations
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-black/40 hover:bg-black/70 text-slate-300 hover:text-white border border-industrial-border transition"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-6 grid grid-cols-1 md:grid-cols-12 gap-6">
          
          {/* Left Column: Forensic Evidence Snapshot */}
          <div className="md:col-span-7 flex flex-col gap-3">
            <div className="flex items-center justify-between text-xs font-mono text-slate-300">
              <span className="flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-cyan-400" /> FORENSIC SNAPSHOT EVIDENCE
              </span>
              {evidenceUrl && (
                <button
                  onClick={() => setIsZoomed(!isZoomed)}
                  className="flex items-center gap-1 text-cyan-400 hover:underline"
                >
                  <ZoomIn className="w-3 h-3" /> {isZoomed ? 'Reset Zoom' : 'Enlarge'}
                </button>
              )}
            </div>

            <div className="relative rounded-lg overflow-hidden border border-industrial-border bg-black aspect-video flex items-center justify-center">
              {evidenceUrl ? (
                <img
                  src={evidenceUrl}
                  alt={`Evidence for ${event.id}`}
                  className={`w-full h-full object-contain transition-transform duration-300 ${
                    isZoomed ? 'scale-150 cursor-zoom-out' : 'cursor-zoom-in'
                  }`}
                  onClick={() => setIsZoomed(!isZoomed)}
                />
              ) : (
                <div className="flex flex-col items-center justify-center p-8 text-slate-500">
                  <AlertOctagon className="w-10 h-10 mb-2 opacity-50" />
                  <p className="text-xs font-mono">Live video stream frame captured</p>
                  <p className="text-[11px] text-slate-600 mt-1">Snapshot evidence stored in forensic database</p>
                </div>
              )}
            </div>

            {/* Rule Triggered Info Box */}
            <div className="p-3.5 rounded-lg bg-industrial-950 border border-industrial-border/80 text-xs">
              <span className="font-mono text-[10px] text-cyan-400 font-bold uppercase block mb-1">
                RULE LOGIC TRIGGERED:
              </span>
              <p className="font-mono text-slate-300 leading-relaxed">
                {event.rule_triggered || 'Compound spatial and temporal hazard rule evaluated.'}
              </p>
            </div>
          </div>

          {/* Right Column: Telemetry, Risk Breakdown & Operational Actions */}
          <div className="md:col-span-5 flex flex-col gap-4">
            
            {/* 0-100 Compound Risk Badge */}
            <div className="p-4 rounded-xl bg-industrial-950 border border-industrial-border">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-mono text-slate-400">COMPOUND RISK SCORE</span>
                <span className={`text-xl font-mono font-bold ${
                  isCritical ? 'text-hazard-critical' : isHigh ? 'text-hazard-high' : 'text-amber-400'
                }`}>
                  {event.risk_score} <span className="text-xs text-slate-500 font-normal">/ 100</span>
                </span>
              </div>
              <div className="w-full h-2.5 rounded-full bg-industrial-800 overflow-hidden">
                <div
                  className={`h-full transition-all duration-500 ${
                    isCritical ? 'bg-hazard-critical' : isHigh ? 'bg-hazard-high' : 'bg-hazard-medium'
                  }`}
                  style={{ width: `${Math.min(100, event.risk_score)}%` }}
                />
              </div>
            </div>

            {/* Incident Context Matrix */}
            <div className="space-y-2 text-xs font-mono bg-industrial-850 p-3.5 rounded-lg border border-industrial-border">
              <div className="flex items-center justify-between py-1 border-b border-industrial-border/60">
                <span className="text-slate-400 flex items-center gap-1.5"><User className="w-3.5 h-3.5 text-cyan-400" /> Target:</span>
                <strong className="text-slate-100">Worker #{event.worker_id.toString().padStart(2, '0')}</strong>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-industrial-border/60">
                <span className="text-slate-400 flex items-center gap-1.5"><MapPin className="w-3.5 h-3.5 text-cyan-400" /> Location:</span>
                <strong className="text-slate-100">{event.camera_id}</strong>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-industrial-border/60">
                <span className="text-slate-400 flex items-center gap-1.5"><Clock className="w-3.5 h-3.5 text-amber-400" /> Exposure Time:</span>
                <strong className="text-amber-300">{event.exposure_seconds.toFixed(1)} seconds</strong>
              </div>

              <div className="flex items-center justify-between py-1 border-b border-industrial-border/60">
                <span className="text-slate-400 flex items-center gap-1.5"><Compass className="w-3.5 h-3.5 text-cyan-400" /> Metric Distance:</span>
                <strong className="text-slate-100">{event.distance_m ? `${event.distance_m} meters` : 'Metric Uncalibrated'}</strong>
              </div>

              <div className="flex items-center justify-between py-1">
                <span className="text-slate-400">AI Confidence:</span>
                <strong className="text-emerald-400">{(event.confidence * 100).toFixed(0)}%</strong>
              </div>
            </div>

            {/* Recommended Safety Action */}
            <div className="p-3.5 rounded-lg bg-cyan-950/40 border border-cyan-500/40 text-xs">
              <span className="font-mono text-[10px] text-cyan-300 font-bold uppercase block mb-1">
                RECOMMENDED OPERATOR ACTION:
              </span>
              <p className="text-slate-200 font-medium leading-relaxed">
                {event.recommended_action || 'Inspect area and ensure operator compliance.'}
              </p>
            </div>

            {/* False Positive Notes Input */}
            <div className="flex flex-col gap-1.5">
              <label className="text-[11px] font-mono text-slate-400">Resolution / Audit Notes:</label>
              <input
                type="text"
                placeholder="Optional notes for safety audit log..."
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                className="px-3 py-1.5 rounded bg-industrial-950 border border-industrial-border text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
              />
            </div>

          </div>
        </div>

        {/* Modal Footer Controls */}
        <div className="flex items-center justify-between px-6 py-3.5 bg-industrial-950 border-t border-industrial-border">
          <button
            onClick={() => handleAction('fp')}
            disabled={loadingAction !== null}
            className="px-3 py-1.5 rounded bg-industrial-800 hover:bg-industrial-700 text-slate-400 hover:text-slate-200 border border-slate-700 text-xs font-mono transition"
          >
            Mark False Positive
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={() => handleAction('ack')}
              disabled={loadingAction !== null || event.status === 'ACKNOWLEDGED'}
              className={`px-4 py-2 rounded text-xs font-semibold font-mono border transition ${
                event.status === 'ACKNOWLEDGED'
                  ? 'bg-industrial-800 text-slate-500 border-industrial-border cursor-not-allowed'
                  : 'bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border-amber-500/50'
              }`}
            >
              {event.status === 'ACKNOWLEDGED' ? 'Already Acknowledged' : 'Acknowledge Event'}
            </button>

            <button
              onClick={() => handleAction('resolve')}
              disabled={loadingAction !== null}
              className="flex items-center gap-1.5 px-5 py-2 rounded bg-emerald-600 hover:bg-emerald-500 text-white font-mono font-bold text-xs shadow-lg transition"
            >
              <Check className="w-4 h-4" /> Resolve Hazard
            </button>
          </div>
        </div>

      </div>
    </div>
  );
};
