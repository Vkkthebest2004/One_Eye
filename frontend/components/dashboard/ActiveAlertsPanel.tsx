import React from 'react';
import { AlertOctagon, CheckCircle2, Clock, MapPin, User, ShieldAlert, ArrowUpRight, Flame, HardHat, Compass } from 'lucide-react';
import { SafetyEvent } from '@/types';

interface ActiveAlertsPanelProps {
  alerts: SafetyEvent[];
  onSelectEvent: (event: SafetyEvent) => void;
  onAcknowledge: (eventId: string) => void;
  onResolve: (eventId: string) => void;
}

export const ActiveAlertsPanel: React.FC<ActiveAlertsPanelProps> = ({
  alerts,
  onSelectEvent,
  onAcknowledge,
  onResolve,
}) => {
  return (
    <div className="flex flex-col h-full bg-industrial-900 rounded-xl border border-industrial-border overflow-hidden">
      {/* Panel Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-industrial-border bg-industrial-850">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-hazard-critical animate-ping" />
          <h2 className="font-mono font-bold text-xs uppercase tracking-wider text-slate-200">
            Priority Alert Queue ({alerts.length})
          </h2>
        </div>
        <span className="text-[11px] font-mono text-slate-400">Live Dispatch</span>
      </div>

      {/* Alerts List */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {alerts.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-48 text-center p-6 border border-dashed border-industrial-border rounded-lg text-slate-500">
            <CheckCircle2 className="w-8 h-8 text-emerald-500/60 mb-2" />
            <p className="font-mono text-sm font-semibold text-slate-300">All Zones Nominal</p>
            <p className="text-xs text-slate-500 mt-1">No active critical or high-risk hazard events detected.</p>
          </div>
        ) : (
          alerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onSelect={() => onSelectEvent(alert)}
              onAcknowledge={() => onAcknowledge(alert.id)}
              onResolve={() => onResolve(alert.id)}
            />
          ))
        )}
      </div>
    </div>
  );
};

interface AlertCardProps {
  alert: SafetyEvent;
  onSelect: () => void;
  onAcknowledge: () => void;
  onResolve: () => void;
}

const AlertCard: React.FC<AlertCardProps> = ({
  alert,
  onSelect,
  onAcknowledge,
  onResolve,
}) => {
  const isCritical = alert.severity === 'CRITICAL';
  const isHigh = alert.severity === 'HIGH';
  const isAcknowledged = alert.status === 'ACKNOWLEDGED';

  const severityBg = isCritical
    ? 'bg-hazard-critical/15 border-hazard-critical/60 glow-critical'
    : isHigh
    ? 'bg-hazard-high/15 border-hazard-high/60 glow-high'
    : 'bg-hazard-medium/15 border-hazard-medium/50';

  const badgeColor = isCritical
    ? 'bg-hazard-critical text-white'
    : isHigh
    ? 'bg-hazard-high text-black font-bold'
    : 'bg-hazard-medium text-black font-bold';

  const getHazardIcon = (hazard: string) => {
    if (hazard.includes('FIRE') || hazard.includes('SMOKE')) return <Flame className="w-3.5 h-3.5" />;
    if (hazard.includes('HELMET') || hazard.includes('PPE')) return <HardHat className="w-3.5 h-3.5" />;
    if (hazard.includes('PROXIMITY')) return <Compass className="w-3.5 h-3.5" />;
    return <AlertOctagon className="w-3.5 h-3.5" />;
  };

  return (
    <div
      className={`flex flex-col p-3 rounded-lg border transition-all duration-200 ${severityBg}`}
    >
      {/* Top Tag & Risk Score */}
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5">
          <span className={`text-[10px] uppercase font-mono px-2 py-0.5 rounded font-bold tracking-wider ${badgeColor}`}>
            {alert.severity}
          </span>
          <span className="text-[11px] font-mono text-slate-400">
            {alert.id}
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          <span className="text-[11px] font-mono text-slate-400">RISK:</span>
          <span className={`text-xs font-mono font-bold px-1.5 py-0.5 rounded ${
            isCritical ? 'bg-hazard-critical/30 text-hazard-critical' : 'bg-amber-500/30 text-amber-300'
          }`}>
            {alert.risk_score}/100
          </span>
        </div>
      </div>

      {/* Hazard Title & Worker */}
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <h3 className="font-semibold text-xs text-white flex items-center gap-1.5">
            {getHazardIcon(alert.primary_hazard)}
            {alert.primary_hazard.replace(/_/g, ' ')}
          </h3>
          <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-2">
            <span className="flex items-center gap-1">
              <User className="w-3 h-3 text-cyan-400" /> Worker #{alert.worker_id.toString().padStart(2, '0')}
            </span>
            <span>•</span>
            <span className="flex items-center gap-1">
              <MapPin className="w-3 h-3 text-cyan-400" /> {alert.camera_id}
            </span>
          </p>
        </div>
      </div>

      {/* Telemetry Metrics: Distance & Exposure */}
      <div className="grid grid-cols-2 gap-2 bg-industrial-950/70 p-2 rounded border border-industrial-border/60 text-[11px] font-mono mb-2.5">
        <div className="flex items-center gap-1 text-slate-300">
          <Clock className="w-3 h-3 text-amber-400" />
          <span>Exposure: <strong>{alert.exposure_seconds.toFixed(1)}s</strong></span>
        </div>
        <div className="flex items-center gap-1 text-slate-300">
          <Compass className="w-3 h-3 text-cyan-400" />
          <span>Dist: <strong>{alert.distance_m ? `${alert.distance_m}m` : 'N/A'}</strong></span>
        </div>
      </div>

      {/* Actions */}
      <div className="flex items-center gap-1.5 pt-1 border-t border-industrial-border/40">
        <button
          onClick={onSelect}
          className="flex-1 flex items-center justify-center gap-1 px-2.5 py-1 rounded bg-industrial-800 hover:bg-industrial-700 text-slate-200 border border-slate-700 text-xs font-medium transition"
        >
          <span>Evidence</span>
          <ArrowUpRight className="w-3 h-3" />
        </button>

        {!isAcknowledged ? (
          <button
            onClick={onAcknowledge}
            className="flex-1 px-2.5 py-1 rounded bg-amber-500/20 hover:bg-amber-500/30 text-amber-300 border border-amber-500/50 text-xs font-medium transition"
          >
            Acknowledge
          </button>
        ) : (
          <button
            onClick={onResolve}
            className="flex-1 px-2.5 py-1 rounded bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-300 border border-emerald-500/50 text-xs font-medium transition"
          >
            Resolve
          </button>
        )}
      </div>
    </div>
  );
};
