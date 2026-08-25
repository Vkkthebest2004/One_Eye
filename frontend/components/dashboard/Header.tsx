import React from 'react';
import { Shield, Radio, Activity, AlertTriangle, Eye, Video, Settings, Map, BarChart3, History, Sparkles } from 'lucide-react';
import { SystemHealth } from '@/types';

interface HeaderProps {
  health: SystemHealth | null;
  activeAlertCount: number;
  criticalCount: number;
  wsConnected: boolean;
  activeTab: 'live' | 'analytics' | 'map' | 'history' | 'calibration';
  setActiveTab: (tab: 'live' | 'analytics' | 'map' | 'history' | 'calibration') => void;
}

export const Header: React.FC<HeaderProps> = ({
  health,
  activeAlertCount,
  criticalCount,
  wsConnected,
  activeTab,
  setActiveTab,
}) => {
  const onlineCams = health ? Object.values(health.cameras).filter(c => c.status === 'ONLINE').length : 0;
  const totalCams = health ? Object.keys(health.cameras).length : 4;

  return (
    <header className="border-b border-industrial-border bg-industrial-900/90 backdrop-blur sticky top-0 z-40 px-4 py-2.5">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3">
        
        {/* Left: Brand & Status */}
        <div className="flex items-center gap-3">
          <div className="relative flex items-center justify-center w-10 h-10 rounded-lg bg-cyan-950/80 border border-cyan-500/40 text-cyan-400">
            <Eye className="w-5 h-5 animate-pulse" />
            <div className="absolute -bottom-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-emerald-400 ring-2 ring-industrial-900" />
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="font-mono font-bold tracking-wider text-lg text-white">ONE EYE</h1>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-cyan-950/70 border border-cyan-500/30 text-cyan-400 font-semibold tracking-wider">
                Control Room v1.0
              </span>
              {health?.demo_mode && (
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-amber-500/20 border border-amber-500/40 text-amber-300 font-semibold flex items-center gap-1">
                  <Sparkles className="w-3 h-3" /> DEMO MODE
                </span>
              )}
            </div>
            <p className="text-xs text-slate-400 font-medium">Industrial Safety & Hazard Intelligence Platform</p>
          </div>
        </div>

        {/* Center: System Status Telemetry */}
        <div className="flex items-center gap-3 bg-industrial-950/80 px-3 py-1.5 rounded-lg border border-industrial-border/60 text-xs">
          <div className="flex items-center gap-1.5">
            <div className={`w-2 h-2 rounded-full ${wsConnected ? 'bg-emerald-400 animate-ping' : 'bg-red-400'}`} />
            <span className="text-slate-400 font-mono">SYSTEM:</span>
            <span className={`font-mono font-semibold ${wsConnected ? 'text-emerald-400' : 'text-red-400'}`}>
              {wsConnected ? 'ONLINE' : 'CONNECTING'}
            </span>
          </div>

          <div className="h-3 w-[1px] bg-industrial-border" />

          <div className="flex items-center gap-1.5">
            <Video className="w-3.5 h-3.5 text-cyan-400" />
            <span className="text-slate-400">CAMERAS:</span>
            <span className="font-mono font-semibold text-slate-200">{onlineCams}/{totalCams}</span>
          </div>

          <div className="h-3 w-[1px] bg-industrial-border" />

          <div className="flex items-center gap-1.5">
            <AlertTriangle className={`w-3.5 h-3.5 ${activeAlertCount > 0 ? 'text-amber-400' : 'text-slate-500'}`} />
            <span className="text-slate-400">ALERTS:</span>
            <span className={`font-mono font-semibold ${activeAlertCount > 0 ? 'text-amber-400' : 'text-slate-300'}`}>
              {activeAlertCount}
            </span>
          </div>

          {criticalCount > 0 && (
            <>
              <div className="h-3 w-[1px] bg-industrial-border" />
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded bg-hazard-critical/20 border border-hazard-critical/40 text-hazard-critical font-mono font-bold animate-pulse">
                <span>{criticalCount} CRITICAL</span>
              </div>
            </>
          )}
        </div>

        {/* Right: Navigation Tabs */}
        <div className="flex items-center gap-1.5 bg-industrial-950 p-1 rounded-lg border border-industrial-border">
          <button
            onClick={() => setActiveTab('live')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'live'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-industrial-800'
            }`}
          >
            <Radio className="w-3.5 h-3.5" />
            <span>Live Feeds</span>
          </button>

          <button
            onClick={() => setActiveTab('map')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'map'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-industrial-800'
            }`}
          >
            <Map className="w-3.5 h-3.5" />
            <span>Safety Map</span>
          </button>

          <button
            onClick={() => setActiveTab('analytics')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'analytics'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-industrial-800'
            }`}
          >
            <BarChart3 className="w-3.5 h-3.5" />
            <span>Analytics</span>
          </button>

          <button
            onClick={() => setActiveTab('history')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'history'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-industrial-800'
            }`}
          >
            <History className="w-3.5 h-3.5" />
            <span>Audit Log</span>
          </button>

          <button
            onClick={() => setActiveTab('calibration')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded text-xs font-medium transition ${
              activeTab === 'calibration'
                ? 'bg-cyan-600/20 text-cyan-300 border border-cyan-500/40 shadow-sm'
                : 'text-slate-400 hover:text-slate-200 hover:bg-industrial-800'
            }`}
          >
            <Settings className="w-3.5 h-3.5" />
            <span>Calibration</span>
          </button>
        </div>

      </div>
    </header>
  );
};
