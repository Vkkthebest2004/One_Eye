'use client';

import React, { useState, useEffect } from 'react';
import { SideNavBar, TabType } from '@/components/dashboard/SideNavBar';
import { TopNavBar } from '@/components/dashboard/TopNavBar';
import { KpiRow } from '@/components/dashboard/KpiRow';
import { MonitoringArray } from '@/components/dashboard/MonitoringArray';
import { EventStreamSidebar } from '@/components/dashboard/EventStreamSidebar';
import { AlertCenterTab } from '@/components/dashboard/AlertCenterTab';
import { AnalyticsTab } from '@/components/dashboard/AnalyticsTab';
import { SafetyMapTab } from '@/components/dashboard/SafetyMapTab';
import { EventsAuditTab } from '@/components/dashboard/EventsAuditTab';
import { SettingsTab } from '@/components/dashboard/SettingsTab';
import { ForensicDetailModal } from '@/components/dashboard/ForensicDetailModal';

import { Camera, Zone, Machine, SafetyEvent, SystemHealth, AnalyticsSummary } from '@/types';
import {
  getCameras,
  getZones,
  getMachines,
  getHealth,
  getAnalyticsSummary,
  getEvents,
  acknowledgeEvent,
  resolveEvent,
  markFalsePositive,
} from '@/lib/api';
import { useOneEyeWebSocket } from '@/lib/websocket';

