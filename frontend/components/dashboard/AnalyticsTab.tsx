import React, { useState, useEffect } from 'react';
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, CartesianGrid
} from 'recharts';
import { getAnalyticsTrends, getHazardStats, getCameraRiskStats, getCameras } from '@/lib/api';
import { HazardStat, CameraRiskStat, Camera } from '@/types';
import { ShieldAlert, TrendingUp, BarChart2, Camera as CameraIcon, Activity, CheckCircle2 } from 'lucide-react';

export const AnalyticsTab: React.FC = () => {
  const [trends, setTrends] = useState<any[]>([]);
  const [hazards, setHazards] = useState<HazardStat[]>([]);
  const [camRankings, setCamRankings] = useState<CameraRiskStat[]>([]);
  const [cameras, setCameras] = useState<Camera[]>([]);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '24h'>('7d');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      setLoading(true);
      try {
        const [tr, hz, cr, cms] = await Promise.all([
          getAnalyticsTrends(timeRange === '24h' ? 1 : timeRange === '30d' ? 30 : 7),
          getHazardStats(),
          getCameraRiskStats(),
          getCameras(),
        ]);
        setTrends(tr);
        setHazards(hz);
        setCamRankings(cr);
        setCameras(cms);
      } catch (e) {
        console.error('Failed to load analytics:', e);
      } finally {
        setLoading(false);
      }
    };
    fetchAnalytics();
  }, [timeRange]);

  const COLORS = ['#dc2626', '#d97706', '#2563eb', '#7d5700', '#059669', '#9333ea'];

  // Map camera metadata to rankings
  const activeCameraList = cameras.map((c) => {
    const match = camRankings.find((r) => r.camera_id === c.id);
    return {
      id: c.id,
      name: c.name || c.id,
      status: c.status,
      incidents: match?.total_events ?? 0,
      risk: match?.avg_risk ?? 0,
      critical: match?.critical_events ?? 0,
      level: match && match.avg_risk >= 70 ? 'CRITICAL' : match && match.avg_risk >= 40 ? 'HIGH' : 'NOMINAL'
    };
  });

  const hasTrendData = trends.some((t) => (t.total || 0) > 0);
  const hasHazardData = hazards.length > 0 && hazards.some((h) => h.count > 0);

  return (
    <div className="flex flex-col gap-6 p-1">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4 bg-surface-container-low p-4 rounded-lg border border-outline-variant">
        <div>
          <h1 className="font-headline-md text-lg font-bold text-on-surface mb-1 flex items-center gap-2">
            <Activity className="w-5 h-5 text-primary" />
            Live Safety Intelligence & Incident Telemetry
          </h1>
          <p className="font-label-mono text-xs text-on-surface-variant">
            Real-time hazard telemetry, multi-camera risk escalation, and compliance audit trail.
          </p>
        </div>
        <div className="flex gap-1.5 bg-surface-container p-1 rounded-DEFAULT border border-outline-variant">
          {(['24h', '7d', '30d'] as const).map((r) => (
            <button
              key={r}
              onClick={() => setTimeRange(r)}
              className={`px-3 py-1 rounded-DEFAULT font-label-mono-bold text-xs transition ${
                timeRange === r
                  ? 'bg-primary text-white shadow-sm font-bold'
                  : 'text-on-surface-variant hover:text-on-surface'
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
            <h3 className="font-label-mono text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-primary" />
              Safety Incident Trends ({timeRange.toUpperCase()})
            </h3>
            <span className="font-label-mono text-[11px] text-on-surface-variant">
              {hasTrendData ? 'Real-Time Volume' : 'Zero Incidents Recorded'}
            </span>
          </div>

          <div className="h-64 w-full flex items-center justify-center">
            {hasTrendData ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={trends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
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
                  <CartesianGrid strokeDasharray="3 3" stroke="#2b303c" />
                  <XAxis dataKey="date" stroke="#74777f" fontSize={11} fontFamily="monospace" />
                  <YAxis stroke="#74777f" fontSize={11} fontFamily="monospace" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1f2c',
                      borderColor: '#2b303c',
                      borderRadius: '6px',
                      fontFamily: 'monospace',
                      fontSize: '11px',
                      color: '#ffffff'
                    }}
                  />
                  <Area type="monotone" dataKey="critical" stroke="#dc2626" fillOpacity={1} fill="url(#critGrad)" name="Critical" />
                  <Area type="monotone" dataKey="high" stroke="#d97706" fillOpacity={1} fill="url(#highGrad)" name="High Risk" />
                  <Area type="monotone" dataKey="medium" stroke="#2563eb" fillOpacity={0.2} fill="#2563eb" name="Medium Risk" />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center text-center p-6">
                <CheckCircle2 className="w-8 h-8 text-severity-safe mb-2" />
                <p className="font-label-mono text-sm text-on-surface font-bold">ALL CLEAR — NO RECORDED INCIDENTS</p>
                <p className="font-label-mono text-xs text-on-surface-variant mt-1">
                  Zero safety violations or hazard breaches detected during this {timeRange.toUpperCase()} window.
                </p>
              </div>
            )}
          </div>
        </div>

        {/* Hazard Breakdown (4 cols) */}
        <div className="lg:col-span-4 level-1-panel rounded-lg p-panel-padding flex flex-col gap-4">
          <h3 className="font-label-mono text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-severity-warning" />
            Hazard Type Distribution
          </h3>
          <div className="h-64 w-full flex items-center justify-center">
            {hasHazardData ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={hazards}
                    dataKey="count"
                    nameKey="hazard"
                    cx="50%"
                    cy="50%"
                    innerRadius={45}
                    outerRadius={75}
                    paddingAngle={3}
                  >
                    {hazards.map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#1a1f2c',
                      borderColor: '#2b303c',
                      borderRadius: '6px',
                      fontFamily: 'monospace',
                      fontSize: '11px',
                      color: '#ffffff'
                    }}
                  />
                  <Legend wrapperStyle={{ fontFamily: 'monospace', fontSize: '10px' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex flex-col items-center justify-center text-center p-6">
                <ShieldAlert className="w-8 h-8 text-on-surface-variant mb-2" />
                <p className="font-label-mono text-xs text-on-surface-variant">
                  No active hazard categories currently flagged.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Camera Risk Index Table */}
      <div className="level-1-panel rounded-lg p-panel-padding flex flex-col gap-3">
        <h3 className="font-label-mono text-xs font-bold text-on-surface uppercase tracking-wider flex items-center gap-2">
          <CameraIcon className="w-4 h-4 text-primary" />
          Camera Safety Risk Index Ranking
        </h3>
        <div className="overflow-x-auto">
          <table className="w-full text-left font-label-mono text-xs">
            <thead>
              <tr className="border-b border-outline-variant text-on-surface-variant bg-surface-container-low">
                <th className="py-2.5 px-3">CAMERA ID</th>
                <th className="py-2.5 px-3">FEED NAME</th>
                <th className="py-2.5 px-3">TOTAL INCIDENTS</th>
                <th className="py-2.5 px-3">CRITICAL BREACHES</th>
                <th className="py-2.5 px-3">AVG RISK SCORE</th>
                <th className="py-2.5 px-3">OPERATIONAL STATUS</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/60">
              {activeCameraList.length > 0 ? (
                activeCameraList.map((c) => (
                  <tr key={c.id} className="hover:bg-surface-container-low transition-colors">
                    <td className="py-2.5 px-3 font-bold text-primary">{c.id}</td>
                    <td className="py-2.5 px-3 text-on-surface">{c.name}</td>
                    <td className="py-2.5 px-3 text-on-surface font-semibold">{c.incidents}</td>
                    <td className="py-2.5 px-3 text-severity-critical font-semibold">{c.critical}</td>
                    <td className="py-2.5 px-3">
                      <span className={c.risk >= 70 ? 'text-severity-critical font-bold' : c.risk >= 40 ? 'text-severity-warning font-bold' : 'text-severity-safe font-bold'}>
                        {Math.round(c.risk)} / 100
                      </span>
                    </td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        c.status === 'ONLINE'
                          ? 'bg-severity-safe/10 text-severity-safe border border-severity-safe/30'
                          : 'bg-on-surface-variant/10 text-on-surface-variant border border-on-surface-variant/30'
                      }`}>
                        {c.status}
                      </span>
                    </td>
                  </tr>
                ))
              ) : (
                <tr>
                  <td colSpan={6} className="py-6 text-center text-on-surface-variant font-label-mono text-xs">
                    No active cameras registered in the monitoring array.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
