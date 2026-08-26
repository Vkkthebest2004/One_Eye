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
      title: '1. PPE Compliance Test',
      desc: 'Worker without hardhat or vest',
      icon: 'engineering',
      color: 'text-severity-warning',
    },
    {
      id: 'restricted_zone',
      title: '2. No-Entry Zone Breach',
      desc: 'Foot-anchor crosses safety perimeter',
      icon: 'emergency',
      color: 'text-severity-warning',
    },
    {
      id: 'proximity_danger',
      title: '3. Machine Proximity Risk',
      desc: 'Worker < 1.5m from running machine',
      icon: 'warning',
      color: 'text-severity-critical',
    },
    {
      id: 'fire_smoke',
      title: '4. Fire & Smoke Outbreak',
      desc: 'Plant-wide flame and smoke plume',
      icon: 'local_fire_department',
      color: 'text-severity-critical',
    },
    {
      id: 'worker_fall',
      title: '5. Worker Fall & Collapse',
      desc: 'Rapid posture drop and immobility',
      icon: 'person_off',
      color: 'text-primary',
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
    <div className="level-1-panel rounded-lg p-2.5 flex flex-col gap-2 shadow-sm mb-2 shrink-0">
      <div className="flex items-center justify-between">
        <span className="font-label-mono-bold text-xs uppercase tracking-wider text-on-surface flex items-center gap-1.5 font-bold">
          <span className="material-symbols-outlined text-primary text-sm">science</span>
          Safety Test Runner &amp; Hazard Simulation
        </span>
        <span className="font-label-mono text-[10px] text-on-surface-variant hidden sm:inline">
          Click any scenario to simulate real-time AI detection &amp; risk escalation
        </span>
      </div>

      <div className="flex lg:grid lg:grid-cols-5 gap-2 overflow-x-auto sliding-scroll-container pb-0.5">
        {scenarios.map((sc) => {
          const isLoading = activeScenario === sc.id;
          const isTriggered = lastSuccess === sc.id;

          return (
            <button
              key={sc.id}
              onClick={() => handleTrigger(sc.id)}
              disabled={activeScenario !== null}
              className={`flex flex-col text-left p-2 rounded-lg bg-surface border border-outline-variant transition-all shrink-0 min-w-[180px] lg:min-w-0 active:scale-98 ${
                isTriggered
                  ? 'ring-1 ring-severity-safe bg-severity-safe/10 border-severity-safe'
                  : 'hover:bg-surface-container'
              }`}
            >
              <div className="flex items-center justify-between w-full mb-0.5">
                <span className="flex items-center gap-1 font-label-mono-bold text-xs text-on-surface font-bold">
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
              <p className="font-label-mono text-[10px] text-on-surface-variant truncate">
                {sc.desc}
              </p>
            </button>
          );
        })}
      </div>
    </div>
  );
};
