import React, { useState } from 'react';
import { SafetyEvent } from '@/types';
import { ShieldAlert, AlertTriangle, CheckCircle2, Flame, HardHat, Compass, Clock, ArrowUpRight, User, MapPin } from 'lucide-react';

interface AlertCenterTabProps {
  alerts: SafetyEvent[];
  onSelectEvent: (event: SafetyEvent) => void;
  onAcknowledge: (id: string) => void;
  onResolve: (id: string) => void;
}

export const AlertCenterTab: React.FC<AlertCenterTabProps> = ({
  alerts,
  onSelectEvent,
  onAcknowledge,
  onResolve,
}) => {
  const [filter, setFilter] = useState<'All' | 'Critical' | 'High' | 'Medium' | 'Unresolved'>('All');

  const filteredAlerts = alerts.filter((a) => {
    if (filter === 'All') return true;
    if (filter === 'Critical') return a.severity === 'CRITICAL';
    if (filter === 'High') return a.severity === 'HIGH';
    if (filter === 'Medium') return a.severity === 'MEDIUM';
    if (filter === 'Unresolved') return a.status === 'ALERTING';
    return true;
  });

  const getHazardIcon = (hazard: string) => {
    if (hazard.includes('FIRE') || hazard.includes('SMOKE')) return <Flame className="w-4 h-4 text-severity-critical" />;
    if (hazard.includes('HELMET') || hazard.includes('PPE')) return <HardHat className="w-4 h-4 text-severity-warning" />;
    if (hazard.includes('PROXIMITY')) return <Compass className="w-4 h-4 text-cyan-400" />;
    return <ShieldAlert className="w-4 h-4 text-severity-critical" />;
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Header & Filter Chips */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 bg-surface-container-low p-4 rounded-lg border border-outline-variant">
        <div>
          <h1 className="font-headline-md text-xl font-bold text-on-surface mb-1 flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-severity-critical" />
            Safety Alert Dispatch Queue ({alerts.length})
          </h1>
          <p className="font-label-mono text-xs text-on-surface-variant">
            Live unresolved safety incidents requiring operator acknowledgment, escalation, or resolution.
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 bg-surface-container p-1 rounded-DEFAULT border border-outline-variant">
          {(['All', 'Critical', 'High', 'Medium', 'Unresolved'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-mono-bold text-xs transition ${
                filter === f
                  ? 'bg-primary text-white shadow-sm font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
              }`}
            >
              {f.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Alert List */}
      <div className="flex flex-col gap-unit">
        {filteredAlerts.length === 0 ? (
          <div className="bg-surface-container-low border border-outline-variant rounded-lg p-10 text-center text-on-surface-variant">
            <CheckCircle2 className="w-10 h-10 text-severity-safe mx-auto mb-2 animate-pulse" />
            <p className="font-label-mono-bold text-sm text-on-surface">ALL ZONES NOMINAL — NO ACTIVE INCIDENTS</p>
            <p className="font-label-mono text-xs text-on-surface-variant mt-1">
              All plant sectors are currently operating within safe hazard and proximity thresholds.
            </p>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isCrit = alert.severity === 'CRITICAL';
            const isHigh = alert.severity === 'HIGH';
            const isAck = alert.status === 'ACKNOWLEDGED';

            return (
              <div
                key={alert.id}
                onClick={() => onSelectEvent(alert)}
                className={`bg-surface-container-low border-l-4 ${
                  isCrit
                    ? 'border-l-severity-critical critical-pulse'
                    : isHigh
                    ? 'border-l-severity-warning'
                    : 'border-l-primary'
                } border border-outline-variant rounded-lg p-panel-padding flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 relative overflow-hidden group hover:shadow-md transition-shadow cursor-pointer`}
              >
                <div className="flex items-center gap-4 min-w-[280px]">
                  <div
                    className={`w-11 h-11 rounded-lg ${
                      isCrit ? 'bg-error-container text-error' : 'bg-surface-container text-on-surface'
                    } border border-outline-variant flex items-center justify-center flex-shrink-0`}
                  >
                    {getHazardIcon(alert.primary_hazard)}
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`${
                          isCrit
                            ? 'bg-severity-critical text-white'
                            : isHigh
                            ? 'bg-severity-warning text-black font-bold'
                            : 'bg-primary text-white'
                        } px-2 py-0.5 rounded text-[10px] font-label-mono-bold uppercase leading-none`}
                      >
                        {alert.severity}
                      </span>
                      <span className="font-label-mono text-[11px] text-on-surface-variant">
                        {alert.id}
                      </span>
                      {isAck && (
                        <span className="font-label-mono text-[10px] bg-primary/15 text-primary px-1.5 py-0.5 rounded font-bold">
                          ACKNOWLEDGED
                        </span>
                      )}
                    </div>
                    <h3 className="font-body-sm text-sm font-semibold text-on-surface">
                      {alert.primary_hazard.replace(/_/g, ' ')}
                    </h3>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 lg:gap-8 flex-1 w-full lg:w-auto text-xs font-label-mono">
                  <div>
                    <div className="text-[10px] text-on-surface-variant mb-0.5">SUBJECT</div>
                    <div className="font-bold text-on-surface flex items-center gap-1">
                      <User className="w-3 h-3 text-primary" />
                      {alert.worker_id > 0 ? `Worker #${alert.worker_id.toString().padStart(2, '0')}` : 'Plant-Wide'}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-on-surface-variant mb-0.5">CAMERA SOURCE</div>
                    <div className="font-bold text-on-surface flex items-center gap-1">
                      <MapPin className="w-3 h-3 text-primary" />
                      {alert.camera_id}
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-on-surface-variant mb-0.5">RISK SCORE</div>
                    <div
                      className={`font-bold ${
                        isCrit ? 'text-severity-critical' : isHigh ? 'text-severity-warning' : 'text-primary'
                      }`}
                    >
                      {alert.risk_score} / 100
                    </div>
                  </div>
                  <div>
                    <div className="text-[10px] text-on-surface-variant mb-0.5">EXPOSURE DWELL</div>
                    <div className="font-bold text-on-surface flex items-center gap-1">
                      <Clock className="w-3 h-3 text-severity-warning" />
                      {alert.exposure_seconds ? `${alert.exposure_seconds.toFixed(1)}s` : '0.0s'}
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 w-full lg:w-auto justify-end">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectEvent(alert);
                    }}
                    className="px-3 py-1.5 bg-surface-container border border-outline-variant rounded font-label-mono text-xs text-on-surface hover:bg-surface-variant transition-colors flex items-center gap-1"
                  >
                    <span>Evidence</span>
                    <ArrowUpRight className="w-3 h-3" />
                  </button>
                  {!isAck ? (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAcknowledge(alert.id);
                      }}
                      className="px-3 py-1.5 bg-severity-critical text-white rounded font-label-mono-bold text-xs hover:bg-severity-critical/90 transition-colors shadow-sm"
                    >
                      Acknowledge
                    </button>
                  ) : (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onResolve(alert.id);
                      }}
                      className="px-3 py-1.5 bg-severity-safe text-white rounded font-label-mono-bold text-xs hover:bg-severity-safe/90 transition-colors shadow-sm"
                    >
                      Resolve
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
