import React, { useState, useEffect } from 'react';
import { History, Search, Filter, Download, ArrowUpRight, CheckCircle2, ShieldAlert, AlertTriangle, User, RefreshCw } from 'lucide-react';
import { SafetyEvent } from '@/types';
import { getEvents } from '@/lib/api';

interface EventHistoryTableProps {
  onSelectEvent: (event: SafetyEvent) => void;
}

export const EventHistoryTable: React.FC<EventHistoryTableProps> = ({ onSelectEvent }) => {
  const [events, setEvents] = useState<SafetyEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [selectedSeverity, setSelectedSeverity] = useState<string>('');
  const [selectedStatus, setSelectedStatus] = useState<string>('');
  const [searchQuery, setSearchQuery] = useState('');
  const [page, setPage] = useState(0);
  const limit = 15;

  const fetchHistory = async () => {
    setLoading(true);
    try {
      const res = await getEvents({
        severity: selectedSeverity || undefined,
        status: selectedStatus || undefined,
        limit,
        offset: page * limit,
      });
      setEvents(res.events);
      setTotal(res.total);
    } catch (e) {
      console.error('Failed to load history:', e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [selectedSeverity, selectedStatus, page]);

  const filteredEvents = events.filter((ev) => {
    if (!searchQuery) return true;
    const q = searchQuery.toLowerCase();
    return (
      ev.id.toLowerCase().includes(q) ||
      ev.camera_id.toLowerCase().includes(q) ||
      ev.primary_hazard.toLowerCase().includes(q) ||
      ev.worker_id.toString().includes(q)
    );
  });

  const exportCSV = () => {
    if (events.length === 0) return;
    const headers = ['Event ID', 'Camera', 'Worker', 'Hazard', 'Risk Score', 'Severity', 'Status', 'Started At', 'Exposure (s)'];
    const rows = events.map((e) => [
      e.id,
      e.camera_id,
      e.worker_id,
      e.primary_hazard,
      e.risk_score,
      e.severity,
      e.status,
      e.started_at,
      e.exposure_seconds,
    ]);

    const csvContent = [headers.join(','), ...rows.map((r) => r.join(','))].join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.setAttribute('href', url);
    link.setAttribute('download', `one_eye_audit_log_${Date.now()}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div className="flex flex-col gap-4 p-1">
      {/* Header & Controls Bar */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-3 bg-industrial-900 p-4 rounded-xl border border-industrial-border">
        <div>
          <h2 className="text-base font-mono font-bold text-white flex items-center gap-2">
            <History className="w-5 h-5 text-cyan-400" />
            SAFETY INCIDENT AUDIT TRAIL & LOGS
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Immutable forensic history of all detected hazards, severity escalations, and operator actions
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchHistory}
            className="p-2 rounded-lg bg-industrial-950 hover:bg-industrial-800 border border-industrial-border text-slate-300 transition"
            title="Refresh logs"
          >
            <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          </button>

          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-2 rounded-lg bg-cyan-600/20 hover:bg-cyan-600/30 text-cyan-300 border border-cyan-500/40 text-xs font-mono font-semibold transition"
          >
            <Download className="w-3.5 h-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Filter Strip */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-industrial-900/60 p-3 rounded-lg border border-industrial-border text-xs font-mono">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <Search className="w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by Event ID, Worker #, Camera..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-industrial-950 px-3 py-1.5 rounded border border-industrial-border text-slate-200 placeholder-slate-600 focus:outline-none focus:border-cyan-500"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-industrial-950 px-2.5 py-1.5 rounded border border-industrial-border text-slate-200 focus:outline-none"
            >
              <option value="">ALL SEVERITIES</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="ADVISORY">ADVISORY</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-slate-400">Status:</span>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-industrial-950 px-2.5 py-1.5 rounded border border-industrial-border text-slate-200 focus:outline-none"
            >
              <option value="">ALL STATUSES</option>
              <option value="ALERTING">ALERTING</option>
              <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
              <option value="RESOLVED">RESOLVED</option>
              <option value="FALSE_POSITIVE">FALSE POSITIVE</option>
            </select>
          </div>
        </div>
      </div>

      {/* Table */}
      <div className="bg-industrial-900 rounded-xl border border-industrial-border overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs font-mono">
            <thead>
              <tr className="border-b border-industrial-border bg-industrial-850 text-slate-400">
                <th className="py-3 px-4">EVENT ID</th>
                <th className="py-3 px-4">TIMESTAMP</th>
                <th className="py-3 px-4">CAMERA</th>
                <th className="py-3 px-4">TARGET</th>
                <th className="py-3 px-4">PRIMARY HAZARD</th>
                <th className="py-3 px-4">RISK SCORE</th>
                <th className="py-3 px-4">SEVERITY</th>
                <th className="py-3 px-4">STATUS</th>
                <th className="py-3 px-4 text-right">EVIDENCE</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-industrial-border/60">
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-slate-500">
                    No safety incidents found matching query.
                  </td>
                </tr>
              ) : (
                filteredEvents.map((event) => {
                  const isCrit = event.severity === 'CRITICAL';
                  const isHi = event.severity === 'HIGH';

                  return (
                    <tr
                      key={event.id}
                      onClick={() => onSelectEvent(event)}
                      className="hover:bg-industrial-850 cursor-pointer transition"
                    >
                      <td className="py-3 px-4 font-bold text-cyan-300">{event.id}</td>
                      <td className="py-3 px-4 text-slate-300">
                        {new Date(event.started_at).toLocaleString()}
                      </td>
                      <td className="py-3 px-4 text-slate-200">{event.camera_id}</td>
                      <td className="py-3 px-4 text-slate-200 font-semibold">
                        Worker #{event.worker_id.toString().padStart(2, '0')}
                      </td>
                      <td className="py-3 px-4 text-white font-medium">
                        {event.primary_hazard.replace(/_/g, ' ')}
                      </td>
                      <td className="py-3 px-4">
                        <span className={`font-bold ${isCrit ? 'text-hazard-critical' : isHi ? 'text-hazard-high' : 'text-amber-400'}`}>
                          {event.risk_score} / 100
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          isCrit
                            ? 'bg-hazard-critical/20 text-hazard-critical border border-hazard-critical/40'
                            : isHi
                            ? 'bg-hazard-high/20 text-hazard-high border border-hazard-high/40'
                            : 'bg-amber-500/20 text-amber-300 border border-amber-500/40'
                        }`}>
                          {event.severity}
                        </span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`px-2 py-0.5 rounded text-[10px] ${
                          event.status === 'RESOLVED'
                            ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40'
                            : event.status === 'ACKNOWLEDGED'
                            ? 'bg-blue-500/20 text-blue-300 border border-blue-500/40'
                            : 'bg-hazard-critical/20 text-hazard-critical border border-hazard-critical/40 animate-pulse font-bold'
                        }`}>
                          {event.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectEvent(event);
                          }}
                          className="p-1 rounded hover:bg-industrial-700 text-cyan-400 transition"
                          title="View forensic evidence"
                        >
                          <ArrowUpRight className="w-4 h-4" />
                        </button>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination Bar */}
        <div className="flex items-center justify-between px-4 py-3 border-t border-industrial-border bg-industrial-850 text-xs font-mono text-slate-400">
          <span>
            Showing {filteredEvents.length} of {total} events
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-3 py-1 rounded bg-industrial-950 border border-industrial-border disabled:opacity-40 hover:bg-industrial-800"
            >
              Previous
            </button>
            <span>Page {page + 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= total}
              className="px-3 py-1 rounded bg-industrial-950 border border-industrial-border disabled:opacity-40 hover:bg-industrial-800"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
