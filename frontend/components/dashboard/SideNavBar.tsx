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
  isOpenMobile?: boolean;
  onCloseMobile?: () => void;
}

export const SideNavBar: React.FC<SideNavBarProps> = ({
  activeTab,
  setActiveTab,
  activeAlertCount,
  demoMode = false,
  isOpenMobile = false,
  onCloseMobile,
}) => {
  const navItems: Array<{ id: TabType; label: string; icon: string }> = [
    { id: 'dashboard', label: 'Dashboard', icon: 'dashboard' },
    { id: 'monitoring', label: 'Live Monitoring', icon: 'videocam' },
    { id: 'alerts', label: 'Active Alerts', icon: 'warning' },
    { id: 'events', label: 'Events Audit', icon: 'history' },
    { id: 'cameras', label: 'Cameras', icon: 'videocam_off' },
    { id: 'zones', label: 'Restricted Zones', icon: 'polyline' },
    { id: 'analytics', label: 'Analytics', icon: 'insights' },
    { id: 'map', label: 'Safety Map', icon: 'map' },
    { id: 'settings', label: 'Settings', icon: 'settings' },
    { id: 'mobile', label: 'Mobile Camera', icon: 'usb' },
  ];

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpenMobile && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/70 backdrop-blur-sm z-40 md:hidden transition-opacity"
        />
      )}

      {/* Main Sidebar Container */}
      <nav
        className={`bg-surface-container flex flex-col h-screen fixed left-0 top-0 py-4 z-50 border-r border-outline-variant w-64 shrink-0 transition-transform duration-300 ${
          isOpenMobile ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        } custom-scrollbar`}
      >
        {/* Brand Header */}
        <div className="px-4 mb-4 shrink-0">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <span
                className="material-symbols-outlined text-primary text-3xl"
                style={{ fontVariationSettings: "'FILL' 1" }}
              >
                visibility
              </span>
              <div>
                <h1 className="font-headline-md text-xl text-primary font-bold tracking-tight">ONE EYE</h1>
                <p className="font-label-mono text-[11px] text-on-surface-variant">Safety Intelligence</p>
              </div>
            </div>

            {/* Close Button on Mobile */}
            {isOpenMobile && (
              <button
                onClick={onCloseMobile}
                className="md:hidden p-1.5 rounded-lg text-on-surface-variant hover:bg-surface-variant"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            )}
          </div>

          {/* Operational Mode Badge */}
          <div className={`mt-3 px-2.5 py-1 rounded inline-flex items-center gap-1.5 shadow-sm border w-full justify-center ${
            !demoMode
              ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
              : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${!demoMode ? 'bg-emerald-500 animate-pulse' : 'bg-amber-500'}`} />
            <span className="font-label-mono-bold text-[10px] tracking-wider uppercase font-bold truncate">
              {!demoMode ? 'LIVE PRODUCTION' : 'DEMO SIMULATION'}
            </span>
          </div>
        </div>

        {/* Scrollable Navigation Items */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-2 space-y-1 min-h-0">
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-all active:scale-[0.98] ${
                  isActive
                    ? 'bg-secondary-container text-on-secondary-container border-l-4 border-primary font-label-mono-bold shadow-sm'
                    : 'text-on-surface-variant hover:bg-surface-variant/60 font-label-mono'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <span className="material-symbols-outlined text-xl shrink-0">{item.icon}</span>
                  <span className="text-sm font-medium truncate">{item.label}</span>
                </div>
                {item.id === 'alerts' && activeAlertCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded bg-error text-white font-label-mono-bold text-[10px] animate-pulse shrink-0 ml-1">
                    {activeAlertCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom Auxiliary Section */}
        <div className="px-2 mt-auto pt-3 border-t border-outline-variant shrink-0 space-y-1">
          <button
            onClick={() => {
              setActiveTab('logs');
              if (onCloseMobile) onCloseMobile();
            }}
            className={`w-full flex items-center gap-3 px-3 py-2 rounded-lg text-on-surface-variant hover:bg-surface-variant/60 transition-all ${
              activeTab === 'logs' ? 'bg-secondary-container font-label-mono-bold' : 'font-label-mono'
            }`}
          >
            <span className="material-symbols-outlined text-xl">terminal</span>
            <span className="text-sm font-medium">Terminal Logs</span>
          </button>
        </div>
      </nav>
    </>
  );
};
