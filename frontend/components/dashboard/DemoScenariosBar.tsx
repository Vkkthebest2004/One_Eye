import React, { useState } from 'react';
import { triggerDemoScenario } from '@/lib/api';

interface DemoScenariosBarProps {
  onScenarioTriggered?: () => void;
}

export const DemoScenariosBar: React.FC<DemoScenariosBarProps> = ({ onScenarioTriggered }) => {
  const [activeScenario, setActiveScenario] = useState<string | null>(null);
  const [lastSuccess, setLastSuccess] = useState<string | null>(null);

  const scenarios = [
    {
      id: 'missing_helmet',
      title: '1. PPE Violation',
      desc: 'Worker #07 missing mandatory hardhat',
      icon: 'engineering',
      color: 'hover:border-severity-warning text-severity-warning',
    },
    {
      id: 'restricted_zone',
      title: '2. Zone Breach',
      desc: 'Worker enters Hydraulic Press danger boundary',
      icon: 'emergency',
      color: 'hover:border-severity-warning text-severity-warning',
    },
    {
      id: 'proximity_danger',
      title: '3. Machine Proximity',
      desc: 'Worker at 1.1m + Zone + 8.4s exposure (Risk 86)',
      icon: 'warning',
      color: 'hover:border-severity-critical text-severity-critical',
    },
    {
      id: 'fire_smoke',
      title: '4. Fire / Smoke',
      desc: 'Thermal flame pattern detected (Risk 95)',
      icon: 'local_fire_department',
      color: 'hover:border-severity-critical text-severity-critical',
    },
    {
      id: 'worker_fall',
      title: '5. Worker Fall',
      desc: 'Multi-frame posture drop & ground contact',
      icon: 'person_off',
      color: 'hover:border-primary text-primary',
    },
  ];

  const handleTrigger = async (id: string) => {
    setActiveScenario(id);
    setLastSuccess(null);
    try {
      await triggerDemoScenario(id, 'CAM_03', 7);
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
    <div className="level-1-panel rounded-lg p-2.5 flex flex-col gap-2 shadow-sm mb-2">
      <div className="flex items-center justify-between">
        <span className="font-label-mono-bold text-xs uppercase tracking-wider text-on-surface flex items-center gap-1.5">
          <span className="material-symbols-outlined text-primary text-sm">science</span>
          Interactive Demo Hazard Scenarios
        </span>
        <span className="font-label-mono text-[10px] text-on-surface-variant">
          Click any hazard to test real-time risk escalation &amp; alert dispatch
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
              className={`flex flex-col text-left p-2 rounded bg-surface border border-outline-variant transition-all ${
                isTriggered
                  ? 'ring-1 ring-severity-safe bg-severity-safe/10 border-severity-safe'
                  : 'hover:bg-surface-container'
              }`}
            >
              <div className="flex items-center justify-between w-full mb-0.5">
                <span className="flex items-center gap-1 font-label-mono-bold text-xs text-on-surface">
                  <span className={`material-symbols-outlined text-sm ${sc.color}`}>
                    {sc.icon}
                  </span>
                  {sc.title}
                </span>
                {isLoading ? (
                  <span className="material-symbols-outlined text-xs text-primary animate-spin">
                    sync
                  </span>
                ) : isTriggered ? (
                  <span className="material-symbols-outlined text-xs text-severity-safe">
                    check
                  </span>
                ) : null}
              </div>
              <p className="font-label-mono text-[10px] text-on-surface-variant line-clamp-1">
                {sc.desc}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
