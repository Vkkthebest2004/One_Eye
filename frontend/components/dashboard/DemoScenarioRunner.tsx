import React, { useState } from 'react';
import { Sparkles, HardHat, AlertOctagon, Compass, Flame, ArrowDownCircle, Check, Loader2 } from 'lucide-react';
import { triggerDemoScenario } from '@/lib/api';

interface DemoScenarioRunnerProps {
  onScenarioTriggered?: () => void;
}

export const DemoScenarioRunner: React.FC<DemoScenarioRunnerProps> = ({ onScenarioTriggered }) => {
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);

  const scenarios = [
    {
      id: 'missing_helmet',
      title: '1. PPE Violation',
      desc: 'Worker #07 missing mandatory hardhat',
      icon: <HardHat className="w-3.5 h-3.5 text-amber-400" />,
      color: 'hover:border-amber-500/60 hover:bg-amber-500/10',
    },
    {
      id: 'restricted_zone',
      title: '2. Zone Breach',
      desc: 'Worker enters Hydraulic Press danger boundary',
      icon: <AlertOctagon className="w-3.5 h-3.5 text-orange-400" />,
      color: 'hover:border-orange-500/60 hover:bg-orange-500/10',
    },
    {
      id: 'proximity_danger',
      title: '3. Machine Proximity',
      desc: 'Worker at 1.1m + Zone + 8.4s exposure (Risk 86)',
      icon: <Compass className="w-3.5 h-3.5 text-hazard-critical" />,
      color: 'hover:border-hazard-critical/60 hover:bg-hazard-critical/10',
    },
    {
      id: 'fire_smoke',
      title: '4. Fire / Smoke',
      desc: 'Thermal flame pattern detected (Risk 95)',
      icon: <Flame className="w-3.5 h-3.5 text-red-400" />,
      color: 'hover:border-red-500/60 hover:bg-red-500/10',
    },
    {
      id: 'worker_fall',
      title: '5. Worker Fall',
      desc: 'Multi-frame posture drop & ground contact',
      icon: <ArrowDownCircle className="w-3.5 h-3.5 text-purple-400" />,
      color: 'hover:border-purple-500/60 hover:bg-purple-500/10',
    },
  ];

  const handleTrigger = async (id: string) => {
    setActiveScenario(id);
    setLastSuccess(null);
    try {
      await triggerDemoScenario(id, 'CAM_01', 7);
      setLastSuccess(id);
      if (onScenarioTriggered) onScenarioTriggered();
    } catch (e) {
      console.error('Failed to trigger scenario:', e);
    } finally {
      setActiveScenario(null);
      setTimeout(() => setLastSuccess(null), 3000);
    }
  };

  return (
    <div className="bg-industrial-900/90 backdrop-blur rounded-xl border border-industrial-border p-3 flex flex-col gap-2.5">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-mono font-bold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
          <Sparkles className="w-3.5 h-3.5 text-cyan-400" />
          Interactive Demo Scenarios Runner
        </span>
        <span className="text-[10px] font-mono text-slate-500">
          Click any hazard scenario to test live CV risk escalation & alert dispatch
        </span>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-2">
        {scenarios.map((sc) => {
          const isLoading = activeScenario === sc.id;
          const isTriggered = lastSuccess === sc.id;

          return (
            <button
              key={sc.id}
              onClick={() => handleTrigger(sc.id)}
              disabled={activeScenario !== null}
              className={`flex flex-col text-left p-2.5 rounded-lg bg-industrial-950 border border-industrial-border transition-all duration-200 ${sc.color} ${
                isTriggered ? 'ring-1 ring-emerald-400 bg-emerald-500/15' : ''
              }`}
            >
              <div className="flex items-center justify-between w-full mb-1">
                <span className="flex items-center gap-1.5 font-mono font-bold text-xs text-white">
                  {sc.icon} {sc.title}
                </span>
                {isLoading ? (
                  <Loader2 className="w-3 h-3 text-cyan-400 animate-spin" />
                ) : isTriggered ? (
                  <Check className="w-3 h-3 text-emerald-400" />
                ) : null}
              </div>
              <p className="text-[10px] text-slate-400 leading-snug line-clamp-1">
                {sc.desc}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
