import React, { useState, useEffect } from 'react';
import { SafetyEvent } from '@/types';
import { getEvents } from '@/lib/api';

interface EventsAuditTabProps {
  onSelectEvent: (event: SafetyEvent) => void;
}

export const EventsAuditTab: React.FC<EventsAuditTabProps> = ({ onSelectEvent }) => {
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
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="font-headline-md text-xl font-bold text-on-surface mb-1">
            Safety Incident Audit Trail &amp; Logs
          </h1>
          <p className="font-label-mono text-xs text-on-surface-variant">
            Immutable forensic history of all detected hazards, severity escalations, and operator actions.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={fetchHistory}
            className="p-2 rounded-DEFAULT bg-surface hover:bg-surface-container border border-outline-variant text-on-surface transition"
            title="Refresh logs"
          >
            <span className={`material-symbols-outlined text-sm ${loading ? 'animate-spin' : ''}`}>
              refresh
            </span>
          </button>

          <button
            onClick={exportCSV}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-DEFAULT bg-primary text-white font-label-mono-bold text-xs shadow-sm hover:bg-primary/90 transition"
          >
            <span className="material-symbols-outlined text-sm">download</span>
            Export CSV
          </button>
        </div>
      </div>

      {/* Filter Strip */}
      <div className="level-1-panel rounded-lg p-3 flex flex-wrap items-center justify-between gap-3 font-label-mono text-xs">
        <div className="flex items-center gap-2 flex-1 max-w-sm">
          <span className="material-symbols-outlined text-on-surface-variant text-sm">search</span>
          <input
            type="text"
            placeholder="Search by Event ID, Worker #, Camera..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-surface-container-low px-3 py-1 rounded border border-outline-variant text-on-surface placeholder-on-surface-variant focus:outline-none focus:border-primary"
          />
        </div>

        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            <span className="text-on-surface-variant">Severity:</span>
            <select
              value={selectedSeverity}
              onChange={(e) => setSelectedSeverity(e.target.value)}
              className="bg-surface px-2.5 py-1 rounded border border-outline-variant text-on-surface focus:outline-none"
            >
              <option value="">ALL SEVERITIES</option>
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM">MEDIUM</option>
              <option value="ADVISORY">ADVISORY</option>
            </select>
          </div>

          <div className="flex items-center gap-1.5">
            <span className="text-on-surface-variant">Status:</span>
            <select
              value={selectedStatus}
              onChange={(e) => setSelectedStatus(e.target.value)}
              className="bg-surface px-2.5 py-1 rounded border border-outline-variant text-on-surface focus:outline-none"
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
      <div className="level-1-panel rounded-lg overflow-hidden flex flex-col">
        <div className="overflow-x-auto">
          <table className="w-full text-left font-label-mono text-xs">
            <thead>
              <tr className="border-b border-outline-variant bg-surface-container-low text-on-surface-variant">
                <th className="py-3 px-3">EVENT ID</th>
                <th className="py-3 px-3">TIMESTAMP</th>
                <th className="py-3 px-3">CAMERA</th>
                <th className="py-3 px-3">TARGET</th>
                <th className="py-3 px-3">PRIMARY HAZARD</th>
                <th className="py-3 px-3">RISK SCORE</th>
                <th className="py-3 px-3">SEVERITY</th>
                <th className="py-3 px-3">STATUS</th>
                <th className="py-3 px-3 text-right">ACTION</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-outline-variant/60">
              {filteredEvents.length === 0 ? (
                <tr>
                  <td colSpan={9} className="py-8 text-center text-on-surface-variant">
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
                      className="hover:bg-surface-container-low cursor-pointer transition-colors"
                    >
                      <td className="py-2.5 px-3 font-bold text-primary">{event.id}</td>
                      <td className="py-2.5 px-3 text-on-surface-variant">
                        {new Date(event.started_at).toLocaleString()}
                      </td>
                      <td className="py-2.5 px-3 text-on-surface">{event.camera_id}</td>
                      <td className="py-2.5 px-3 text-on-surface font-semibold">
                        Worker #{event.worker_id.toString().padStart(2, '0')}
                      </td>
                      <td className="py-2.5 px-3 text-on-surface font-medium">
                        {event.primary_hazard.replace(/_/g, ' ')}
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`font-bold ${isCrit ? 'text-severity-critical' : isHi ? 'text-severity-warning' : 'text-primary'}`}>
                          {event.risk_score} / 100
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          isCrit
                            ? 'bg-error-container text-error border border-error/30'
                            : isHi
                            ? 'bg-severity-warning/10 text-severity-warning border border-severity-warning/30'
                            : 'bg-primary/10 text-primary border border-primary/30'
                        }`}>
                          {event.severity}
                        </span>
                      </td>
                      <td className="py-2.5 px-3">
                        <span className={`px-2 py-0.5 rounded text-[10px] font-bold ${
                          event.status === 'RESOLVED'
                            ? 'bg-severity-safe/10 text-severity-safe border border-severity-safe/30'
                            : event.status === 'ACKNOWLEDGED'
                            ? 'bg-primary-container text-on-primary-container'
                            : 'bg-error-container text-error animate-pulse'
                        }`}>
                          {event.status}
                        </span>
                      </td>
                      <td className="py-2.5 px-3 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectEvent(event);
                          }}
                          className="p-1 rounded hover:bg-surface-variant text-primary transition"
                          title="View forensic evidence"
                        >
                          <span className="material-symbols-outlined text-sm">open_in_new</span>
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
        <div className="flex items-center justify-between px-3 py-2.5 border-t border-outline-variant bg-surface-container-low font-label-mono text-xs text-on-surface-variant">
          <span>
            Showing {filteredEvents.length} of {total} events
          </span>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0}
              className="px-2.5 py-1 rounded bg-surface border border-outline-variant disabled:opacity-40 hover:bg-surface-container"
            >
              Previous
            </button>
            <span>Page {page + 1}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={(page + 1) * limit >= total}
              className="px-2.5 py-1 rounded bg-surface border border-outline-variant disabled:opacity-40 hover:bg-surface-container"
            >
              Next
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
