import React from 'react';
import { SafetyEvent } from '@/types';

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
  const criticalAlert = alerts.find((a) => a.severity === 'CRITICAL') || alerts[0];
  const warningAlerts = alerts.filter((a) => a.id !== criticalAlert?.id);

  return (
    <div className="flex flex-col gap-unit h-full">
      {/* Header */}
      <div className="flex justify-between items-center mb-2">
        <h3 className="font-label-mono text-xs font-bold text-on-surface-variant uppercase tracking-widest flex items-center gap-2">
          <span className="material-symbols-outlined text-sm">receipt_long</span>
          Event Stream
        </h3>
        <span className="font-label-mono text-[10px] text-on-surface-variant">
          {alerts.length} Active
        </span>
      </div>

      {/* Main Events Container */}
      <div className="level-1-panel rounded-lg flex-1 overflow-hidden flex flex-col shadow-sm">
        
        {/* Active Critical Alert Card */}
        {criticalAlert ? (
          <div
            onClick={() => onSelectEvent(criticalAlert)}
            className="p-3 border-b border-outline-variant border-l-4 border-l-severity-critical bg-error-container/20 relative cursor-pointer group hover:bg-error-container/30 transition-colors"
          >
            <div className="absolute top-2 right-2 text-severity-critical animate-pulse">
              <span className="material-symbols-outlined text-sm">my_location</span>
            </div>

            <div className="flex items-center gap-2 mb-1">
              <span className="font-label-mono-bold text-[10px] px-1.5 py-0.5 rounded bg-severity-critical text-white tracking-widest shadow-sm">
                {criticalAlert.severity}
              </span>
              <span className="font-label-mono text-[10px] text-on-surface-variant">JUST NOW</span>
            </div>

            <h4 className="font-body-sm text-sm font-semibold text-on-surface leading-tight mb-1">
              {criticalAlert.primary_hazard.replace(/_/g, ' ')}
            </h4>
            <p className="font-label-mono text-xs text-on-surface-variant mb-2">
              Worker #{criticalAlert.worker_id.toString().padStart(2, '0')} hazard in {criticalAlert.camera_id}.
            </p>

            <div className="grid grid-cols-2 gap-1 mb-3">
              <div className="bg-surface-container-lowest border border-outline-variant rounded p-1 flex flex-col">
                <span className="font-label-mono text-[9px] text-on-surface-variant">SOURCE</span>
                <span className="font-label-mono-bold text-xs text-on-surface">{criticalAlert.camera_id}</span>
              </div>
              <div className="bg-surface-container-lowest border border-outline-variant rounded p-1 flex flex-col">
                <span className="font-label-mono text-[9px] text-on-surface-variant">RISK INDEX</span>
                <span className="font-label-mono-bold text-xs text-severity-critical">
                  {criticalAlert.risk_score} (CRITICAL)
                </span>
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onAcknowledge(criticalAlert.id);
                }}
                className="flex-1 bg-severity-critical hover:bg-severity-critical/90 text-white font-label-mono-bold text-xs py-1.5 rounded transition-colors flex items-center justify-center gap-1 shadow-sm"
              >
                <span className="material-symbols-outlined text-sm" style={{ fontVariationSettings: "'FILL' 1" }}>
                  campaign
                </span>
                SOUND ALARM
              </button>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  onResolve(criticalAlert.id);
                }}
                className="px-2.5 py-1.5 rounded bg-surface border border-outline-variant hover:bg-surface-variant font-label-mono text-xs text-on-surface transition-colors"
              >
                Resolve
              </button>
            </div>
          </div>
        ) : (
          <div className="p-4 border-b border-outline-variant border-l-4 border-l-severity-safe bg-surface-container-lowest text-center">
            <span className="material-symbols-outlined text-severity-safe text-2xl mb-1">check_circle</span>
            <p className="font-label-mono-bold text-xs text-on-surface">All Zones Nominal</p>
            <p className="font-label-mono text-[10px] text-on-surface-variant">No active critical alerts.</p>
          </div>
        )}

        {/* Warning / Secondary Incident List */}
        <div className="flex-1 overflow-y-auto divide-y divide-outline-variant/60">
          {warningAlerts.length > 0 ? (
            warningAlerts.map((w) => (
              <div
                key={w.id}
                onClick={() => onSelectEvent(w)}
                className="p-3 border-l-4 border-l-severity-warning hover:bg-surface-variant/30 transition-colors cursor-pointer bg-surface-container-lowest"
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-label-mono-bold text-[10px] px-1.5 py-0.5 rounded border border-severity-warning text-severity-warning tracking-widest bg-severity-warning/10">
                    {w.severity}
                  </span>
                  <span className="font-label-mono text-[10px] text-on-surface-variant">
                    Worker #{w.worker_id}
                  </span>
                </div>
                <h4 className="font-body-sm text-xs text-on-surface font-semibold leading-tight mb-1">
                  {w.primary_hazard.replace(/_/g, ' ')}
                </h4>
                <div className="flex gap-2 items-center">
                  <span className="font-label-mono text-[9px] px-1 bg-surface-container-lowest border border-outline-variant rounded text-on-surface-variant">
                    {w.camera_id}
                  </span>
                  <span className="font-label-mono text-[9px] text-severity-warning font-bold">
                    Risk: {w.risk_score}/100
                  </span>
                </div>
              </div>
            ))
          ) : (
            <>
              {/* Default Mock Historical Stream cards matching design */}
              <div className="p-3 border-l-4 border-l-severity-warning hover:bg-surface-variant/30 transition-colors cursor-pointer bg-surface-container-lowest">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-label-mono-bold text-[10px] px-1.5 py-0.5 rounded border border-severity-warning text-severity-warning tracking-widest bg-severity-warning/10">
                    WARNING
                  </span>
                  <span className="font-label-mono text-[10px] text-on-surface-variant">-12m</span>
                </div>
                <h4 className="font-body-sm text-xs text-on-surface font-semibold leading-tight mb-1">
                  PPE Violation Detected
                </h4>
                <p className="font-label-mono text-[11px] text-on-surface-variant mb-1">
                  Hardhat missing near Assembly Line B.
                </p>
                <div className="flex gap-2 items-center">
                  <span className="font-label-mono text-[9px] px-1 bg-surface-container-lowest border border-outline-variant rounded text-on-surface-variant">
                    CAM 02
                  </span>
                </div>
              </div>

              <div className="p-3 hover:bg-surface-variant/30 transition-colors cursor-pointer bg-surface-container-lowest">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-label-mono text-[10px] text-on-surface-variant">-45m</span>
                </div>
                <h4 className="font-body-sm text-xs text-on-surface font-semibold leading-tight mb-1">
                  Routine Shift Change
                </h4>
                <p className="font-label-mono text-[11px] text-on-surface-variant mb-1">
                  Sector A Corridor traffic spike normalized.
                </p>
                <div className="flex gap-2 items-center">
                  <span className="font-label-mono text-[9px] px-1 bg-surface-container-lowest border border-outline-variant rounded text-on-surface-variant">
                    CAM 01
                  </span>
                </div>
              </div>

              <div className="p-3 hover:bg-surface-variant/30 transition-colors cursor-pointer bg-surface-container-lowest">
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-label-mono text-[10px] text-on-surface-variant">-1h 12m</span>
                </div>
                <h4 className="font-body-sm text-xs text-on-surface font-semibold leading-tight mb-1">
                  System Diagnostic Complete
                </h4>
                <p className="font-label-mono text-[11px] text-on-surface-variant mb-1">
                  All monitoring nodes reporting nominally.
                </p>
                <div className="flex gap-2 items-center">
                  <span className="font-label-mono text-[9px] px-1 bg-surface-container-lowest border border-outline-variant rounded text-on-surface-variant">
                    SYSTEM
                  </span>
                </div>
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
