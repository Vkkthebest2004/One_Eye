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

    // Read stored preference first, then sync with server
    const cachedMode = typeof window !== 'undefined' ? localStorage.getItem('oneeye_perception_mode') : null;
    if (cachedMode && ['YOLO', 'QWEN_VL', 'HYBRID'].includes(cachedMode)) {
      setPerceptionState(cachedMode as any);
    } else {
      setPerceptionState('YOLO');
    }

    getPerceptionMode()
      .then((res) => {
        setPerceptionState(res.perception_mode as any);
        if (typeof window !== 'undefined') {
          localStorage.setItem('oneeye_perception_mode', res.perception_mode);
        }
      })
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
      QWEN_VL: 'HYBRID',
      HYBRID: 'YOLO',
      YOLO: 'QWEN_VL',
    };
    const nextMode = cycleMap[perceptionMode] || 'QWEN_VL';
    setIsChangingMode(true);
    try {
      const res = await setPerceptionMode(nextMode, true);
      setPerceptionState(res.perception_mode as any);
      if (typeof window !== 'undefined') {
        localStorage.setItem('oneeye_perception_mode', res.perception_mode);
      }
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
    <header className="bg-surface/95 backdrop-blur-md flex justify-between items-center w-full px-3 md:px-5 h-13 z-30 border-b border-white/5 shrink-0 max-w-full overflow-hidden">
      {/* Left: Mobile Menu Trigger, Brand Logo, & Landing Link */}
      <div className="flex items-center gap-3 shrink-0 min-w-0">
        <button
          onClick={onOpenMobileMenu}
          className="md:hidden p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-variant focus:outline-none"
          title="Open Navigation Menu"
        >
          <span className="material-symbols-outlined text-xl">menu</span>
        </button>

        <div className="flex items-center gap-2.5 min-w-0">
          <a
            href="/"
            className="flex items-center gap-2 group hover:opacity-90 transition-opacity"
            title="Return to Landing Page"
          >
            <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
              <span className="material-symbols-outlined text-base">visibility</span>
            </div>
            <span className="font-bold text-sm tracking-tight text-white font-mono">
              ONE EYE
            </span>
          </a>

          <a
            href="/"
            className="hidden sm:inline-flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-white px-2 py-0.5 rounded border border-white/5 hover:border-white/20 transition-all"
          >
            <span className="material-symbols-outlined text-[13px]">arrow_back</span>
            Landing
          </a>

          <span className="hidden lg:inline-block text-[11px] font-mono text-slate-500">
            {timeStr}
          </span>
        </div>
      </div>

      {/* Right Controls: Minimal & Non-Distracting */}
      <div className="flex items-center gap-2 md:gap-3 shrink-0 py-1">
        {/* Perception Mode Badge */}
        <button
          onClick={handleCyclePerceptionMode}
          disabled={isChangingMode}
          className={`hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium border transition-all active:scale-95 ${
            perceptionMode === 'QWEN_VL'
              ? 'bg-purple-500/10 text-purple-300 border-purple-500/30 hover:bg-purple-500/20'
              : perceptionMode === 'HYBRID'
              ? 'bg-cyan-500/10 text-cyan-300 border-cyan-500/30 hover:bg-cyan-500/20'
              : 'bg-blue-500/10 text-blue-300 border-blue-500/30 hover:bg-blue-500/20'
          }`}
          title="Switch Perception Engine"
        >
          <span className={`w-1.5 h-1.5 rounded-full ${
            perceptionMode === 'QWEN_VL' ? 'bg-purple-400' :
            perceptionMode === 'HYBRID' ? 'bg-cyan-400' : 'bg-blue-400'
          }`} />
          <span className="text-[11px]">
            {perceptionMode === 'QWEN_VL' ? 'Qwen-VL' : perceptionMode === 'HYBRID' ? 'Hybrid AI' : 'YOLOv8n'}
          </span>
        </button>

        {/* Master AI Safety Detection Toggle */}
        <button
          onClick={handleToggleAi}
          disabled={isTogglingAi}
          className={`flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-mono font-medium border transition-all active:scale-95 ${
            aiEnabled
              ? 'bg-emerald-500/10 text-emerald-300 border-emerald-500/30 hover:bg-emerald-500/20'
              : 'bg-amber-500/10 text-amber-300 border-amber-500/30 hover:bg-amber-500/20'
          }`}
          title={aiEnabled ? 'Pause AI Vision Detection' : 'Resume AI Vision Detection'}
        >
          <span className={`w-1.5 h-1.5 rounded-full ${aiEnabled ? 'bg-emerald-400 animate-pulse' : 'bg-amber-400'}`} />
          <span className="text-[11px]">
            {aiEnabled ? 'Detection On' : 'View Only'}
          </span>
        </button>

        {/* Active Alerts Pill */}
        <div className={`px-2 py-1 rounded-md flex items-center gap-1.5 border font-mono text-xs ${
          activeAlertCount > 0
            ? 'bg-red-500/15 border-red-500/40 text-red-300 animate-pulse'
            : 'bg-white/5 border-white/10 text-slate-400'
        }`}>
          <span className={`w-1.5 h-1.5 rounded-full ${activeAlertCount > 0 ? 'bg-red-500' : 'bg-emerald-500'}`} />
          <span className="text-[11px] font-medium">
            {activeAlertCount} {activeAlertCount === 1 ? 'Alert' : 'Alerts'}
          </span>
        </div>

        {/* Mobile Camera Link */}
        <a
          href="/mobile-cam"
          target="_blank"
          rel="noreferrer"
          className="hidden md:flex items-center gap-1 px-2.5 py-1 rounded-md bg-white/5 hover:bg-white/10 border border-white/10 text-slate-300 text-xs font-mono transition-all"
          title="Open Mobile Camera Node in new tab"
        >
          <span className="material-symbols-outlined text-sm">phone_iphone</span>
          <span className="text-[11px]">Mobile Cam</span>
        </a>
      </div>
    </header>
  );
};
