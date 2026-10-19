'use client';

import React, { useState, useEffect } from 'react';
import {
  analyzeRetrospective,
  getCameraTimeline,
  getMediaUrl,
  RetrospectiveReport,
  TimelineEvent,
  CameraTimelineData
} from '@/lib/api';

interface RetrospectiveModalProps {
  cameraId: string;
  cameraName?: string;
  isOpen: boolean;
  onClose: () => void;
}

export const RetrospectiveModal: React.FC<RetrospectiveModalProps> = ({
  cameraId,
  cameraName = 'Live Camera',
  isOpen,
  onClose,
}) => {
  const [selectedDomain, setSelectedDomain] = useState<string>('INDUSTRIAL_SOP');
  const [customGoal, setCustomGoal] = useState<string>('');
  const [seconds, setSeconds] = useState<number>(60);
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [report, setReport] = useState<RetrospectiveReport | null>(null);
  const [timelineData, setTimelineData] = useState<CameraTimelineData | null>(null);
  const [selectedKeyframeUrl, setSelectedKeyframeUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Load preview timeline on open
  useEffect(() => {
    if (isOpen && cameraId) {
      setErrorMsg(null);
      getCameraTimeline(cameraId, seconds)
        .then((data) => setTimelineData(data))
        .catch(() => {});
    }
  }, [isOpen, cameraId, seconds]);

  if (!isOpen) return null;

  const handleRunAnalysis = async () => {
    setIsLoading(true);
    setErrorMsg(null);
    try {
      const res = await analyzeRetrospective(cameraId, selectedDomain, customGoal || undefined, seconds);
      setReport(res);
      if (res.keyframe_paths && res.keyframe_paths.length > 0) {
        setSelectedKeyframeUrl(res.keyframe_paths[0]);
      }
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to complete 60s sequence analysis. Ensure camera is online.');
    } finally {
      setIsLoading(false);
    }
  };

  const domainOptions = [
    {
      id: 'INDUSTRIAL_SOP',
      title: 'Industrial Safety & PPE SOP',
      desc: 'Mandatory PPE compliance (hard hat, vest, safety glasses), zone boundary clearance, and danger avoidance.',
      icon: 'verified_user',
    },
    {
      id: 'EQUIPMENT_OPERATION',
      title: 'Machine & Equipment Operation',
      desc: 'Approach, hopper inspection, loading sequence, unplanned machine stops/stalls, and restart safety.',
      icon: 'precision_manufacturing',
    },
    {
      id: 'SECURITY_PERIMETER',
      title: 'Restricted Perimeter & Security',
      desc: 'Unauthorized boundary entries, loitering exceeding 15s, tailgating, and unattended equipment.',
      icon: 'security',
    },
    {
      id: 'ERGONOMICS_SAFETY',
      title: 'Ergonomics, Falls & Deceleration',
      desc: 'Biomechanical posturing, sudden drop/collapse detection, slip/trip dynamics, and safe lifting paths.',
      icon: 'accessibility_new',
    },
    {
      id: 'CUSTOM',
      title: 'Custom Operational Goal',
      desc: 'Define custom prompt criteria to critique and evaluate specific workplace tasks.',
      icon: 'psychology',
    },
  ];

  const getSeverityStyle = (sev: string) => {
    switch (sev?.toUpperCase()) {
      case 'CRITICAL':
        return 'bg-red-500/20 text-red-400 border-red-500/50';
      case 'HIGH':
        return 'bg-orange-500/20 text-orange-400 border-orange-500/50';
      case 'MEDIUM':
        return 'bg-amber-500/20 text-amber-400 border-amber-500/50';
      case 'LOW':
        return 'bg-blue-500/20 text-blue-400 border-blue-500/50';
      default:
        return 'bg-emerald-500/20 text-emerald-400 border-emerald-500/50';
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 overflow-y-auto">
      <div className="bg-surface border border-outline-variant rounded-2xl w-full max-w-5xl shadow-2xl p-6 relative my-8 flex flex-col max-h-[92vh]">
        {/* Header */}
        <div className="flex justify-between items-center pb-4 mb-4 border-b border-outline-variant">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-primary/10 border border-primary/30 flex items-center justify-center text-primary">
              <span className="material-symbols-outlined text-2xl">history_toggle_off</span>
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h3 className="font-label-mono-bold text-base text-on-surface font-bold tracking-tight">
                  60-Second Sequence Video Retrospective
                </h3>
                <span className="px-2 py-0.5 rounded text-[10px] font-label-mono-bold font-bold bg-primary/20 text-primary border border-primary/30">
                  AI SEQUENCE CRITIC
                </span>
              </div>
              <p className="font-label-mono text-xs text-on-surface-variant">
                Reconstructs past sequence, diagnoses mistakes or stalls, and compares against operational SOPs •{' '}
                <span className="text-on-surface font-bold">{cameraName}</span> ({cameraId})
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface-variant hover:text-on-surface transition font-bold"
          >
            <span className="material-symbols-outlined text-lg">close</span>
          </button>
        </div>

        {/* Scrollable Content Body */}
        <div className="overflow-y-auto flex-1 pr-1 space-y-5">
          {/* Controls: Domain Selection */}
          <div className="bg-surface-container/50 border border-outline-variant rounded-xl p-4">
            <div className="flex justify-between items-center mb-3">
              <span className="font-label-mono-bold text-xs uppercase tracking-wider text-on-surface flex items-center gap-1.5 font-bold">
                <span className="material-symbols-outlined text-sm text-primary">rule</span>
                1. Select Evaluation Domain / Standard Operating Procedure (SOP)
              </span>
              <div className="flex items-center gap-2 text-xs font-label-mono">
                <span className="text-on-surface-variant">Lookback Window:</span>
                {[30, 60, 90].map((sec) => (
                  <button
                    key={sec}
                    onClick={() => setSeconds(sec)}
                    className={`px-2.5 py-0.5 rounded text-xs font-bold transition border ${
                      seconds === sec
                        ? 'bg-primary text-black border-primary'
                        : 'bg-surface border-outline-variant text-on-surface-variant hover:text-on-surface'
                    }`}
                  >
                    {sec}s
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
              {domainOptions.slice(0, 4).map((d) => (
                <div
                  key={d.id}
                  onClick={() => setSelectedDomain(d.id)}
                  className={`p-3 rounded-lg border cursor-pointer transition-all flex flex-col justify-between ${
                    selectedDomain === d.id
                      ? 'bg-primary/10 border-primary shadow-sm shadow-primary/20'
                      : 'bg-surface border-outline-variant hover:border-outline-variant/80 text-on-surface-variant'
                  }`}
                >
                  <div className="flex items-center gap-2 mb-1.5">
                    <span className={`material-symbols-outlined text-base ${selectedDomain === d.id ? 'text-primary' : 'text-on-surface-variant'}`}>
                      {d.icon}
                    </span>
                    <span className={`font-label-mono-bold text-xs font-bold ${selectedDomain === d.id ? 'text-on-surface' : 'text-on-surface-variant'}`}>
                      {d.title}
                    </span>
                  </div>
                  <p className="font-label-mono text-[11px] text-on-surface-variant leading-relaxed line-clamp-3">
                    {d.desc}
                  </p>
                </div>
              ))}
            </div>

            {/* Custom prompt accordion / option */}
            <div className="mt-3 pt-3 border-t border-outline-variant flex flex-col gap-2">
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="customGoalToggle"
                  checked={selectedDomain === 'CUSTOM'}
                  onChange={(e) => setSelectedDomain(e.target.checked ? 'CUSTOM' : 'INDUSTRIAL_SOP')}
                  className="rounded border-outline-variant text-primary focus:ring-0"
                />
                <label htmlFor="customGoalToggle" className="font-label-mono text-xs text-on-surface font-bold cursor-pointer">
                  Provide Specific Operational Goal / Custom Investigation Instructions
                </label>
              </div>
              {selectedDomain === 'CUSTOM' && (
                <input
                  type="text"
                  placeholder="e.g. Analyze how worker operated machine, identify if material jammed, and check if restart was safe"
                  value={customGoal}
                  onChange={(e) => setCustomGoal(e.target.value)}
                  className="w-full bg-surface border border-outline-variant rounded-lg px-3 py-2 text-xs font-label-mono text-on-surface placeholder:text-on-surface-variant/50 focus:border-primary outline-none"
                />
              )}
            </div>

            {/* Action Bar */}
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3 pt-3 border-t border-outline-variant">
              <div className="flex items-center gap-2 font-label-mono text-xs text-on-surface-variant">
                <span className="w-2 h-2 rounded-full bg-emerald-500 animate-ping" />
                <span>
                  Rolling Ring Buffer:{' '}
                  <strong className="text-emerald-400">
                    {timelineData ? `${timelineData.buffered_seconds}s cached (${timelineData.total_snapshots} frames)` : 'Active'}
                  </strong>
                </span>
              </div>
              <button
                onClick={handleRunAnalysis}
                disabled={isLoading}
                className="px-5 py-2.5 bg-gradient-to-r from-primary to-emerald-400 text-black font-label-mono-bold text-xs font-bold rounded-lg shadow-lg hover:shadow-primary/30 transition-all flex items-center gap-2 active:scale-95 disabled:opacity-50"
              >
                <span className={`material-symbols-outlined text-base ${isLoading ? 'animate-spin' : ''}`}>
                  {isLoading ? 'progress_activity' : 'psychology'}
                </span>
                {isLoading ? 'ANALYZING 60-SECOND SEQUENCE...' : 'ANALYZE PREVIOUS 60 SECONDS'}
              </button>
            </div>
          </div>

          {errorMsg && (
            <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-xl text-red-400 text-xs font-label-mono flex items-center gap-2">
              <span className="material-symbols-outlined text-base">error</span>
              {errorMsg}
            </div>
          )}

          {/* Report Results */}
          {report && (
            <div className="space-y-4 animate-in fade-in duration-300">
              {/* Report Header Cards */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 font-label-mono">
                <div className="bg-surface-container/60 border border-outline-variant p-3 rounded-xl flex flex-col">
                  <span className="text-[10px] uppercase text-on-surface-variant font-bold">Severity Assessment</span>
                  <div className="mt-1 flex items-center gap-1.5">
                    <span className={`px-2 py-0.5 rounded text-xs font-bold border ${getSeverityStyle(report.severity)}`}>
                      {report.severity}
                    </span>
                  </div>
                </div>
                <div className="bg-surface-container/60 border border-outline-variant p-3 rounded-xl flex flex-col">
                  <span className="text-[10px] uppercase text-on-surface-variant font-bold">Sequence Window</span>
                  <span className="mt-1 text-sm font-bold text-on-surface">{report.analysis_duration_sec}s Elapsed</span>
                </div>
                <div className="bg-surface-container/60 border border-outline-variant p-3 rounded-xl flex flex-col">
                  <span className="text-[10px] uppercase text-on-surface-variant font-bold">Timeline Milestones</span>
                  <span className="mt-1 text-sm font-bold text-primary">{report.evidence_timeline?.length || 0} Events Detected</span>
                </div>
                <div className="bg-surface-container/60 border border-outline-variant p-3 rounded-xl flex flex-col">
                  <span className="text-[10px] uppercase text-on-surface-variant font-bold">Reasoning Engine</span>
                  <span className="mt-1 text-xs font-bold text-on-surface truncate" title={report.reasoning_engine}>
                    {report.reasoning_engine}
                  </span>
                </div>
              </div>

              {/* What Happened & What Went Wrong */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-surface-container/50 border border-outline-variant rounded-xl p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-label-mono-bold font-bold text-primary">
                    <span className="material-symbols-outlined text-base">timeline</span>
                    What Happened
                  </div>
                  <p className="font-label-mono text-xs text-on-surface leading-relaxed">
                    {report.what_happened}
                  </p>
                </div>

                <div className="bg-red-500/5 border border-red-500/30 rounded-xl p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-label-mono-bold font-bold text-red-400">
                    <span className="material-symbols-outlined text-base">warning</span>
                    What May Have Gone Wrong
                  </div>
                  <p className="font-label-mono text-xs text-red-300 leading-relaxed font-semibold">
                    {report.what_went_wrong}
                  </p>
                </div>
              </div>

              {/* Reconstructed Event Timeline */}
              <div className="bg-surface-container/50 border border-outline-variant rounded-xl p-4">
                <div className="flex justify-between items-center mb-3">
                  <span className="font-label-mono-bold text-xs uppercase tracking-wider text-on-surface flex items-center gap-1.5 font-bold">
                    <span className="material-symbols-outlined text-sm text-primary">format_list_numbered</span>
                    Reconstructed Event Timeline (Evidence to Investigate)
                  </span>
                  <span className="text-[10px] font-label-mono text-on-surface-variant">
                    Click an event to view associated keyframe
                  </span>
                </div>

                <div className="space-y-2">
                  {report.evidence_timeline && report.evidence_timeline.length > 0 ? (
                    report.evidence_timeline.map((evt, idx) => (
                      <div
                        key={idx}
                        onClick={() => evt.keyframe_url && setSelectedKeyframeUrl(evt.keyframe_url)}
                        className={`p-2.5 rounded-lg border font-label-mono text-xs flex items-center justify-between gap-3 cursor-pointer transition ${
                          selectedKeyframeUrl === evt.keyframe_url
                            ? 'bg-primary/10 border-primary text-on-surface'
                            : 'bg-surface border-outline-variant hover:border-outline-variant/80 text-on-surface-variant'
                        }`}
                      >
                        <div className="flex items-center gap-2.5">
                          <span className="px-2 py-0.5 rounded bg-surface-container-high text-primary font-bold text-[11px] border border-outline-variant">
                            {evt.timestamp_str}
                          </span>
                          <span className="font-bold text-on-surface">{evt.label}:</span>
                          <span className="text-on-surface-variant text-[11px]">{evt.description}</span>
                        </div>
                        <div className="flex items-center gap-2 shrink-0">
                          <span
                            className={`px-1.5 py-0.2 text-[9px] font-bold rounded uppercase ${
                              evt.risk_level === 'DANGER'
                                ? 'bg-red-500/20 text-red-400'
                                : evt.risk_level === 'WARNING'
                                ? 'bg-amber-500/20 text-amber-400'
                                : 'bg-emerald-500/20 text-emerald-400'
                            }`}
                          >
                            {evt.category}
                          </span>
                          {evt.keyframe_url && (
                            <span className="material-symbols-outlined text-xs text-primary">visibility</span>
                          )}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="text-center py-4 text-xs font-label-mono text-on-surface-variant">
                      No discrete state transitions detected during this minute.
                    </div>
                  )}
                </div>
              </div>

              {/* Possible Explanation & Recommended Next Steps */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="bg-surface-container/50 border border-outline-variant rounded-xl p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-label-mono-bold font-bold text-amber-400">
                    <span className="material-symbols-outlined text-base">lightbulb</span>
                    Possible Explanation
                  </div>
                  <p className="font-label-mono text-xs text-on-surface leading-relaxed">
                    {report.possible_explanation}
                  </p>
                </div>

                <div className="bg-surface-container/50 border border-outline-variant rounded-xl p-4 flex flex-col gap-2">
                  <div className="flex items-center gap-2 text-xs font-label-mono-bold font-bold text-emerald-400">
                    <span className="material-symbols-outlined text-base">task_alt</span>
                    Recommended Next Steps
                  </div>
                  <ul className="space-y-1.5 font-label-mono text-xs text-on-surface">
                    {report.recommended_next_steps?.map((step, sIdx) => (
                      <li key={sIdx} className="flex items-start gap-2">
                        <span className="material-symbols-outlined text-emerald-400 text-sm mt-0.5 shrink-0">
                          check_circle
                        </span>
                        <span>{step}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Keyframe Sequence Gallery */}
              {report.keyframe_paths && report.keyframe_paths.length > 0 && (
                <div className="bg-surface-container/50 border border-outline-variant rounded-xl p-4">
                  <div className="flex justify-between items-center mb-3">
                    <span className="font-label-mono-bold text-xs uppercase tracking-wider text-on-surface flex items-center gap-1.5 font-bold">
                      <span className="material-symbols-outlined text-sm text-primary">photo_library</span>
                      Sampled Keyframe Evidence ({report.keyframe_paths.length} frames)
                    </span>
                    {report.clip_path && (
                      <a
                        href={getMediaUrl(report.clip_path)}
                        download
                        className="px-2.5 py-1 bg-surface-container-high hover:bg-surface-container-highest text-primary text-xs font-bold rounded flex items-center gap-1 transition"
                      >
                        <span className="material-symbols-outlined text-sm">download</span>
                        Export 60s MP4 Clip
                      </a>
                    )}
                  </div>

                  <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2">
                    {report.keyframe_paths.map((kfUrl, kIdx) => (
                      <div
                        key={kIdx}
                        onClick={() => setSelectedKeyframeUrl(kfUrl)}
                        className={`rounded-lg overflow-hidden border cursor-pointer relative group aspect-video ${
                          selectedKeyframeUrl === kfUrl ? 'border-primary ring-2 ring-primary/40' : 'border-outline-variant'
                        }`}
                      >
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img src={getMediaUrl(kfUrl)} alt={`Keyframe ${kIdx}`} className="w-full h-full object-cover" />
                        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition flex items-center justify-center">
                          <span className="material-symbols-outlined text-white text-base">zoom_in</span>
                        </div>
                        <span className="absolute bottom-1 right-1 bg-black/80 text-[9px] font-label-mono text-white px-1 rounded">
                          Frame #{kIdx + 1}
                        </span>
                      </div>
                    ))}
                  </div>

                  {/* Selected Keyframe Expanded View */}
                  {selectedKeyframeUrl && (
                    <div className="mt-3 pt-3 border-t border-outline-variant flex flex-col items-center">
                      <div className="max-w-2xl w-full rounded-xl overflow-hidden border border-outline-variant bg-black">
                        {/* eslint-disable-next-line @next/next/no-img-element */}
                        <img
                          src={getMediaUrl(selectedKeyframeUrl)}
                          alt="Expanded Keyframe"
                          className="w-full max-h-[340px] object-contain mx-auto"
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Modal Footer */}
        <div className="pt-3 mt-3 border-t border-outline-variant flex justify-between items-center text-xs font-label-mono">
          <span className="text-on-surface-variant">
            ONE EYE Sequence Reconstruction Engine • Qwen3-VL / YOLOv8 Multi-Stage
          </span>
          <button
            onClick={onClose}
            className="px-4 py-1.5 rounded-lg bg-surface-container hover:bg-surface-container-high text-on-surface font-bold transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
