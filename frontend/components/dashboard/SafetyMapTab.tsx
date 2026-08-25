import React from 'react';
import { Camera, Zone, Machine, LiveTrack, SafetyEvent } from '@/types';

interface SafetyMapTabProps {
  cameras: Camera[];
  zones: Zone[];
  machines: Machine[];
  tracks: Record<string, LiveTrack[]>;
  alerts: SafetyEvent[];
}

export const SafetyMapTab: React.FC<SafetyMapTabProps> = ({
  cameras,
  zones,
  machines,
  tracks,
  alerts,
}) => {
  return (
    <div className="flex flex-col gap-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
        <div>
          <h1 className="font-headline-md text-xl font-bold text-on-surface mb-1">
            2D Plant Safety Map & Digital Twin
          </h1>
          <p className="font-label-mono text-xs text-on-surface-variant">
            Real-time spatial floorplan, camera FOV coverage cones, restricted zones, and personnel pings.
          </p>
        </div>

        {/* Legend */}
        <div className="flex items-center gap-3 bg-surface p-2 rounded-DEFAULT border border-outline-variant text-xs font-label-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-severity-safe" />
            <span className="text-on-surface">Safe</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-severity-warning" />
            <span className="text-on-surface">Warning</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-severity-critical animate-ping" />
            <span className="text-severity-critical font-bold">Critical</span>
          </div>
        </div>
      </div>

      {/* SVG Map Container */}
      <div className="level-1-panel rounded-lg overflow-hidden relative aspect-[16/9] min-h-[480px] flex items-center justify-center p-6 bg-surface-container-low">
        {/* Floor Grid Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#e1e2e8_1px,transparent_1px),linear-gradient(to_bottom,#e1e2e8_1px,transparent_1px)] bg-[size:32px_32px] opacity-80" />

        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1000 600">
          {/* Main Perimeter */}
          <rect x="50" y="50" width="900" height="500" fill="none" stroke="#c4c6d0" strokeWidth="4" />

          {/* Bay 1: Stamping & Press Bay (CAM_01) */}
          <rect x="70" y="70" width="410" height="230" fill="#ffffff" stroke="#c4c6d0" strokeWidth="2" rx="4" />
          <text x="85" y="95" fill="#74777f" fontFamily="Geist Mono" fontSize="11" fontWeight="bold">
            BAY 1: STAMPING &amp; PRESS (CAM_01)
          </text>

          {/* Bay 2: Robotic Welding Cell (CAM_02) */}
          <rect x="520" y="70" width="410" height="230" fill="#ffffff" stroke="#c4c6d0" strokeWidth="2" rx="4" />
          <text x="535" y="95" fill="#74777f" fontFamily="Geist Mono" fontSize="11" fontWeight="bold">
            BAY 2: ROBOTIC WELDING (CAM_02)
          </text>

          {/* Bay 3: Chemical Storage (CAM_03) */}
          <rect x="70" y="320" width="410" height="210" fill="#ffffff" stroke="#c4c6d0" strokeWidth="2" rx="4" />
          <text x="85" y="345" fill="#74777f" fontFamily="Geist Mono" fontSize="11" fontWeight="bold">
            BAY 3: CHEMICAL STORAGE (CAM_03)
          </text>

          {/* Bay 4: Logistics & Loading Dock (CAM_04) */}
          <rect x="520" y="320" width="410" height="210" fill="#ffffff" stroke="#c4c6d0" strokeWidth="2" rx="4" />
          <text x="535" y="345" fill="#74777f" fontFamily="Geist Mono" fontSize="11" fontWeight="bold">
            BAY 4: LOGISTICS &amp; DOCKS (CAM_04)
          </text>

          {/* RESTRICTED DANGER ZONES */}
          {/* Zone 1: Hydraulic Press Perimeter */}
          <polygon
            points="140,120 340,120 380,260 120,260"
            fill="rgba(217, 119, 6, 0.15)"
            stroke="#d97706"
            strokeWidth="2"
            strokeDasharray="6,4"
          />
          <text x="160" y="145" fill="#d97706" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">
            RESTRICTED ZONE (PRESS)
          </text>

          {/* Zone 2: Arc Flash Hazard */}
          <polygon
            points="600,120 840,120 860,250 580,250"
            fill="rgba(220, 38, 38, 0.15)"
            stroke="#dc2626"
            strokeWidth="2"
            strokeDasharray="6,4"
          />
          <text x="630" y="145" fill="#dc2626" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">
            ARC FLASH PERIMETER
          </text>

          {/* MACHINERY */}
          {/* Machine 1: Hydraulic Press */}
          <rect x="200" y="150" width="120" height="80" fill="#f2f4f6" stroke="#2563eb" strokeWidth="2" rx="4" />
          <text x="210" y="195" fill="#2563eb" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">
            HYDRAULIC PRESS
          </text>

          {/* Machine 2: Robotic Arm */}
          <rect x="680" y="150" width="100" height="70" fill="#f2f4f6" stroke="#2563eb" strokeWidth="2" rx="4" />
          <text x="695" y="190" fill="#2563eb" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">
            KUKA ARM
          </text>

          {/* CAMERA COVERAGE CONES & ICONS */}
          <polygon points="75,75 220,260 380,260" fill="rgba(37, 99, 235, 0.08)" stroke="rgba(37, 99, 235, 0.3)" strokeWidth="1" />
          <circle cx="75" cy="75" r="9" fill="#2563eb" />
          <text x="90" y="78" fill="#2563eb" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">CAM_01</text>

          <polygon points="525,75 660,260 840,260" fill="rgba(37, 99, 235, 0.08)" stroke="rgba(37, 99, 235, 0.3)" strokeWidth="1" />
          <circle cx="525" cy="75" r="9" fill="#2563eb" />
          <text x="540" y="78" fill="#2563eb" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">CAM_02</text>

          <polygon points="75,325 220,500 380,500" fill="rgba(37, 99, 235, 0.08)" stroke="rgba(37, 99, 235, 0.3)" strokeWidth="1" />
          <circle cx="75" cy="325" r="9" fill="#2563eb" />
          <text x="90" y="328" fill="#2563eb" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">CAM_03</text>

          <polygon points="525,325 660,500 840,500" fill="rgba(37, 99, 235, 0.08)" stroke="rgba(37, 99, 235, 0.3)" strokeWidth="1" />
          <circle cx="525" cy="325" r="9" fill="#2563eb" />
          <text x="540" y="328" fill="#2563eb" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">CAM_04</text>

          {/* ACTIVE WORKER POSITIONS */}
          {/* Worker 07 in Bay 1 (Critical) */}
          <g transform="translate(240, 210)">
            <circle cx="0" cy="0" r="14" fill="rgba(220, 38, 38, 0.25)" className="animate-ping" />
            <circle cx="0" cy="0" r="7" fill="#dc2626" />
            <text x="12" y="4" fill="#dc2626" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">
              Worker #07 (CRITICAL)
            </text>
          </g>

          {/* Worker 03 in Bay 2 (Nominal) */}
          <g transform="translate(730, 220)">
            <circle cx="0" cy="0" r="6" fill="#059669" />
            <text x="10" y="4" fill="#059669" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">
              Worker #03 (NOMINAL)
            </text>
          </g>

          {/* Worker 05 in Bay 3 (Moderate) */}
          <g transform="translate(260, 420)">
            <circle cx="0" cy="0" r="6" fill="#d97706" />
            <text x="10" y="4" fill="#d97706" fontFamily="Geist Mono" fontSize="10" fontWeight="bold">
              Worker #05 (WARNING)
            </text>
          </g>
        </svg>

        {/* HUD Info Box */}
        <div className="absolute bottom-4 left-4 bg-surface/90 backdrop-blur p-2.5 rounded-DEFAULT border border-outline-variant font-label-mono text-xs text-on-surface shadow-sm">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-severity-safe" />
            <span>FACILITY STATUS: <strong>4 BAYS MONITORED</strong></span>
          </div>
          <p className="text-[10px] text-on-surface-variant mt-0.5">Scale: 1px = 0.08m • 3 Active Workers</p>
        </div>
      </div>
    </div>
  );
};
