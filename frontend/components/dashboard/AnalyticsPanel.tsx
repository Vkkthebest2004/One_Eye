import React, { useState, useEffect } from 'react';
import {
  AreaChart,
  Area,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
  Legend
} from 'recharts';
import { ShieldAlert, AlertTriangle, CheckCircle2, TrendingUp, BarChart2, Flame, HardHat, Camera, Activity } from 'lucide-react';
import { AnalyticsSummary, TrendData, HazardStat, CameraRiskStat } from '@/types';
import { getAnalyticsSummary, getAnalyticsTrends, getHazardStats, getCameraRiskStats } from '@/lib/api';

export const AnalyticsPanel: React.FC = () => {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [trends, setTrends] = useState<TrendData[]>([]);
  const [hazards, setHazards] = useState<HazardStat[]>([]);
  const [cameraRisks, setCameraRisks] = useState<CameraRiskStat[]>([]);
  const [days, setDays] = useState<number>(7);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      setLoading(true);
      try {
        const [sumRes, trendRes, hazRes, camRes] = await Promise.all([
          getAnalyticsSummary(),
          getAnalyticsTrends(days),
          getHazardStats(),
          getCameraRiskStats(),
        ]);
        setSummary(sumRes);
        setTrends(trendRes);
        setHazards(hazRes);
        setCameraRisks(camRes);
      } catch (e) {
        console.error('Error fetching analytics:', e);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, [days]);

  const COLORS = ['#ff334b', '#ff8a00', '#ffcc00', '#00e5a3', '#00b4d8', '#a855f7'];

  return (
    <div className="flex flex-col gap-5 p-1">
      {/* Top Header & Range Filters */}
      <div className="flex items-center justify-between bg-industrial-900 p-4 rounded-xl border border-industrial-border">
        <div>
          <h2 className="text-base font-mono font-bold text-white flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-cyan-400" />
            SAFETY INTELLIGENCE & AUDIT ANALYTICS
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time hazard telemetry, multi-camera risk escalation, and compliance metrics
          </p>
        </div>

        <div className="flex items-center gap-1.5 bg-industrial-950 p-1 rounded-lg border border-industrial-border text-xs font-mono">
          {[7, 14, 30].map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              className={`px-3 py-1.5 rounded transition ${
                days === d
                  ? 'bg-cyan-600/30 text-cyan-300 border border-cyan-500/50 font-bold'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {d} Days
            </button>
          ))}
        </div>
      </div>

      {/* KPI Metric Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3.5">
        <MetricCard
          label="TOTAL EVENTS"
          value={summary?.total_events ?? 0}
          subtext="Audited incidents"
          icon={<Activity className="w-4 h-4 text-cyan-400" />}
          color="cyan"
        />
        <MetricCard
          label="ACTIVE ALERTS"
          value={summary?.active_alerts ?? 0}
          subtext="Requiring dispatch"
          icon={<AlertTriangle className="w-4 h-4 text-amber-400" />}
          color="amber"
        />
        <MetricCard
          label="CRITICAL EVENTS"
          value={summary?.critical_events ?? 0}
          subtext="High danger score"
          icon={<ShieldAlert className="w-4 h-4 text-hazard-critical" />}
          color="red"
        />
        <MetricCard
          label="RESOLVED"
          value={summary?.resolved_events ?? 0}
          subtext="Operator cleared"
          icon={<CheckCircle2 className="w-4 h-4 text-emerald-400" />}
          color="emerald"
        />
        <MetricCard
          label="AVG RISK SCORE"
          value={summary?.avg_risk_score ?? 0}
          unit="/100"
          subtext="Weighted average"
          icon={<TrendingUp className="w-4 h-4 text-orange-400" />}
          color="orange"
        />
        <MetricCard
          label="ONLINE FEEDS"
          value={`${summary?.cameras_online ?? 0}/${summary?.cameras_total ?? 0}`}
          subtext="Active CV pipelines"
          icon={<Camera className="w-4 h-4 text-purple-400" />}
          color="purple"
        />
      </div>

      {/* Charts Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5">
        
        {/* Trend Chart (8 Cols) */}
        <div className="lg:col-span-8 flex flex-col bg-industrial-900 p-5 rounded-xl border border-industrial-border">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200 flex items-center gap-2">
              <BarChart2 className="w-4 h-4 text-cyan-400" />
              Hazard Incidents Trend ({days} Days)
            </h3>
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-hazard-critical">
                <span className="w-2.5 h-2.5 rounded-full bg-hazard-critical" /> Critical
              </span>
              <span className="flex items-center gap-1.5 text-hazard-high">
                <span className="w-2.5 h-2.5 rounded-full bg-hazard-high" /> High
              </span>
              <span className="flex items-center gap-1.5 text-amber-400">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Medium
              </span>
            </div>
          </div>

          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={trends} margin={{ top: 10, right: 10, left: -20, bottom: 0 }}>
                <defs>
                  <linearGradient id="colorCritical" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff334b" stopOpacity={0.4}/>
                    <stop offset="95%" stopColor="#ff334b" stopOpacity={0}/>
                  </linearGradient>
                  <linearGradient id="colorHigh" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#ff8a00" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#ff8a00" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#242d45" />
                <XAxis dataKey="date" stroke="#64748b" fontSize={11} fontFamily="monospace" />
                <YAxis stroke="#64748b" fontSize={11} fontFamily="monospace" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#0d111a',
                    border: '1px solid #242d45',
                    borderRadius: '8px',
                    fontFamily: 'monospace',
                    fontSize: '12px'
                  }}
                />
                <Area type="monotone" dataKey="critical" stroke="#ff334b" strokeWidth={2} fillOpacity={1} fill="url(#colorCritical)" />
                <Area type="monotone" dataKey="high" stroke="#ff8a00" strokeWidth={2} fillOpacity={1} fill="url(#colorHigh)" />
                <Area type="monotone" dataKey="medium" stroke="#ffcc00" strokeWidth={1.5} fillOpacity={0.1} fill="#ffcc00" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Hazard Breakdown (4 Cols) */}
        <div className="lg:col-span-4 flex flex-col bg-industrial-900 p-5 rounded-xl border border-industrial-border">
          <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200 mb-4 flex items-center gap-2">
            <ShieldAlert className="w-4 h-4 text-amber-400" />
            Hazard Type Distribution
          </h3>

          <div className="h-72 w-full flex items-center justify-center">
            {hazards.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={hazards}
                    dataKey="count"
                    nameKey="hazard"
                    cx="50%"
                    cy="50%"
                    innerRadius={55}
                    outerRadius={85}
                    paddingAngle={3}
                  >
                    {hazards.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      backgroundColor: '#0d111a',
                      border: '1px solid #242d45',
                      borderRadius: '8px',
                      fontFamily: 'monospace',
                      fontSize: '12px'
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
                </PieChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-xs font-mono text-slate-500">No hazard distribution data</p>
            )}
          </div>
        </div>

      </div>

      {/* Camera Ranking Table */}
      <div className="bg-industrial-900 p-5 rounded-xl border border-industrial-border">
        <h3 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200 mb-3 flex items-center gap-2">
          <Camera className="w-4 h-4 text-cyan-400" />
          Camera Safety Risk Index Ranking
        </h3>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-industrial-border text-slate-400">
                <th className="py-2.5 px-3">CAMERA ID</th>
                <th className="py-2.5 px-3">TOTAL INCIDENTS</th>
                <th className="py-2.5 px-3">CRITICAL BREACHES</th>
                <th className="py-2.5 px-3">AVG RISK SCORE</th>
                <th className="py-2.5 px-3">RISK SEVERITY</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-industrial-border/60">
              {cameraRisks.map((cam) => {
                const isHighRisk = cam.avg_risk >= 60;
                return (
                  <tr key={cam.camera_id} className="hover:bg-industrial-850 transition">
                    <td className="py-2.5 px-3 font-bold text-cyan-300">{cam.camera_id}</td>
                    <td className="py-2.5 px-3 text-slate-200">{cam.total_events}</td>
                    <td className="py-2.5 px-3 text-hazard-critical font-semibold">{cam.critical_events}</td>
                    <td className="py-2.5 px-3 text-slate-200">{cam.avg_risk} / 100</td>
                    <td className="py-2.5 px-3">
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                        isHighRisk ? 'bg-hazard-critical/20 text-hazard-critical border border-hazard-critical/40' : 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                      }`}>
                        {isHighRisk ? 'ELEVATED RISK' : 'NORMAL'}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

interface MetricCardProps {
  label: string;
  value: string | number;
  unit?: string;
  subtext: string;
  icon: React.ReactNode;
  color: 'cyan' | 'amber' | 'red' | 'emerald' | 'orange' | 'purple';
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  unit,
  subtext,
  icon,
  color,
}) => {
  return (
    <div className="flex flex-col justify-between p-3.5 rounded-xl bg-industrial-900 border border-industrial-border hover:border-slate-600 transition">
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono font-bold tracking-wider text-slate-400">{label}</span>
        {icon}
      </div>
      <div>
        <div className="text-xl font-mono font-bold text-white tracking-tight">
          {value} {unit && <span className="text-xs font-normal text-slate-400">{unit}</span>}
        </div>
        <p className="text-[10px] text-slate-500 mt-0.5">{subtext}</p>
      </div>
    </div>
  );
};
