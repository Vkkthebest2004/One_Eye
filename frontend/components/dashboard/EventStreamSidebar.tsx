import React from 'react';
import { SafetyEvent } from '@/types';
import { ShieldAlert, CheckCircle2, Clock, Compass, ArrowUpRight, Flame, HardHat } from 'lucide-react';

interface EventStreamSidebarProps {
  alerts: SafetyEvent[];
  onSelectEvent: (event: SafetyEvent) => void;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
}

export const EventStreamSidebar: React.FC<EventStreamSidebarProps> = ({
  alerts,
  onSelectEvent,
  onAcknowledge,
  onResolve,
}) => {
  // Priority sort: CRITICAL > HIGH > MEDIUM > ADVISORY
  const priorityMap: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, ADVISORY: 1 };
  const sortedAlerts = [...alerts].sort(
    (a, b) => (priorityMap[b.severity] || 0) - (priorityMap[a.severity] || 0)
  );

  const criticalAlert = sortedAlerts.find((a) => a.severity === 'CRITICAL');
  const otherAlerts = sortedAlerts.filter((a) => a.id !== criticalAlert?.id);

  const getHazardIcon = (hazard: string) => {
    if (hazard.includes('FIRE') || hazard.includes('SMOKE')) return <Flame className="w-3.5 h-3.5 text-severity-critical" />;
    if (hazard.includes('HELMET') || hazard.includes('PPE')) return <HardHat className="w-3.5 h-3.5 text-severity-warning" />;
    if (hazard.includes('PROXIMITY')) return <Compass className="w-3.5 h-3.5 text-primary" />;
    return <ShieldAlert className="w-3.5 h-3.5 text-severity-critical" />;
  };

  return (
    <div className="flex flex-col h-[600px] lg:h-[calc(100vh-210px)] max-h-[calc(100vh-210px)] min-h-[480px] w-full">
      {/* Header (Fixed) */}
      <div className="flex justify-between items-center mb-2 px-1 shrink-0">
        <h3 className="font-label-mono text-xs font-bold text-on-surface-variant uppercase tracking-widest flex items-center gap-2 font-bold">
          <span className="material-symbols-outlined text-sm text-primary">receipt_long</span>
          Active Hazards &amp; Incident Queue
        </h3>
        <span className={`font-label-mono text-[10px] px-2 py-0.5 rounded font-bold ${
          alerts.length > 0
            ? 'bg-severity-warning/15 text-severity-warning border border-severity-warning/40 animate-pulse'
            : 'bg-severity-safe/10 text-severity-safe border border-severity-safe/30'
        }`}>
          {alerts.length} Active
        </span>
      </div>

      {/* Main Events Container (Rigid Box) */}
      <div className="level-1-panel rounded-lg flex-1 overflow-hidden flex flex-col shadow-sm min-h-0 border border-outline-variant bg-surface">
        {/* Pinned Critical Alert Hero Card */}
        {criticalAlert ? (
          <div
            onClick={() => onSelectEvent(criticalAlert)}
            className="p-3 border-b border-outline-variant border-l-4 border-l-severity-critical bg-error-container/20 relative cursor-pointer group hover:bg-error-container/30 transition-colors shrink-0"
          >
            <div className="absolute top-2 right-2 text-severity-critical animate-pulse">
              <span className="material-symbols-outlined text-sm">my_location</span>
            </div>

            <div className="flex items-center gap-2 mb-1">
              <span className="font-label-mono-bold text-[10px] px-1.5 py-0.5 rounded bg-severity-critical text-white tracking-widest shadow-sm">
                {criticalAlert.severity}
              </span>
              <span className="font-label-mono text-[10px] text-on-surface-variant">
                {criticalAlert.status}
              </span>
            </div>

            <h4 className="font-body-sm text-sm font-semibold text-on-surface leading-tight mb-1 flex items-center gap-1.5 truncate">
              {getHazardIcon(criticalAlert.primary_hazard)}
              {criticalAlert.primary_hazard.replace(/_/g, ' ')}
            </h4>
            <p className="font-label-mono text-xs text-on-surface-variant mb-2 truncate">
              {criticalAlert.worker_id > 0 ? `Worker #${criticalAlert.worker_id.toString().padStart(2, '0')}` : 'Plant-Wide'} in {criticalAlert.camera_id}.
            </p>

            <div className="grid grid-cols-2 gap-1.5 mb-2.5">
              <div className="bg-surface-container-lowest border border-outline-variant rounded p-1 flex flex-col">
                <span className="font-label-mono text-[9px] text-on-surface-variant">SOURCE</span>
                <span className="font-label-mono-bold text-xs text-on-surface truncate">{criticalAlert.camera_id}</span>
              </div>
              <div className="bg-surface-container-lowest border border-outline-variant rounded p-1 flex flex-col">
                <span className="font-label-mono text-[9px] text-on-surface-variant">RISK INDEX</span>
                <span className="font-label-mono-bold text-xs text-severity-critical">
                  {criticalAlert.risk_score}/100
                </span>
              </div>
            </div>

            <div className="flex gap-2">
              {criticalAlert.status !== 'ACKNOWLEDGED' ? (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onAcknowledge(criticalAlert.id);
                  }}
                  className="flex-1 bg-severity-critical hover:bg-severity-critical/90 text-white font-label-mono-bold text-xs py-1.5 rounded transition-colors flex items-center justify-center gap-1 shadow-sm font-bold"
                >
                  <span className="material-symbols-outlined text-sm">check</span>
                  Acknowledge
                </button>
              ) : (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onResolve(criticalAlert.id);
                  }}
                  className="flex-1 bg-severity-safe hover:bg-severity-safe/90 text-white font-label-mono-bold text-xs py-1.5 rounded transition-colors flex items-center justify-center gap-1 shadow-sm font-bold"
                >
                  <span className="material-symbols-outlined text-sm">done_all</span>
                  Resolve
                </button>
              )}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectEvent(criticalAlert);
                }}
                className="px-2.5 py-1.5 rounded bg-surface border border-outline-variant hover:bg-surface-variant font-label-mono text-xs text-on-surface transition-colors flex items-center gap-1"
              >
                <span>Evidence</span>
                <ArrowUpRight className="w-3 h-3" />
              </button>
            </div>
          </div>
        ) : null}

        {/* Scrollable Secondary Alerts List with Smooth Custom Scrollbar */}
        <div className="flex-1 min-h-0 overflow-y-auto custom-scrollbar divide-y divide-outline-variant/60">
          {otherAlerts.length > 0 ? (
            otherAlerts.map((w) => (
              <div
                key={w.id}
                onClick={() => onSelectEvent(w)}
                className={`p-3 border-l-4 transition-colors cursor-pointer bg-surface hover:bg-surface-variant/40 ${
                  w.severity === 'CRITICAL'
                    ? 'border-l-severity-critical bg-error-container/10'
                    : w.severity === 'HIGH'
                    ? 'border-l-severity-warning bg-amber-500/5'
                    : 'border-l-primary'
                }`}
              >
                <div className="flex items-center justify-between gap-2 mb-1">
                  <div className="flex items-center gap-1.5">
                    <span className={`font-label-mono-bold text-[9px] px-1.5 py-0.5 rounded border tracking-widest ${
                      w.severity === 'CRITICAL'
                        ? 'border-severity-critical text-severity-critical bg-severity-critical/10'
                        : w.severity === 'HIGH'
                        ? 'border-severity-warning text-severity-warning bg-severity-warning/10'
                        : 'border-primary text-primary bg-primary/10'
                    }`}>
                      {w.severity}
                    </span>
                    <span className="font-label-mono text-[10px] text-on-surface-variant font-medium">
                      {w.worker_id > 0 ? `Worker #${w.worker_id}` : 'System'}
                    </span>
                  </div>
                  <span className={`font-label-mono text-[11px] font-bold ${
                    w.severity === 'CRITICAL' ? 'text-severity-critical' : 'text-on-surface'
                  }`}>
                    {w.risk_score}/100
                  </span>
                </div>

                <h4 className="font-body-sm text-xs text-on-surface font-semibold leading-tight mb-1 flex items-center gap-1.5 truncate">
                  {getHazardIcon(w.primary_hazard)}
                  {w.primary_hazard.replace(/_/g, ' ')}
                </h4>

                <div className="flex justify-between items-center text-[10px] font-label-mono text-on-surface-variant mt-1.5">
                  <span className="px-1.5 py-0.5 bg-surface-container-low border border-outline-variant rounded text-on-surface font-medium truncate max-w-[120px]">
                    {w.camera_id}
                  </span>
                  <span>{w.exposure_seconds ? `${w.exposure_seconds.toFixed(1)}s dwell` : ''}</span>
                </div>
              </div>
            ))
          ) : !criticalAlert ? (
            <div className="flex flex-col items-center justify-center h-full p-6 text-center">
              <CheckCircle2 className="w-10 h-10 text-severity-safe mb-2 animate-pulse" />
              <p className="font-label-mono-bold text-xs text-on-surface uppercase tracking-wider font-bold">
                All Zones Nominal
              </p>
              <p className="font-label-mono text-[11px] text-on-surface-variant mt-1">
                Zero active safety violations in the dispatch queue.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};
