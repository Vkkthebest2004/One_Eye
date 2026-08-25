import React from 'react';
import { Map, Camera, AlertTriangle, Shield, User, Compass, Zap, Flame } from 'lucide-react';
import { LiveTrack, SafetyEvent, Camera as CameraType, Zone, Machine } from '@/types';

interface SafetyMapProps {
  cameras: CameraType[];
  zones: Zone[];
  machines: Machine[];
  tracks: Record<string, LiveTrack[]>;
  alerts: SafetyEvent[];
}

export const SafetyMap: React.FC<SafetyMapProps> = ({
  cameras,
  zones,
  machines,
  tracks,
  alerts,
}) => {
  // Aggregate all active worker tracks across cameras
  const allTracks = Object.entries(tracks).flatMap(([camId, trkList]) =>
    trkList.map((t) => ({ ...t, cameraId: camId }))
  );

  return (
    <div className="flex flex-col gap-4 p-1">
      {/* Map Header & Legend */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 bg-industrial-900 p-4 rounded-xl border border-industrial-border">
        <div>
          <h2 className="text-base font-mono font-bold text-white flex items-center gap-2">
            <Map className="w-5 h-5 text-cyan-400" />
            2D INDUSTRIAL PLANT SAFETY MAP & DIGITAL TWIN
          </h2>
          <p className="text-xs text-slate-400 mt-0.5">
            Real-time spatial floorplan, camera FOV coverage cones, restricted zones, and personnel pings
          </p>
        </div>

        {/* Risk Legend */}
        <div className="flex items-center gap-3 bg-industrial-950 px-3 py-1.5 rounded-lg border border-industrial-border text-xs font-mono">
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400" />
            <span className="text-slate-300">Safe (0-29)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400" />
            <span className="text-slate-300">Medium (30-59)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-hazard-high" />
            <span className="text-slate-300">High (60-79)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2.5 h-2.5 rounded-full bg-hazard-critical animate-ping" />
            <span className="text-hazard-critical font-bold">Critical (80+)</span>
          </div>
        </div>
      </div>

      {/* Interactive 2D SVG Factory Layout */}
      <div className="relative w-full aspect-[16/9] min-h-[480px] bg-industrial-950 rounded-xl border border-industrial-border overflow-hidden shadow-2xl p-6 flex items-center justify-center">
        
        {/* Floor Grid Pattern */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#161d2e_1px,transparent_1px),linear-gradient(to_bottom,#161d2e_1px,transparent_1px)] bg-[size:32px_32px] opacity-60" />

        <svg className="absolute inset-0 w-full h-full" viewBox="0 0 1000 600">
          
          {/* PLANT STRUCTURE WALLS & BAYS */}
          {/* Main Perimeter */}
          <rect x="50" y="50" width="900" height="500" fill="none" stroke="#242d45" strokeWidth="4" />

          {/* Bay 1: Stamping & Press Bay (CAM_01) */}
          <rect x="70" y="70" width="410" height="230" fill="#0d111a" stroke="#2b3652" strokeWidth="2" rx="6" />
          <text x="85" y="95" fill="#64748b" fontFamily="monospace" fontSize="12" fontWeight="bold">BAY 1: STAMPING & PRESS (CAM_01)</text>

          {/* Bay 2: Robotic Welding Cell (CAM_02) */}
          <rect x="520" y="70" width="410" height="230" fill="#0d111a" stroke="#2b3652" strokeWidth="2" rx="6" />
          <text x="535" y="95" fill="#64748b" fontFamily="monospace" fontSize="12" fontWeight="bold">BAY 2: ROBOTIC WELDING (CAM_02)</text>

          {/* Bay 3: Chemical Storage (CAM_03) */}
          <rect x="70" y="320" width="410" height="210" fill="#0d111a" stroke="#2b3652" strokeWidth="2" rx="6" />
          <text x="85" y="345" fill="#64748b" fontFamily="monospace" fontSize="12" fontWeight="bold">BAY 3: CHEMICAL STORAGE (CAM_03)</text>

          {/* Bay 4: Logistics & Loading Dock (CAM_04) */}
          <rect x="520" y="320" width="410" height="210" fill="#0d111a" stroke="#2b3652" strokeWidth="2" rx="6" />
          <text x="535" y="345" fill="#64748b" fontFamily="monospace" fontSize="12" fontWeight="bold">BAY 4: LOGISTICS & DOCKS (CAM_04)</text>

          {/* RESTRICTED DANGER ZONES */}
          {/* Zone 1: Hydraulic Press Perimeter */}
          <polygon
            points="140,120 340,120 380,260 120,260"
            fill="rgba(255, 138, 0, 0.15)"
            stroke="#ff8a00"
            strokeWidth="2"
            strokeDasharray="6,4"
          />
          <text x="160" y="145" fill="#ff8a00" fontFamily="monospace" fontSize="10" fontWeight="bold">RESTRICTED ZONE (PRESS)</text>

          {/* Zone 2: Robotic Arc Hazard */}
          <polygon
            points="600,120 840,120 860,250 580,250"
            fill="rgba(255, 51, 75, 0.15)"
            stroke="#ff334b"
            strokeWidth="2"
            strokeDasharray="6,4"
          />
          <text x="630" y="145" fill="#ff334b" fontFamily="monospace" fontSize="10" fontWeight="bold">ARC FLASH PERIMETER</text>

          {/* MACHINERY */}
          {/* Machine 1: Hydraulic Press */}
          <rect x="200" y="150" width="120" height="80" fill="#1c2336" stroke="#00e5a3" strokeWidth="2" rx="4" />
          <text x="210" y="195" fill="#00e5a3" fontFamily="monospace" fontSize="10" fontWeight="bold">HYDRAULIC PRESS</text>

          {/* Machine 2: Robotic Arm */}
          <rect x="680" y="150" width="100" height="70" fill="#1c2336" stroke="#00e5a3" strokeWidth="2" rx="4" />
          <text x="695" y="190" fill="#00e5a3" fontFamily="monospace" fontSize="10" fontWeight="bold">KUKA ARM</text>

          {/* CAMERA COVERAGE CONES & ICONS */}
          {/* CAM_01 */}
          <polygon points="75,75 220,260 380,260" fill="rgba(6, 182, 212, 0.08)" stroke="rgba(6, 182, 212, 0.3)" strokeWidth="1" />
          <circle cx="75" cy="75" r="10" fill="#06b6d4" />
          <text x="90" y="78" fill="#06b6d4" fontFamily="monospace" fontSize="10" fontWeight="bold">CAM_01</text>

          {/* CAM_02 */}
          <polygon points="525,75 660,260 840,260" fill="rgba(6, 182, 212, 0.08)" stroke="rgba(6, 182, 212, 0.3)" strokeWidth="1" />
          <circle cx="525" cy="75" r="10" fill="#06b6d4" />
          <text x="540" y="78" fill="#06b6d4" fontFamily="monospace" fontSize="10" fontWeight="bold">CAM_02</text>

          {/* CAM_03 */}
          <polygon points="75,325 220,500 380,500" fill="rgba(6, 182, 212, 0.08)" stroke="rgba(6, 182, 212, 0.3)" strokeWidth="1" />
          <circle cx="75" cy="325" r="10" fill="#06b6d4" />
          <text x="90" y="328" fill="#06b6d4" fontFamily="monospace" fontSize="10" fontWeight="bold">CAM_03</text>

          {/* CAM_04 */}
          <polygon points="525,325 660,500 840,500" fill="rgba(6, 182, 212, 0.08)" stroke="rgba(6, 182, 212, 0.3)" strokeWidth="1" />
          <circle cx="525" cy="325" r="10" fill="#06b6d4" />
          <text x="540" y="328" fill="#06b6d4" fontFamily="monospace" fontSize="10" fontWeight="bold">CAM_04</text>

          {/* ACTIVE WORKER POSITIONS PINGS */}
          {/* Worker 07 (Simulated Position near Press in Bay 1) */}
          <g transform="translate(240, 210)">
            <circle cx="0" cy="0" r="14" fill="rgba(255, 51, 75, 0.3)" className="animate-ping" />
            <circle cx="0" cy="0" r="8" fill="#ff334b" />
            <text x="12" y="4" fill="#ffffff" fontFamily="monospace" fontSize="10" fontWeight="bold">Worker #07 (CRITICAL)</text>
          </g>

          {/* Worker 03 (Safe Position in Bay 2) */}
          <g transform="translate(730, 220)">
            <circle cx="0" cy="0" r="6" fill="#00e5a3" />
            <text x="10" y="4" fill="#00e5a3" fontFamily="monospace" fontSize="10" fontWeight="bold">Worker #03 (NOMINAL)</text>
          </g>

          {/* Worker 05 (Moderate in Bay 3) */}
          <g transform="translate(260, 420)">
            <circle cx="0" cy="0" r="6" fill="#ff8a00" />
            <text x="10" y="4" fill="#ff8a00" fontFamily="monospace" fontSize="10" fontWeight="bold">Worker #05 (HIGH)</text>
          </g>
        </svg>

        {/* Overlay Plant Status HUD */}
        <div className="absolute bottom-4 left-4 bg-industrial-900/90 backdrop-blur px-3 py-2 rounded-lg border border-industrial-border text-xs font-mono text-slate-300">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <span>FACILITY STATUS: <strong>4 BAYS MONITORED</strong></span>
          </div>
          <p className="text-[10px] text-slate-500 mt-0.5">Floorplan scale: 1px = 0.08m • 3 Active Workers</p>
        </div>
      </div>
    </div>
  );
};
