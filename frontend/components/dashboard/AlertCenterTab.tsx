import React, { useState } from 'react';
import { SafetyEvent } from '@/types';

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

  return (
    <div className="flex flex-col gap-6">
      {/* Header & Filter Chips */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="font-headline-md text-xl font-bold text-on-surface mb-1">Active Alerts</h1>
          <p className="font-label-mono text-xs text-on-surface-variant">
            Monitoring unresolved safety incidents across all factory sectors.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(['All', 'Critical', 'High', 'Medium', 'Unresolved'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-mono-bold text-xs transition-colors ${
                filter === f
                  ? 'bg-primary-container text-on-primary-container border border-primary/30'
                  : 'bg-surface text-on-surface border border-outline-variant hover:bg-surface-container'
              }`}
            >
              {f}
            </button>
          ))}
        </div>
      </div>

      {/* Alert List */}
      <div className="flex flex-col gap-unit">
        {filteredAlerts.length === 0 ? (
          <div className="bg-surface border border-outline-variant rounded-DEFAULT p-8 text-center text-on-surface-variant">
            <span className="material-symbols-outlined text-4xl text-severity-safe mb-2">check_circle</span>
            <p className="font-label-mono-bold text-sm text-on-surface">No Unresolved Alerts</p>
            <p className="font-label-mono text-xs text-on-surface-variant mt-1">
              All plant zones are currently operating within nominal safety thresholds.
            </p>
          </div>
        ) : (
          filteredAlerts.map((alert) => {
            const isCrit = alert.severity === 'CRITICAL';
            const isHigh = alert.severity === 'HIGH';

            return (
              <div
                key={alert.id}
                onClick={() => onSelectEvent(alert)}
                className={`bg-surface border-l-4 ${
                  isCrit
                    ? 'border-l-error critical-pulse'
                    : isHigh
                    ? 'border-l-severity-warning'
                    : 'border-l-primary'
                } border border-outline-variant rounded-DEFAULT p-panel-padding flex flex-col lg:flex-row items-start lg:items-center justify-between gap-4 relative overflow-hidden group hover:shadow-md transition-shadow cursor-pointer`}
              >
                <div className="flex items-center gap-4 min-w-[280px]">
                  <div
                    className={`w-12 h-12 rounded-DEFAULT ${
                      isCrit ? 'bg-error-container text-error' : 'bg-secondary-container text-on-secondary-container'
                    } border border-outline-variant flex items-center justify-center flex-shrink-0`}
                  >
                    <span className="material-symbols-outlined text-2xl">
                      {isCrit ? 'warning' : 'notifications'}
                    </span>
                  </div>
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span
                        className={`${
                          isCrit
                            ? 'bg-error text-on-error'
                            : isHigh
                            ? 'bg-severity-warning text-white'
                            : 'bg-primary text-white'
                        } px-1.5 py-0.5 rounded-sm font-label-mono-bold text-[10px] uppercase leading-none`}
                      >
                        {alert.severity}
                      </span>
                      <span className="font-label-mono text-xs text-on-surface-variant">
                        {new Date(alert.started_at).toLocaleTimeString()}
                      </span>
                    </div>
                    <h3 className="font-body-sm text-sm font-semibold text-on-surface">
                      {alert.primary_hazard.replace(/_/g, ' ')}
                    </h3>
                  </div>
                </div>

                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 lg:gap-8 flex-1 w-full lg:w-auto text-xs">
                  <div>
                    <div className="font-label-mono text-[10px] text-on-surface-variant mb-0.5">Subject</div>
                    <div className="font-label-mono-bold text-on-surface">
                      Worker #{alert.worker_id.toString().padStart(2, '0')}
                    </div>
                  </div>
                  <div>
                    <div className="font-label-mono text-[10px] text-on-surface-variant mb-0.5">Camera</div>
                    <div className="font-label-mono-bold text-on-surface">{alert.camera_id}</div>
                  </div>
                  <div>
                    <div className="font-label-mono text-[10px] text-on-surface-variant mb-0.5">Risk Score</div>
                    <div
                      className={`font-label-mono-bold ${
                        isCrit ? 'text-severity-critical' : isHigh ? 'text-severity-warning' : 'text-primary'
                      }`}
                    >
                      {alert.risk_score} / 100
                    </div>
                  </div>
                  <div>
                    <div className="font-label-mono text-[10px] text-on-surface-variant mb-0.5">Exposure</div>
                    <div className="font-label-mono-bold text-on-surface">
                      {alert.exposure_seconds.toFixed(1)}s
                    </div>
                  </div>
                </div>

                <div className="flex items-center gap-2 w-full lg:w-auto justify-end">
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onSelectEvent(alert);
                    }}
                    className="px-3 py-1.5 bg-surface-container border border-outline-variant rounded font-label-mono-bold text-xs text-on-surface hover:bg-surface-variant transition-colors"
                  >
                    View Evidence
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onAcknowledge(alert.id);
                    }}
                    className="px-3 py-1.5 bg-primary text-white rounded font-label-mono-bold text-xs hover:bg-primary/90 transition-colors"
                  >
                    Acknowledge
                  </button>
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      onResolve(alert.id);
                    }}
                    className="px-3 py-1.5 bg-severity-safe text-white rounded font-label-mono-bold text-xs hover:bg-severity-safe/90 transition-colors"
                  >
                    Resolve
                  </button>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
