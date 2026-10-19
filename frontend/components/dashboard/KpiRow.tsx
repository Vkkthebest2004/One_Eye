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
  // Pure real-time telemetry (no synthetic mock fallbacks)
  const totalCams = summary?.cameras_total ?? 1;
  const onlineCams = summary?.cameras_online ?? 0;
  const criticalCount = summary?.critical_events ?? 0;
  const avgRisk = summary?.avg_risk_score ?? 0;
  const workersCount = totalTrackedWorkers ?? summary?.workers_tracked ?? 0;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-1">
      {/* Metric 1: Connected Cameras */}
      <div className="level-1-panel rounded-lg px-3.5 py-2.5 flex items-center justify-between border border-white/5 bg-surface/80 backdrop-blur-sm">
        <div>
          <div className="font-label-mono text-[10px] uppercase tracking-wider text-on-surface-variant font-medium">
            Video Feeds
          </div>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="font-data-metric text-xl font-bold text-on-surface">
              {onlineCams}
              <span className="text-xs text-on-surface-variant font-normal">/{totalCams}</span>
            </span>
            <span className="text-[11px] font-mono text-emerald-400 font-medium flex items-center gap-1">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {onlineCams > 0 ? 'Live' : 'Standby'}
            </span>
          </div>
        </div>
        <span className="material-symbols-outlined text-slate-500 text-lg">videocam</span>
      </div>

      {/* Metric 2: Workers in View */}
      <div className="level-1-panel rounded-lg px-3.5 py-2.5 flex items-center justify-between border border-white/5 bg-surface/80 backdrop-blur-sm">
        <div>
          <div className="font-label-mono text-[10px] uppercase tracking-wider text-on-surface-variant font-medium">
            Tracked Workers
          </div>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className="font-data-metric text-xl font-bold text-on-surface">
              {workersCount}
            </span>
            <span className="text-[11px] font-mono text-on-surface-variant">
              In Frame
            </span>
          </div>
        </div>
        <span className="material-symbols-outlined text-slate-500 text-lg">engineering</span>
      </div>

      {/* Metric 3: Active Hazards / Alerts */}
      <div className={`level-1-panel rounded-lg px-3.5 py-2.5 flex items-center justify-between border backdrop-blur-sm ${
        activeCount > 0 ? 'border-amber-500/30 bg-amber-500/5' : 'border-white/5 bg-surface/80'
      }`}>
        <div>
          <div className="font-label-mono text-[10px] uppercase tracking-wider text-on-surface-variant font-medium">
            Hazard Violations
          </div>
          <div className="flex items-baseline gap-2 mt-0.5">
            <span className={`font-data-metric text-xl font-bold ${activeCount > 0 ? 'text-amber-400' : 'text-on-surface'}`}>
              {activeCount}
            </span>
            <span className={`text-[11px] font-mono font-medium ${activeCount > 0 ? 'text-amber-400' : 'text-emerald-400'}`}>
              {activeCount > 0 ? 'Active' : 'All Clear'}
            </span>
          </div>
        </div>
        <span className={`material-symbols-outlined text-lg ${activeCount > 0 ? 'text-amber-400 animate-pulse' : 'text-slate-500'}`}>
          {activeCount > 0 ? 'warning' : 'verified_user'}
        </span>
      </div>

      {/* Metric 4: Risk Index */}
      <div className="level-1-panel rounded-lg px-3.5 py-2.5 flex flex-col justify-between border border-white/5 bg-surface/80 backdrop-blur-sm">
        <div className="flex items-center justify-between">
          <div className="font-label-mono text-[10px] uppercase tracking-wider text-on-surface-variant font-medium">
            Safety Risk Index
          </div>
          <span className="font-data-metric text-xs font-bold text-on-surface">
            {Math.round(avgRisk)}/100
          </span>
        </div>
        <div className="w-full bg-white/5 h-1 mt-2 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${
              avgRisk > 60 ? 'bg-red-500' : avgRisk > 30 ? 'bg-amber-400' : 'bg-emerald-500'
            }`}
            style={{ width: `${Math.min(100, Math.max(avgRisk === 0 ? 4 : avgRisk, 4))}%` }}
          />
        </div>
      </div>
    </div>
  );
};
