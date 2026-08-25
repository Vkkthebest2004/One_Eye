import React, { useState, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend
} from 'recharts';
import { getAnalyticsTrends, getHazardStats, getCameraRiskStats } from '@/lib/api';
import { HazardStat, CameraRiskStat } from '@/types';

export const AnalyticsTab: React.FC = () => {
  const [trends, setTrends] = useState<any[]>([]);
  const [hazards, setHazards] = useState<HazardStat[]>([]);
  const [camRankings, setCamRankings] = useState<CameraRiskStat[]>([]);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '24h'>('7d');

  useEffect(() => {
    const fetchAnalytics = async () => {
      try {
        const [tr, hz, cr] = await Promise.all([
          getAnalyticsTrends(timeRange === '24h' ? 1 : timeRange === '30d' ? 30 : 7),
          getHazardStats(),
          getCameraRiskStats(),
        ]);
        setTrends(tr);
        setHazards(hz);
        setCamRankings(cr);
      } catch (e) {
        console.error('Failed to load analytics:', e);
      }
    };
    fetchAnalytics();
  }, [timeRange]);

  const COLORS = ['#dc2626', '#d97706', '#2563eb', '#7d5700', '#059669'];

  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="font-headline-md text-xl font-bold text-on-surface mb-1">Safety Analytics & Intelligence</h1>
          <p className="font-label-mono text-xs text-on-surface-variant">
            Historical incident metrics, hazard distributions, and high-risk sector telemetry.
          </p>
        </div>
        <div className="flex gap-2">
          {(['24h', '7d', '30d'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setTimeRange(r)}
              className={`px-3 py-1.5 rounded-DEFAULT font-label-mono-bold text-xs ${
                timeRange === r
                  ? 'bg-primary text-white shadow-sm'
                  : 'bg-surface text-on-surface border border-outline-variant hover:bg-surface-container'
              }`}
            >
              {r.toUpperCase()}
            </button>
          ))}
        </div>
      </div>

      {/* Grid: Trends Chart & Hazard Pie */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-gutter">
        {/* Incident Trend Chart (8 cols) */}
        <div className="lg:col-span-8 level-1-panel rounded-lg p-panel-padding flex flex-col gap-4">
          <div className="flex justify-between items-center">
            <h3 className="font-label-mono text-xs font-bold text-on-surface uppercase tracking-wider">
              Safety Incident Trends
            </h3>
            <span className="font-label-mono text-[11px] text-on-surface-variant">Daily Incident Volume</span>
          </div>

          <div className="h-64 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends.length > 0 ? trends : [
                { date: 'Mon', critical: 1, high: 2, medium: 4 },
                { date: 'Tue', critical: 0, high: 1, medium: 3 },
                { date: 'Wed', critical: 2, high: 3, medium: 5 },
                { date: 'Thu', critical: 1, high: 2, medium: 2 },
                { date: 'Fri', critical: 3, high: 4, medium: 6 },
                { date: 'Sat', critical: 0, high: 1, medium: 2 },
                { date: 'Sun', critical: 1, high: 2, medium: 3 },
              ]}>
                <defs>
                  <linearGradient id="critGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#dc2626" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#dc2626" stopOpacity={0} />
                  </linearGradient>
                  <linearGradient id="highGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#d97706" stopOpacity={0.4} />
                    <stop offset="95%" stopColor="#d97706" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" stroke="#74777f" fontSize={11} fontFamily="Geist Mono" />
                <YAxis stroke="#74777f" fontSize={11} fontFamily="Geist Mono" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#c4c6d0',
                    borderRadius: '4px',
                    fontFamily: 'Geist Mono',
                    fontSize: '11px',
                  }}
                />
                <Area type="monotone" dataKey="critical" stroke="#dc2626" fillOpacity={1} fill="url(#critGrad)" name="Critical" />
                <Area type="monotone" dataKey="high" stroke="#d97706" fillOpacity={1} fill="url(#highGrad)" name="High Risk" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hazard Breakdown (4 cols) */}
        <div className="lg:col-span-4 level-1-panel rounded-lg p-panel-padding flex flex-col gap-4">
          <h3 className="font-label-mono text-xs font-bold text-on-surface uppercase tracking-wider">
            Hazard Distribution
          </h3>
          <div className="h-64 w-full flex items-center justify-center">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={hazards.length > 0 ? hazards : [
                    { hazard_type: 'PPE Violation', count: 14 },
                    { hazard_type: 'Zone Breach', count: 9 },
                    { hazard_type: 'Proximity Hazard', count: 6 },
                    { hazard_type: 'Worker Fall', count: 2 },
                  ]}
                  dataKey="count"
                  nameKey="hazard_type"
                  cx="50%"
                  cy="50%"
                  innerRadius={45}
                  outerRadius={75}
                  paddingAngle={3}
                >
                  {(hazards.length > 0 ? hazards : [1, 2, 3, 4]).map((_, index) => (
                    <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#ffffff',
                    borderColor: '#c4c6d0',
                    borderRadius: '4px',
                    fontFamily: 'Geist Mono',
                    fontSize: '11px',
                  }}
                />
                <Legend
                  wrapperStyle={{
                    fontFamily: 'Geist Mono',
                    fontSize: '10px',
                  }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Camera Risk Index Table */}
      <div className="level-1-panel rounded-lg p-panel-padding flex flex-col gap-3">
        <h3 className="font-label-mono text-xs font-bold text-on-surface uppercase tracking-wider">
          Camera & Sector Risk Index Ranking
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-label-mono text-xs">
            <thead>
              <tr className="border-b border-outline-variant text-on-surface-variant bg-surface-container-low">
                <th className="py-2.5 px-3">CAMERA</th>
                <th className="py-2.5 px-3">SECTOR / ZONE</th>
                <th className="py-2.5 px-3">TOTAL INCIDENTS</th>
                <th className="py-2.5 px-3">AVG RISK SCORE</th>
                <th className="py-2.5 px-3">SEVERITY LEVEL</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/60">
              {[
                { id: 'CAM_03', name: 'Heavy Stamping & Press Bay', incidents: 18, risk: 78, level: 'CRITICAL' },
                { id: 'CAM_02', name: 'Robotic Welding Cell A', incidents: 11, risk: 52, level: 'HIGH' },
                { id: 'CAM_01', name: 'Sector A Main Corridor', incidents: 7, risk: 34, level: 'MEDIUM' },
                { id: 'CAM_04', name: 'Logistics Loading Dock 4', incidents: 3, risk: 18, level: 'LOW' },
              ].map((c) => (
                <tr key={c.id} className="hover:bg-surface-container-low transition-colors">
                  <td className="py-2.5 px-3 font-bold text-primary">{c.id}</td>
                  <td className="py-2.5 px-3 text-on-surface">{c.name}</td>
                  <td className="py-2.5 px-3 text-on-surface font-semibold">{c.incidents}</td>
                  <td className="py-2.5 px-3">
                    <span className={c.risk > 70 ? 'text-severity-critical font-bold' : c.risk > 40 ? 'text-severity-warning font-bold' : 'text-severity-safe font-bold'}>
                      {c.risk} / 100
                    </span>
                  </td>
                  <td className="py-2.5 px-3">
                    <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                      c.level === 'CRITICAL'
                        ? 'bg-error-container text-error border border-error/30'
                        : c.level === 'HIGH'
                        ? 'bg-severity-warning/10 text-severity-warning border border-severity-warning/30'
                        : 'bg-severity-safe/10 text-severity-safe border border-severity-safe/30'
                    }`}>
                      {c.level}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