export default function HomeSurveillanceDashboard() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  
  // Default with active primary channel so stream begins instantly
  const [cameras, setCameras] = useState<Camera[]>([
    {
      id: 'CAM_WEBCAM',
      name: 'Laptop Built-in Webcam (FaceTime HD)',
      source: '0',
      source_type: 'webcam',
      fps: 30.0,
      resolution: '1280x720',
      status: 'ONLINE',
      is_calibrated: true,
      created_at: new Date().toISOString(),
    },
  ]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<SafetyEvent | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [demoMode, setDemoMode] = useState<boolean>(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState<boolean>(false);

  // WebSocket Live Hook
  const {
    isConnected,
    activeAlerts,
    cameraTracks,
    cameraDetections,
    cameraFps,
    visualZones,
    cameraIntrusions,
    setActiveAlerts,
  } = useOneEyeWebSocket();

  const loadData = async () => {
    try {
      const [cams, zns, machs, hlth, summ, eventsResult] = await Promise.all([
        getCameras(),
        getZones(),
        getMachines(),
        getHealth(),
        getAnalyticsSummary(),
        getEvents({ limit: 200 }),
      ]);
      if (cams && cams.length > 0) {
        setCameras(cams);
      }
      setZones(zns || []);
      setMachines(machs || []);
      setHealth(hlth);
      setSummary(summ);
      if (eventsResult && eventsResult.events) {
        const active = eventsResult.events.filter(
          (event) => event.status === 'ALERTING' || event.status === 'ACKNOWLEDGED'
        );
        const priority: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, ADVISORY: 1 };
        setActiveAlerts(active.sort((a, b) => (priority[b.severity] || 0) - (priority[a.severity] || 0)));
      }
    } catch (e) {
      console.error('Failed to load surveillance data:', e);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(async () => {
      try {
        const [hlth, summ] = await Promise.all([getHealth(), getAnalyticsSummary()]);
        setHealth(hlth);
        setSummary(summ);
      } catch (e) {
        // silent
      }
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  // Alert Handlers
  const handleAcknowledge = async (id: string) => {
    try {
      const updated = await acknowledgeEvent(id, 'OPERATOR_01');
      setActiveAlerts((prev) => prev.map((a) => (a.id === id ? updated : a)));
      if (selectedEvent?.id === id) setSelectedEvent(updated);
    } catch (e) {
      console.error('Failed to acknowledge:', e);
    }
  };

  const handleResolve = async (id: string) => {
    try {
      await resolveEvent(id, 'OPERATOR_01');
      setActiveAlerts((prev) => prev.filter((a) => a.id !== id));
      if (selectedEvent?.id === id) setSelectedEvent(null);
    } catch (e) {
      console.error('Failed to resolve:', e);
    }
  };

  const handleMarkFalsePositive = async (id: string, notes: string) => {
    try {
      await markFalsePositive(id, notes, 'OPERATOR_01');
      setActiveAlerts((prev) => prev.filter((a) => a.id !== id));
      if (selectedEvent?.id === id) setSelectedEvent(null);
    } catch (e) {
      console.error('Failed to mark false positive:', e);
    }
  };

  const totalTracksCount = Object.values(cameraTracks).reduce((acc, trks) => acc + trks.length, 0);

  return (
    <div className="flex h-screen w-full antialiased bg-background text-on-surface overflow-hidden">
      {/* Side Navigation Bar */}
      <SideNavBar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeAlertCount={activeAlerts.length}
        demoMode={demoMode}
        isOpenMobile={isMobileMenuOpen}
        onCloseMobile={() => setIsMobileMenuOpen(false)}
      />

      {/* Main Content Area */}
      <main className="md:ml-60 flex-1 flex flex-col h-screen overflow-hidden min-w-0">
        {/* Top App Bar */}
        <TopNavBar
          health={health}
          activeAlertCount={activeAlerts.length}
          onSearchChange={setSearchQuery}
          onDemoModeChanged={setDemoMode}
          onOpenMobileMenu={() => setIsMobileMenuOpen(true)}
        />

        {/* Scrollable Dashboard View Canvas with Rigid Scroll Bounds */}
        <div className="flex-1 overflow-y-auto custom-scrollbar p-3 md:p-4 flex flex-col gap-3 min-h-0 w-full">
          {/* Minimal 4-Metric Telemetry Strip */}
          <div className="shrink-0">
            <KpiRow
              summary={summary}
              activeCount={activeAlerts.length}
              totalTrackedWorkers={totalTracksCount}
            />
          </div>

          {/* Tab 1 & 2: Dashboard / Live Monitoring Array */}
          {(activeTab === 'dashboard' || activeTab === 'monitoring') && (
            <div className="grid grid-cols-12 gap-3 flex-1 min-h-0 items-start pb-4">
              {/* Left: Camera Feed Array (8-9 cols on desktop) */}
              <div className="col-span-12 lg:col-span-8 xl:col-span-9 flex flex-col min-w-0 min-h-0">
                <MonitoringArray
                  cameras={cameras}
                  zones={zones}
                  machines={machines}
                  cameraTracks={cameraTracks}
                  cameraDetections={cameraDetections}
                  cameraFps={cameraFps}
                  visualZones={visualZones}
                  cameraIntrusions={cameraIntrusions}
                  onZonesUpdated={loadData}
                />
              </div>

              {/* Right: Live Event Stream & Incident Queue (3-4 cols on desktop) */}
              <div className="col-span-12 lg:col-span-4 xl:col-span-3 flex flex-col min-w-0 min-h-0 lg:sticky lg:top-0 max-h-[calc(100vh-140px)]">
                <EventStreamSidebar
                  alerts={activeAlerts}
                  onSelectEvent={setSelectedEvent}
                  onAcknowledge={handleAcknowledge}
                  onResolve={handleResolve}
                />
              </div>
            </div>
          )}

          {/* Tab 3: Alerts Center */}
          {activeTab === 'alerts' && (
            <div className="flex-1 min-h-0 pb-6">
              <AlertCenterTab
                alerts={activeAlerts}
                onSelectEvent={setSelectedEvent}
                onAcknowledge={handleAcknowledge}
                onResolve={handleResolve}
              />
            </div>
          )}

          {/* Tab 4: Events & Audit History */}
          {(activeTab === 'events' || activeTab === 'logs') && (
            <div className="flex-1 min-h-0 pb-6">
              <EventsAuditTab onSelectEvent={setSelectedEvent} />
            </div>
          )}

          {/* Tab 5: Safety Map */}
          {activeTab === 'map' && (
            <div className="flex-1 min-h-0 pb-6">
              <SafetyMapTab
                cameras={cameras}
                zones={zones}
                machines={machines}
                tracks={cameraTracks}
                alerts={activeAlerts}
              />
            </div>
          )}

          {/* Tab 6: Analytics */}
          {activeTab === 'analytics' && (
            <div className="flex-1 min-h-0 pb-6">
              <AnalyticsTab />
            </div>
          )}

          {/* Tab 7: Settings / Cameras / Zones */}
          {(activeTab === 'settings' || activeTab === 'cameras' || activeTab === 'zones') && (
            <div className="flex-1 min-h-0 pb-6">
              <SettingsTab
                cameras={cameras}
                zones={zones}
                machines={machines}
                onConfigSaved={loadData}
              />
            </div>
          )}
        </div>
      </main>

      {/* Forensic Evidence Modal */}
      <ForensicDetailModal
        event={selectedEvent}
        onClose={() => setSelectedEvent(null)}
        onAcknowledge={handleAcknowledge}
        onResolve={handleResolve}
        onMarkFalsePositive={handleMarkFalsePositive}
      />
    </div>
  );
}
