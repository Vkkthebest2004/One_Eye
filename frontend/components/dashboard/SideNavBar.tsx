import React from 'react';

export type TabType =
  | 'dashboard'
  | 'monitoring'
  | 'alerts'
  | 'events'
  | 'cameras'
  | 'zones'
  | 'analytics'
  | 'map'
  | 'settings'
  | 'mobile'
  | 'logs';

interface SideNavBarProps {
  activeTab: TabType;
  setActiveTab: (tab: TabType) => void;
  activeAlertCount: number;
  demoMode?: boolean;
}

export const SideNavBar: React.FC<SideNavBarProps> = ({
  activeTab,
  setActiveTab,
  activeAlertCount,
  demoMode = false,
}) => {
  const navItems: Array<{ id: TabType; label: string; icon: string }> = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
    { id: 'monitoring', label: 'Live Monitoring', icon: 'videocam' },
    { id: 'alerts', label: 'Alerts', icon: 'warning' },
    { id: 'events', label: 'Events', icon: 'history' },
    { id: 'cameras', label: 'Cameras', icon: 'videocam_off' },
    { id: 'zones', label: 'Zones', icon: 'polyline' },
    { id: 'analytics', label: 'Analytics', icon: 'insights' },
    { id: 'map', label: 'Safety Map', icon: 'map' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
    { id: 'mobile', label: 'Mobile USB', icon: 'usb' },
  ];

  return (
    <nav className="bg-surface-container flex flex-col h-screen fixed left-0 top-0 py-panel-padding z-40 border-r border-outline-variant w-64 shrink-0 hidden md:flex">
      {/* Brand Header */}
      <div className="px-gutter mb-6">
        <div className="flex items-center gap-3">
          <span
            className="material-symbols-outlined text-primary text-3xl"
            style={{ fontVariationSettings: "'FILL' 1" }}
          >
            visibility
          </span>
          <div>
            <h1 className="font-headline-md text-xl text-primary font-bold tracking-tight">ONE_EYE</h1>
            <p className="font-label-mono text-xs text-on-surface-variant">Vigilant v2.4</p>
          </div>
        </div>
        <div className={`mt-3 px-2 py-1 rounded inline-flex items-center gap-1.5 shadow-sm border ${
          !demoMode
            ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600'
            : 'bg-amber-500/10 border-amber-500/30 text-amber-600'
        }`}>
          <span className={`w-2 h-2 rounded-full ${!demoMode ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
          <span className="font-label-mono-bold text-[11px] tracking-wider">
            {!demoMode ? 'LIVE MODE (PROD)' : 'DEMO MODE'}
          </span>
        </div>
      </div>

      {/* Main Navigation Links */}
      <div className="flex-1 overflow-y-auto px-2 space-y-1">
        {navItems.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id)}
              className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-all active:opacity-80 ${
                isActive
                  ? 'bg-secondary-container text-on-secondary-container border-l-4 border-primary font-label-mono-bold shadow-sm'
                  : 'text-on-surface-variant hover:bg-surface-variant font-label-mono'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="material-symbols-outlined text-xl">{item.icon}</span>
                <span className="text-sm font-medium">{item.label}</span>
              </div>
              {item.id === 'alerts' && activeAlertCount > 0 && (
                <span className="px-1.5 py-0.5 rounded bg-error text-white font-label-mono-bold text-[10px] animate-pulse">
                  {activeAlertCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Bottom Auxiliary Links */}
      <div className="px-2 mt-auto pt-4 space-y-1 border-t border-outline-variant">
        <button
          onClick={() => setActiveTab('logs')}
          className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-variant transition-all ${
            activeTab === 'logs' ? 'bg-secondary-container font-label-mono-bold' : 'font-label-mono'
          }`}
        >
          <span className="material-symbols-outlined text-xl">terminal</span>
          <span className="text-sm">Logs</span>
        </button>
      </div>
    </nav>
  );
};
