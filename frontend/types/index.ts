export type SeverityLevel = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'ADVISORY' | 'SAFE';

export type EventStatus = 'ALERTING' | 'ACKNOWLEDGED' | 'RESOLVED' | 'FALSE_POSITIVE';

export interface Camera {
  id: string;
  name: string;
  source: string;
  source_type: string;
  status: 'ONLINE' | 'OFFLINE' | 'ERROR';
  fps: number;
  resolution: string;
  is_calibrated: boolean;
  calibration_matrix?: number[][];
  calibration_points?: {
    image: number[][];
    world: number[][];
  };
  created_at: string;
}

export interface Zone {
  id: string;
  camera_id: string;
  name: string;
  polygon: number[][]; // [[x1, y1], [x2, y2], ...]
  severity: number;
  allowed_classes: string[];
  active: boolean;
  created_at: string;
}

export interface Machine {
  id: string;
  camera_id: string;
  name: string;
  geometry: number[]; // [x, y, w, h]
  danger_radius_m: number;
  active: boolean;
  created_at: string;
}

export interface SafetyEvent {
  id: string;
  camera_id: string;
  worker_id: number;
  hazard_types: string[];
  primary_hazard: string;
  risk_score: number;
  severity: SeverityLevel;
  confidence: number;
  started_at: string;
  updated_at: string;
  acknowledged_at?: string | null;
  resolved_at?: string | null;
  status: EventStatus;
  evidence_path?: string | null;
  distance_m?: number | null;
  exposure_seconds: number;
  description?: string | null;
  rule_triggered?: string | null;
  recommended_action?: string | null;
  is_demo: boolean;
}

export interface LiveDetection {
  class_id: number;
  class_name: string;
  confidence: number;
  bbox: number[]; // [x1, y1, x2, y2]
  center: number[];
  foot_anchor: number[];
  has_helmet?: boolean | null;
  has_vest?: boolean | null;
}

export interface LiveTrack {
  track_id: number;
  label: string;
  class_name: string;
  bbox: number[];
  foot_anchor: number[];
  velocity: number[];
  state: string;
  has_helmet?: boolean | null;
  has_vest?: boolean | null;
  current_zone_id?: string | null;
  closest_machine_id?: string | null;
  closest_machine_distance_m?: number | null;
  is_fallen: boolean;
  current_risk_score: number;
  trajectory: number[][];
}

export interface SystemHealth {
  status: string;
  system: string;
  version: string;
  database: string;
  cv_engine: string;
  model_device: string;
  active_ws_clients: number;
  demo_mode: boolean;
  cameras: Record<string, {
    status: string;
    fps: number;
    inference_ms: number;
    active_tracks: number;
  }>;
  total_active_tracks: number;
  timestamp: number;
}

export interface AnalyticsSummary {
  total_events: number;
  active_alerts: number;
  critical_events: number;
  high_risk_events: number;
  resolved_events: number;
  avg_risk_score: number;
  events_24h: number;
  cameras_total: number;
  cameras_online: number;
}

export interface TrendData {
  date: string;
  total: number;
  critical: number;
  high: number;
  medium: number;
  advisory: number;
}

export interface HazardStat {
  hazard: string;
  count: number;
}

export interface CameraRiskStat {
  camera_id: string;
  total_events: number;
  avg_risk: number;
  critical_events: number;
}
