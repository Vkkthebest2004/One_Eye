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
    { id: 'dashboard', label: 'Live Monitoring', icon: 'videocam' },
    { id: 'alerts', label: 'Active Hazards', icon: 'warning' },
    { id: 'events', label: 'Incident Audit', icon: 'history' },
    { id: 'zones', label: 'Restricted Zones', icon: 'polyline' },
    { id: 'analytics', label: 'Risk Analytics', icon: 'insights' },
    { id: 'settings', label: 'System Settings', icon: 'settings' },
  ];

  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpenMobile && (
        <div
          onClick={onCloseMobile}
          className="fixed inset-0 bg-black/80 backdrop-blur-sm z-40 md:hidden transition-opacity"
        />
      )}

      {/* Main Sidebar Container */}
      <nav
        className={`bg-surface flex flex-col h-screen fixed left-0 top-0 py-4 z-50 border-r border-white/5 w-60 shrink-0 transition-transform duration-300 ${
          isOpenMobile ? 'translate-x-0' : '-translate-x-full md:translate-x-0'
        } custom-scrollbar`}
      >
        {/* Brand Header */}
        <div className="px-4 mb-4 shrink-0">
          <div className="flex items-center justify-between">
            <a href="/" className="flex items-center gap-2.5 group">
              <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/30 flex items-center justify-center text-blue-400 group-hover:scale-105 transition-transform">
                <span className="material-symbols-outlined text-lg">visibility</span>
              </div>
              <div>
                <h1 className="font-bold text-sm tracking-wider text-white font-mono">ONE EYE</h1>
                <p className="font-mono text-[10px] text-slate-400">Vision Intelligence</p>
              </div>
            </a>

            {/* Close Button on Mobile */}
            {isOpenMobile && (
              <button
                onClick={onCloseMobile}
                className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-white"
              >
                <span className="material-symbols-outlined text-xl">close</span>
              </button>
            )}
          </div>
        </div>

        {/* Scrollable Navigation Items */}
        <div className="flex-1 overflow-y-auto custom-scrollbar px-2 space-y-1 min-h-0">
          <div className="px-2 py-1 text-[10px] font-mono uppercase tracking-widest text-slate-500 font-semibold">
            Console Views
          </div>
          {navItems.map((item) => {
            const isActive = activeTab === item.id;
            return (
              <button
                key={item.id}
                onClick={() => {
                  setActiveTab(item.id);
                  if (onCloseMobile) onCloseMobile();
                }}
                className={`w-full flex items-center justify-between px-3 py-2 rounded-lg text-left transition-all text-xs font-mono ${
                  isActive
                    ? 'bg-blue-600/15 text-blue-400 border border-blue-500/30 font-medium'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                <div className="flex items-center gap-2.5 min-w-0">
                  <span className={`material-symbols-outlined text-base shrink-0 ${isActive ? 'text-blue-400' : 'text-slate-400'}`}>
                    {item.icon}
                  </span>
                  <span className="truncate">{item.label}</span>
                </div>
                {item.id === 'alerts' && activeAlertCount > 0 && (
                  <span className="px-1.5 py-0.2 rounded bg-red-500 text-white font-mono text-[10px] animate-pulse shrink-0 ml-1">
                    {activeAlertCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        {/* Bottom Auxiliary Section */}
        <div className="px-2 mt-auto pt-3 border-t border-white/5 shrink-0 space-y-1">
          <a
            href="/landing"
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all text-xs font-mono"
          >
            <div className="flex items-center gap-2.5">
              <span className="material-symbols-outlined text-base">home</span>
              <span>Landing Page</span>
            </div>
            <span className="material-symbols-outlined text-xs text-slate-500">arrow_outward</span>
          </a>

          <a
            href="/mobile-cam"
            target="_blank"
            rel="noreferrer"
            className="w-full flex items-center justify-between px-3 py-2 rounded-lg text-slate-400 hover:text-white hover:bg-white/5 transition-all text-xs font-mono"
          >
            <div className="flex items-center gap-2.5">
              <span className="material-symbols-outlined text-base">phone_iphone</span>
              <span>Mobile Cam</span>
            </div>
            <span className="material-symbols-outlined text-xs text-slate-500">arrow_outward</span>
          </a>
        </div>
      </nav>
    </>
  );
};
