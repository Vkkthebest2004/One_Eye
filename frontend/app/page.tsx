'use client';

import React, { useState, useEffect } from 'react';
import { SideNavBar, TabType } from '@/components/dashboard/SideNavBar';
import { TopNavBar } from '@/components/dashboard/TopNavBar';
import { KpiRow } from '@/components/dashboard/KpiRow';
import { DemoScenariosBar } from '@/components/dashboard/DemoScenariosBar';
import { MonitoringArray } from '@/components/dashboard/MonitoringArray';
import { EventStreamSidebar } from '@/components/dashboard/EventStreamSidebar';
import { AlertCenterTab } from '@/components/dashboard/AlertCenterTab';
import { AnalyticsTab } from '@/components/dashboard/AnalyticsTab';
import { SafetyMapTab } from '@/components/dashboard/SafetyMapTab';
import { EventsAuditTab } from '@/components/dashboard/EventsAuditTab';
import { SettingsTab } from '@/components/dashboard/SettingsTab';
import { MobileConnectionTab } from '@/components/dashboard/MobileConnectionTab';
import { ForensicDetailModal } from '@/components/dashboard/ForensicDetailModal';

import { Camera, Zone, Machine, SafetyEvent, SystemHealth, AnalyticsSummary } from '@/types';
import {
  getCameras,
  getZones,
  getMachines,
  getHealth,
  getAnalyticsSummary,
  acknowledgeEvent,
  resolveEvent,
  markFalsePositive,
} from '@/lib/api';
import { useOneEyeWebSocket } from '@/lib/websocket';

export default function DashboardPage() {
  const [activeTab, setActiveTab] = useState<TabType>('dashboard');
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [zones, setZones] = useState<Zone[]>([]);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [health, setHealth] = useState<SystemHealth | null>(null);
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<SafetyEvent | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [demoMode, setDemoMode] = useState<boolean>(false);

  // WebSocket Live Hook
  const {
    isConnected,
    activeAlerts,
    cameraTracks,
    cameraDetections,
    cameraFps,
    setActiveAlerts,
  } = useOneEyeWebSocket();

  const loadData = async () => {
    try {
      const [cams, zns, machs, hlth, summ] = await Promise.all([
        getCameras(),
        getZones(),
        getMachines(),
        getHealth(),
        getAnalyticsSummary(),
      ]);
      setCameras(cams);
      setZones(zns);
      setMachines(machs);
      setHealth(hlth);
      setSummary(summ);
    } catch (e) {
      console.error('Failed to load initial data:', e);
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
    <div className="flex h-screen w-full antialiased grid-bg bg-background text-on-surface">
      {/* Side Navigation Bar */}
      <SideNavBar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        activeAlertCount={activeAlerts.length}
        demoMode={demoMode}
      />

      {/* Main Content Area */}
      <main className="md:ml-64 flex-1 flex flex-col h-screen overflow-hidden">
        {/* Top App Bar */}
        <TopNavBar
          health={health}
          activeAlertCount={activeAlerts.length}
          onSearchChange={setSearchQuery}
          onDemoModeChanged={setDemoMode}
        />

        {/* Scrollable Dashboard View Canvas */}
        <div className="flex-1 overflow-y-auto p-margin-page flex flex-col gap-4">
          
          {/* Top Title & Demo Runner Bar */}
          <div className="flex flex-col gap-2">
            <div className="flex justify-between items-end">
              <div>
                <h2 className="font-headline-md text-xl font-bold text-on-surface tracking-tight">
                  Good morning, Operator
                </h2>
                <p className="font-label-mono text-xs text-on-surface-variant uppercase mt-0.5">
                  Industrial Safety Command Center // Plant Sector 01
                </p>
              </div>
            </div>

            {/* 1-Click Interactive Hazard Scenarios Bar (Only shown when Demo Simulation Mode is enabled) */}
            {demoMode && (
              <DemoScenariosBar onScenarioTriggered={loadData} />
            )}
          </div>

          {/* 5 KPI Metric Cards Row */}
          <KpiRow
            summary={summary}
            activeCount={activeAlerts.length}
            totalTrackedWorkers={totalTracksCount}
          />

          {/* Tab 1 & 2: Dashboard / Live Monitoring Array */}
          {(activeTab === 'dashboard' || activeTab === 'monitoring') && (
            <div className="grid grid-cols-12 gap-gutter min-h-[580px] flex-1">
              {/* Left: 2x2 Camera Monitoring Array (9 cols) */}
              <div className="col-span-12 lg:col-span-9 flex flex-col">
                <MonitoringArray
                  cameras={cameras}
                  zones={zones}
                  machines={machines}
                  cameraTracks={cameraTracks}
                  cameraDetections={cameraDetections}
                  cameraFps={cameraFps}
                />
              </div>

              {/* Right: Live Event Stream & Incident Card (3 cols) */}
              <div className="col-span-12 lg:col-span-3 flex flex-col">
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
            <AlertCenterTab
              alerts={activeAlerts}
              onSelectEvent={setSelectedEvent}
              onAcknowledge={handleAcknowledge}
              onResolve={handleResolve}
            />
          )}

          {/* Tab 4: Events & Audit History */}
          {(activeTab === 'events' || activeTab === 'logs') && (
            <EventsAuditTab onSelectEvent={setSelectedEvent} />
          )}

          {/* Tab 5: Safety Map */}
          {activeTab === 'map' && (
            <SafetyMapTab
              cameras={cameras}
              zones={zones}
              machines={machines}
              tracks={cameraTracks}
              alerts={activeAlerts}
            />
          )}

          {/* Tab 6: Analytics */}
          {activeTab === 'analytics' && <AnalyticsTab />}

          {/* Tab 7: Settings / Cameras / Zones */}
          {(activeTab === 'settings' || activeTab === 'cameras' || activeTab === 'zones') && (
            <SettingsTab
              cameras={cameras}
              zones={zones}
              machines={machines}
              onConfigSaved={loadData}
            />
          )}

          {/* Tab 8: Mobile USB Connection */}
          {activeTab === 'mobile' && <MobileConnectionTab onDeviceConnected={loadData} />}

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
