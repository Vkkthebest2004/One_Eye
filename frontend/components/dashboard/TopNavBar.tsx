import React, { useState, useEffect } from 'react';
import { SystemHealth } from '@/types';
import { getSystemMode, toggleSystemAi, getDemoMode, toggleDemoMode } from '@/lib/api';

interface TopNavBarProps {
  health: SystemHealth | null;
  activeAlertCount: number;
  onSearchChange?: (val: string) => void;
  onOpenMobileMenu?: () => void;
  onDemoModeChanged?: (demoMode: boolean) => void;
}

export const TopNavBar: React.FC<TopNavBarProps> = ({
  health,
  activeAlertCount,
  onSearchChange,
  onOpenMobileMenu,
  onDemoModeChanged,
}) => {
  const [timeStr, setTimeStr] = useState<string>('00:00:00');
  const [searchVal, setSearchVal] = useState('');
  const [aiEnabled, setAiEnabled] = useState<boolean>(true);
  const [demoMode, setDemoMode] = useState<boolean>(false);
  const [isTogglingAi, setIsTogglingAi] = useState<boolean>(false);
  const [isTogglingDemo, setIsTogglingDemo] = useState<boolean>(false);

  useEffect(() => {
    getSystemMode()
      .then((res) => setAiEnabled(res.ai_enabled))
      .catch(() => null);

    getDemoMode()
      .then((res) => {
        setDemoMode(res.demo_mode);
        if (onDemoModeChanged) onDemoModeChanged(res.demo_mode);
      })
      .catch(() => null);
  }, []);

  const handleToggleAi = async () => {
    setIsTogglingAi(true);
    try {
      const res = await toggleSystemAi(!aiEnabled);
      setAiEnabled(res.ai_enabled);
    } catch (e) {
      console.warn('Failed to toggle AI system mode', e);
    } finally {
      setIsTogglingAi(false);
    }
  };

  const handleToggleDemoMode = async () => {
    setIsTogglingDemo(true);
    try {
      const res = await toggleDemoMode(!demoMode);
      setDemoMode(res.demo_mode);
      if (onDemoModeChanged) onDemoModeChanged(res.demo_mode);
    } catch (e) {
      console.warn('Failed to toggle demo mode', e);
    } finally {
      setIsTogglingDemo(false);
    }
  };

  useEffect(() => {
    const update = () => {
      const now = new Date();
      setTimeStr(
        now.toLocaleTimeString('en-US', {
          hour12: false,
          hour: '2-digit',
          minute: '2-digit',
          second: '2-digit',
        })
      );
    };
    update();
    const interval = setInterval(update, 1000);
    return () => clearInterval(interval);
  }, []);

  const handleSearch = (e: React.ChangeEvent<HTMLInputElement>) => {
    setSearchVal(e.target.value);
    if (onSearchChange) onSearchChange(e.target.value);
  };

  return (
    <header className="bg-surface flex justify-between items-center w-full px-margin-page h-14 z-30 border-b border-outline-variant shrink-0">
      {/* Left: Mobile Menu Button & Platform Title */}
      <div className="flex items-center gap-3">
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden p-1.5 rounded text-on-surface-variant hover:bg-surface-variant"
        >
          <span className="material-symbols-outlined">menu</span>
        </button>

        <div className="flex items-center gap-2">
          <span
            className="material-symbols-outlined text-primary text-xl md:hidden"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            visibility
          </span>
          <span className="font-label-mono text-xs md:text-sm font-bold text-on-surface uppercase tracking-wider">
            One_Eye Safety Intelligence
          </span>
          <span className="hidden sm:inline-block text-xs font-mono text-on-surface-variant">
            // {timeStr}
          </span>
        </div>
      </div>

      {/* Right Controls & Telemetry */}
      <div className="flex items-center gap-4 lg:gap-6">
        {/* Global Search Bar */}
        <div className="relative hidden md:block">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm">
            search
          </span>
          <input
            type="text"
            value={searchVal}
            onChange={handleSearch}
            placeholder="Search entity, camera, or zone..."
            className="bg-surface-container-low border border-outline-variant rounded-full py-1 pl-9 pr-4 font-body-sm text-xs text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary w-56 lg:w-64 transition-all"
          />
        </div>

        {/* Master AI Hazard Scanning / Camera-Only Toggle Button */}
        <button
          onClick={handleToggleAi}
          disabled={isTogglingAi}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-label-mono font-bold border transition-all shadow-sm ${
            aiEnabled
              ? 'bg-emerald-500/15 text-emerald-600 border-emerald-500/40 hover:bg-emerald-500/25'
              : 'bg-amber-500/20 text-amber-600 border-amber-500/50 hover:bg-amber-500/30 ring-1 ring-amber-500/30'
          }`}
          title={aiEnabled ? 'Click to Pause AI Hazard Detection & Alerts (Camera-Only Mode)' : 'Click to Resume AI Hazard Detection & Alerts'}
        >
          <span className={`w-2 h-2 rounded-full ${aiEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          <span className="material-symbols-outlined text-sm">
            {aiEnabled ? 'security' : 'pause_circle'}
          </span>
          <span className="hidden sm:inline">
            {aiEnabled ? 'AI SCANNING: ON' : 'CAMERA ONLY'}
          </span>
        </button>

        {/* Live Production vs Demo Simulation Mode Switch */}
        <button
          onClick={handleToggleDemoMode}
          disabled={isTogglingDemo}
          className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-label-mono font-bold border transition-all shadow-sm ${
            !demoMode
              ? 'bg-rose-500/15 text-rose-600 border-rose-500/40 hover:bg-rose-500/25'
              : 'bg-amber-500/20 text-amber-600 border-amber-500/50 hover:bg-amber-500/30 ring-1 ring-amber-500/30'
          }`}
          title={demoMode ? 'Switch to LIVE Production Mode (100% real camera feeds)' : 'Switch to Demo Simulation Mode'}
        >
          <span className={`w-2 h-2 rounded-full ${!demoMode ? 'bg-rose-500 animate-pulse' : 'bg-amber-500'}`} />
          <span className="material-symbols-outlined text-sm">
            {!demoMode ? 'videocam' : 'science'}
          </span>
          <span className="hidden sm:inline">
            {!demoMode ? 'LIVE MODE (PROD)' : 'DEMO SIMULATION'}
          </span>
        </button>

        {/* System Diagnostics Telemetry Icons */}
        <div className="flex items-center gap-2">
          <button
            title={`CV Engine: ${health?.cv_engine || 'ONLINE'}`}
            className="text-on-surface-variant hover:text-primary hover:bg-surface-variant transition-colors p-1.5 rounded-full cursor-pointer"
          >
            <span className="material-symbols-outlined">memory</span>
          </button>
          <button
            title={`Database: ${health?.database || 'ONLINE'}`}
            className="text-on-surface-variant hover:text-primary hover:bg-surface-variant transition-colors p-1.5 rounded-full cursor-pointer"
          >
            <span className="material-symbols-outlined">database</span>
          </button>
          <button
            title="Active Edge Pipeline Nodes"
            className="text-on-surface-variant hover:text-primary hover:bg-surface-variant transition-colors p-1.5 rounded-full cursor-pointer"
          >
            <span className="material-symbols-outlined">account_tree</span>
          </button>
        </div>

        <div className="h-6 w-px bg-outline-variant" />

        {/* Active Alerts Pill & Operator Avatar */}
        <div className="flex items-center gap-3">
          <div className="px-2.5 py-0.5 bg-error-container border border-error rounded flex items-center gap-1.5 shadow-sm">
            <div className="w-2 h-2 rounded-full bg-error animate-pulse" />
            <span className="font-label-mono-bold text-xs text-error">
              {activeAlertCount} ACTIVE
            </span>
          </div>

          <div className="flex items-center gap-2 cursor-pointer group">
            <div className="w-8 h-8 rounded bg-primary/10 border border-outline-variant flex items-center justify-center text-primary font-bold font-mono text-xs">
              OP
            </div>
            <div className="hidden lg:flex flex-col text-left">
              <span className="font-label-mono-bold text-xs text-on-surface leading-tight">Operator</span>
              <span className="text-[10px] text-on-surface-variant leading-tight">Shift A-1</span>
            </div>
          </div>
        </div>
      </div>
    </header>
  );
};
