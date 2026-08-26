import React, { useState, useEffect } from 'react';
import { SystemHealth } from '@/types';
import { getSystemMode, toggleSystemAi, getDemoMode, toggleDemoMode, getPerceptionMode, setPerceptionMode } from '@/lib/api';

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
  const [perceptionMode, setPerceptionState] = useState<'YOLO' | 'QWEN_VL' | 'HYBRID'>('YOLO');
  const [isTogglingAi, setIsTogglingAi] = useState<boolean>(false);
  const [isTogglingDemo, setIsTogglingDemo] = useState<boolean>(false);
  const [isChangingMode, setIsChangingMode] = useState<boolean>(false);

  useEffect(() => {
    getSystemMode()
      .then((res) => setAiEnabled(res.ai_enabled))
      .catch(() => null);

    getPerceptionMode()
      .then((res) => setPerceptionState(res.perception_mode as any))
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

  const handleCyclePerceptionMode = async () => {
    const cycleMap: Record<string, 'YOLO' | 'QWEN_VL' | 'HYBRID'> = {
      YOLO: 'QWEN_VL',
      QWEN_VL: 'HYBRID',
      HYBRID: 'YOLO',
    };
    const nextMode = cycleMap[perceptionMode] || 'YOLO';
    setIsChangingMode(true);
    try {
      const res = await setPerceptionMode(nextMode);
      setPerceptionState(res.perception_mode as any);
    } catch (e) {
      console.warn('Failed to change perception mode', e);
    } finally {
      setIsChangingMode(false);
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
    <header className="bg-surface flex justify-between items-center w-full px-3 md:px-6 h-14 z-30 border-b border-outline-variant shrink-0 max-w-full overflow-hidden">
      {/* Left: Mobile Menu Trigger & Title */}
      <div className="flex items-center gap-2.5 shrink-0 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-variant focus:outline-none"
          title="Open Navigation Menu"
        >
          <span className="material-symbols-outlined text-2xl">menu</span>
        </button>

        <div className="flex items-center gap-2 min-w-0">
          <span
            className="material-symbols-outlined text-primary text-2xl md:hidden shrink-0"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            visibility
          </span>
          <span className="font-headline-md text-xs md:text-sm font-bold text-on-surface uppercase tracking-wider truncate">
            ONE EYE
          </span>
          <span className="hidden sm:inline-block text-xs font-mono text-on-surface-variant shrink-0">
            // {timeStr}
          </span>
        </div>
      </div>

      {/* Right Controls: Sliding Horizontal Scroll Container on smaller viewports */}
      <div className="flex items-center gap-2 md:gap-4 overflow-x-auto sliding-scroll-container shrink min-w-0 py-1">
        {/* Global Search Bar (hidden on small mobile) */}
        <div className="relative hidden lg:block shrink-0">
          <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-on-surface-variant text-sm pointer-events-none">
            search
          </span>
          <input
            type="text"
            value={searchVal}
            onChange={handleSearch}
            placeholder="Search entity, camera, or zone..."
            className="bg-surface-container-low border border-outline-variant rounded-full py-1 pl-9 pr-4 font-body-sm text-xs text-on-surface focus:outline-none focus:border-primary focus:ring-1 focus:ring-primary w-48 xl:w-60 transition-all"
          />
        </div>

        {/* Perception Engine Switcher: YOLO vs Qwen-VL vs Hybrid */}
        <button
          onClick={handleCyclePerceptionMode}
          disabled={isChangingMode}
          className={`flex items-center gap-1.5 px-2.5 md:px-3 py-1.5 rounded-lg text-xs font-label-mono font-bold border transition-all shadow-sm shrink-0 whitespace-nowrap active:scale-95 ${
            perceptionMode === 'QWEN_VL'
              ? 'bg-purple-500/20 text-purple-300 border-purple-500/50 hover:bg-purple-500/30 ring-1 ring-purple-500/30'
              : perceptionMode === 'HYBRID'
              ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 hover:bg-cyan-500/30 ring-1 ring-cyan-500/30'
              : 'bg-blue-500/15 text-blue-400 border-blue-500/40 hover:bg-blue-500/25'
          }`}
          title="Click to Switch Perception Engine (YOLOv8 ↔ Qwen2-VL ↔ Hybrid Dual-AI)"
        >
          <span className={`w-2 h-2 rounded-full shrink-0 ${
            perceptionMode === 'QWEN_VL' ? 'bg-purple-400 animate-pulse' :
            perceptionMode === 'HYBRID' ? 'bg-cyan-400 animate-pulse' : 'bg-blue-400'
          }`} />
          <span className="material-symbols-outlined text-sm shrink-0">
            {perceptionMode === 'QWEN_VL' ? 'psychology' : perceptionMode === 'HYBRID' ? 'hub' : 'bolt'}
          </span>
          <span className="text-[11px] hidden sm:inline">
            {perceptionMode === 'QWEN_VL' ? 'ENGINE: QWEN2-VL' : perceptionMode === 'HYBRID' ? 'ENGINE: HYBRID DUAL-AI' : 'ENGINE: YOLOV8'}
          </span>
        </button>

        {/* Master AI Hazard Scanning / Camera-Only Toggle Button */}
        <button
          onClick={handleToggleAi}
          disabled={isTogglingAi}
          className={`flex items-center gap-1.5 px-2.5 md:px-3 py-1.5 rounded-lg text-xs font-label-mono font-bold border transition-all shadow-sm shrink-0 whitespace-nowrap active:scale-95 ${
            aiEnabled
              ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/40 hover:bg-emerald-500/25'
              : 'bg-amber-500/20 text-amber-400 border-amber-500/50 hover:bg-amber-500/30 ring-1 ring-amber-500/30'
          }`}
          title={aiEnabled ? 'Click to Pause AI Vision Hazard Detection' : 'Click to Resume AI Vision Hazard Detection'}
        >
          <span className={`w-2 h-2 rounded-full shrink-0 ${aiEnabled ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          <span className="material-symbols-outlined text-sm shrink-0">
            {aiEnabled ? 'security' : 'pause_circle'}
          </span>
          <span className="text-[11px] hidden sm:inline">
            {aiEnabled ? 'AI DETECTION: ACTIVE' : 'AI PAUSED (VIEW ONLY)'}
          </span>
        </button>

        {/* Live Production vs Demo Simulation Mode Switch */}
        <button
          onClick={handleToggleDemoMode}
          disabled={isTogglingDemo}
          className={`flex items-center gap-1.5 px-2.5 md:px-3 py-1.5 rounded-lg text-xs font-label-mono font-bold border transition-all shadow-sm shrink-0 whitespace-nowrap active:scale-95 ${
            !demoMode
              ? 'bg-rose-500/15 text-rose-400 border-rose-500/40 hover:bg-rose-500/25'
              : 'bg-amber-500/20 text-amber-400 border-amber-500/50 hover:bg-amber-500/30 ring-1 ring-amber-500/30'
          }`}
          title={demoMode ? 'Switch to Real Camera Feeds (Production Mode)' : 'Switch to Scenario Simulation Mode'}
        >
          <span className={`w-2 h-2 rounded-full shrink-0 ${!demoMode ? 'bg-rose-500 animate-pulse' : 'bg-amber-500'}`} />
          <span className="material-symbols-outlined text-sm shrink-0">
            {!demoMode ? 'videocam' : 'science'}
          </span>
          <span className="text-[11px] hidden sm:inline">
            {!demoMode ? 'LIVE PRODUCTION' : 'SIMULATION MODE'}
          </span>
        </button>

        {/* Active Alerts Pill */}
        <div className="px-2.5 py-1 bg-error-container/30 border border-error/50 rounded-lg flex items-center gap-1.5 shadow-sm shrink-0 whitespace-nowrap">
          <div className="w-2 h-2 rounded-full bg-error animate-pulse shrink-0" />
          <span className="font-label-mono-bold text-xs text-error font-bold">
            {activeAlertCount} {activeAlertCount === 1 ? 'ACTIVE HAZARD' : 'ACTIVE HAZARDS'}
          </span>
        </div>

        {/* Operator Badge */}
        <div className="flex items-center gap-2 shrink-0 pl-1">
          <div className="w-7 h-7 md:w-8 md:h-8 rounded-lg bg-primary/15 border border-primary/40 flex items-center justify-center text-primary font-bold font-mono text-xs shrink-0">
            SO
          </div>
          <div className="hidden xl:flex flex-col text-left">
            <span className="font-label-mono-bold text-xs text-on-surface leading-tight font-bold">Safety Officer</span>
            <span className="text-[10px] text-on-surface-variant leading-tight">Master Console</span>
          </div>
        </div>
      </div>
    </header>
  );
};
