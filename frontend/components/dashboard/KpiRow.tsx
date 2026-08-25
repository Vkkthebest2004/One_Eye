import React from 'react';
import { AnalyticsSummary } from '@/types';

interface KpiRowProps {
  summary: AnalyticsSummary | null;
  activeCount: number;
  totalTrackedWorkers: number;
}

export const KpiRow: React.FC<KpiRowProps> = ({
  summary,
  activeCount,
  totalTrackedWorkers,
}) => {
  const totalCams = summary?.cameras_total || 4;
  const onlineCams = summary?.cameras_online || 4;
  const criticalCount = summary?.critical_events || (activeCount > 0 ? 1 : 0);
  const avgRisk = summary?.avg_risk_score || 32;
  const workersCount = totalTrackedWorkers > 0 ? totalTrackedWorkers : 27;

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-gutter mb-2">
      {/* KPI 1: Cameras */}
      <div className="level-1-panel rounded-lg p-panel-padding flex flex-col justify-between relative overflow-hidden">
        <div className="absolute top-0 right-0 w-16 h-16 bg-primary/10 rounded-bl-full blur-xl pointer-events-none" />
        <div className="flex justify-between items-start mb-4">
          <span className="font-label-mono text-xs text-on-surface-variant uppercase tracking-wider">
            Cameras
          </span>
          <span className="material-symbols-outlined text-on-surface-variant">videocam</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-data-metric text-3xl font-bold text-on-surface">
            {onlineCams}/{totalCams}
          </span>
          <span className="font-label-mono-bold text-xs text-severity-safe flex items-center gap-1">
            <span className="w-1.5 h-1.5 rounded-full bg-severity-safe inline-block" />
            ONLINE
          </span>
        </div>
      </div>

      {/* KPI 2: Active Alerts */}
      <div className="level-1-panel rounded-lg p-panel-padding flex flex-col justify-between relative overflow-hidden border-l-4 border-l-severity-warning">
        <div className="absolute top-0 right-0 w-16 h-16 bg-severity-warning/10 rounded-bl-full blur-xl pointer-events-none" />
        <div className="flex justify-between items-start mb-4">
          <span className="font-label-mono text-xs text-on-surface-variant uppercase tracking-wider">
            Active Alerts
          </span>
          <span className="material-symbols-outlined text-severity-warning">notifications_active</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-data-metric text-3xl font-bold text-severity-warning">
            {activeCount.toString().padStart(2, '0')}
          </span>
          <span className="font-label-mono-bold text-xs text-on-surface-variant">REQ ATTN</span>
        </div>
      </div>

      {/* KPI 3: Critical Events */}
      <div className={`level-1-panel rounded-lg p-panel-padding flex flex-col justify-between relative overflow-hidden border-l-4 border-l-severity-critical ${
        criticalCount > 0 ? 'critical-bloom' : ''
      }`}>
        <div className="absolute top-0 right-0 w-16 h-16 bg-severity-critical/10 rounded-bl-full blur-xl pointer-events-none" />
        <div className="flex justify-between items-start mb-4">
          <span className="font-label-mono text-xs text-on-surface-variant uppercase tracking-wider">
            Critical Events
          </span>
          <span className={`material-symbols-outlined text-severity-critical ${criticalCount > 0 ? 'animate-pulse' : ''}`}>
            warning
          </span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-data-metric text-3xl font-bold text-severity-critical">
            {criticalCount.toString().padStart(2, '0')}
          </span>
          <span className="font-label-mono-bold text-xs text-severity-critical">
            {criticalCount > 0 ? 'UNRESOLVED' : 'NOMINAL'}
          </span>
        </div>
      </div>

      {/* KPI 4: Workers Tracked */}
      <div className="level-1-panel rounded-lg p-panel-padding flex flex-col justify-between relative overflow-hidden">
        <div className="absolute top-0 right-0 w-16 h-16 bg-severity-info/10 rounded-bl-full blur-xl pointer-events-none" />
        <div className="flex justify-between items-start mb-4">
          <span className="font-label-mono text-xs text-on-surface-variant uppercase tracking-wider">
            Workers Tracked
          </span>
          <span className="material-symbols-outlined text-on-surface-variant">engineering</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-data-metric text-3xl font-bold text-on-surface">
            {workersCount}
          </span>
          <span className="font-label-mono-bold text-xs text-on-surface-variant">ON FLOOR</span>
        </div>
      </div>

      {/* KPI 5: Avg Risk */}
      <div className="level-1-panel rounded-lg p-panel-padding flex flex-col justify-between relative overflow-hidden">
        <div className="absolute top-0 right-0 w-16 h-16 bg-severity-warning/10 rounded-bl-full blur-xl pointer-events-none" />
        <div className="flex justify-between items-start mb-2">
          <span className="font-label-mono text-xs text-on-surface-variant uppercase tracking-wider">
            Avg Risk
          </span>
          <span className="material-symbols-outlined text-on-surface-variant">speed</span>
        </div>
        <div className="flex items-baseline gap-2">
          <span className="font-data-metric text-3xl font-bold text-on-surface">
            {Math.round(avgRisk)}
          </span>
          <span className="font-label-mono-bold text-xs text-on-surface-variant">/100</span>
        </div>
        <div className="w-full bg-surface-container h-1.5 mt-2 rounded overflow-hidden">
          <div
            className={`h-full rounded transition-all duration-500 ${
              avgRisk > 70 ? 'bg-severity-critical' : avgRisk > 40 ? 'bg-severity-warning' : 'bg-severity-safe'
            }`}
            style={{ width: `${Math.min(100, Math.max(5, avgRisk))}%` }}
          />
        </div>
      </div>
    </div>
  );
};
