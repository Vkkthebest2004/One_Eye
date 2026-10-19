import {
  Camera,
  Zone,
  Machine,
  SafetyEvent,
  SystemHealth,
  AnalyticsSummary,
  TrendData,
  HazardStat,
  CameraRiskStat
} from '@/types';

const getApiBase = () => {
  if (process.env.NEXT_PUBLIC_API_URL) return process.env.NEXT_PUBLIC_API_URL;
  if (typeof window !== 'undefined') {
    return `http://${window.location.hostname || 'localhost'}:8001`;
  }
  return 'http://localhost:8001';
};

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const base = getApiBase();
  const res = await fetch(`${base}${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  if (!res.ok) {
    const errorBody = await res.text();
    throw new Error(`API Error [${res.status}] ${path}: ${errorBody}`);
  }
  return res.json();
}

// HEALTH
export async function getHealth(): Promise<SystemHealth> {
  return fetchJson<SystemHealth>('/api/health');
}

// CAMERAS
export async function getCameras(): Promise<Camera[]> {
  return fetchJson<Camera[]>('/api/cameras');
}

export async function createCamera(data: Partial<Camera>): Promise<Camera> {
  return fetchJson<Camera>('/api/cameras', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteCamera(id: string): Promise<void> {
  await fetchJson<void>(`/api/cameras/${id}`, { method: 'DELETE' });
}

export async function useWebcam(cameraId: string = 'CAM_01'): Promise<any> {
  return fetchJson(`/api/cameras/use-webcam?camera_id=${cameraId}`, { method: 'POST' });
}

export async function useDemoVideo(cameraId: string = 'CAM_01'): Promise<any> {
  return fetchJson(`/api/cameras/use-demo-video?camera_id=${cameraId}`, { method: 'POST' });
}

export async function stopCameraFeed(cameraId: string): Promise<{ success: boolean; status: string; message: string }> {
  return fetchJson<{ success: boolean; status: string; message: string }>(`/api/cameras/${cameraId}/stop`, {
    method: 'POST',
  });
}

export async function startCameraFeed(cameraId: string): Promise<{ success: boolean; status: string; message: string }> {
  return fetchJson<{ success: boolean; status: string; message: string }>(`/api/cameras/${cameraId}/start`, {
    method: 'POST',
  });
}

export async function toggleCameraFeed(cameraId: string): Promise<{ success: boolean; status: string; message: string }> {
  return fetchJson<{ success: boolean; status: string; message: string }>(`/api/cameras/${cameraId}/toggle`, {
    method: 'POST',
  });
}

// ZONES
export async function getZones(cameraId?: string): Promise<Zone[]> {
  const query = cameraId ? `?camera_id=${cameraId}` : '';
  return fetchJson<Zone[]>(`/api/zones${query}`);
}

export async function createZone(data: Partial<Zone>): Promise<Zone> {
  return fetchJson<Zone>('/api/zones', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteZone(id: string): Promise<void> {
  await fetchJson<void>(`/api/zones/${id}`, { method: 'DELETE' });
}

export async function importZoneConfig(data: {
  config_json?: any;
  config_path?: string;
  camera_id?: string;
  zone_name?: string;
}): Promise<{ status: string; zone_id: string; zone_name: string; polygon_points: number }> {
  return fetchJson('/api/zones/import-config', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// MACHINES
export async function getMachines(cameraId?: string): Promise<Machine[]> {
  const query = cameraId ? `?camera_id=${cameraId}` : '';
  return fetchJson<Machine[]>(`/api/machines${query}`);
}

export async function createMachine(data: Partial<Machine>): Promise<Machine> {
  return fetchJson<Machine>('/api/machines', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteMachine(id: string): Promise<void> {
  await fetchJson<void>(`/api/machines/${id}`, { method: 'DELETE' });
}

// EVENTS
export async function getEvents(params?: {
  camera_id?: string;
  severity?: string;
  status?: string;
  hazard_type?: string;
  limit?: number;
  offset?: number;
}): Promise<{ total: number; limit: number; offset: number; events: SafetyEvent[] }> {
  const search = new URLSearchParams();
  if (params?.camera_id) search.set('camera_id', params.camera_id);
  if (params?.severity) search.set('severity', params.severity);
  if (params?.status) search.set('status', params.status);
  if (params?.hazard_type) search.set('hazard_type', params.hazard_type);
  if (params?.limit) search.set('limit', params.limit.toString());
  if (params?.offset) search.set('offset', params.offset.toString());
  
  const qs = search.toString() ? `?${search.toString()}` : '';
  return fetchJson<{ total: number; limit: number; offset: number; events: SafetyEvent[] }>(`/api/events${qs}`);
}

export async function getEventById(id: string): Promise<SafetyEvent> {
  return fetchJson<SafetyEvent>(`/api/events/${id}`);
}

export async function acknowledgeEvent(id: string, actor: string = 'OPERATOR_01'): Promise<SafetyEvent> {
  return fetchJson<SafetyEvent>(`/api/events/${id}/acknowledge`, {
    method: 'POST',
    body: JSON.stringify({ actor }),
  });
}

export async function resolveEvent(id: string, actor: string = 'OPERATOR_01'): Promise<SafetyEvent> {
  return fetchJson<SafetyEvent>(`/api/events/${id}/resolve`, {
    method: 'POST',
    body: JSON.stringify({ actor }),
  });
}

export async function markFalsePositive(id: string, notes: string = '', actor: string = 'OPERATOR_01'): Promise<SafetyEvent> {
  return fetchJson<SafetyEvent>(`/api/events/${id}/false-positive`, {
    method: 'POST',
    body: JSON.stringify({ actor, notes }),
  });
}

// ANALYTICS
export async function getAnalyticsSummary(): Promise<AnalyticsSummary> {
  return fetchJson<AnalyticsSummary>('/api/analytics/summary');
}

export async function getAnalyticsTrends(days: number = 7): Promise<TrendData[]> {
  return fetchJson<TrendData[]>(`/api/analytics/trends?days=${days}`);
}

export async function getHazardStats(): Promise<HazardStat[]> {
  return fetchJson<HazardStat[]>('/api/analytics/hazards');
}

export async function getCameraRiskStats(): Promise<CameraRiskStat[]> {
  return fetchJson<CameraRiskStat[]>('/api/analytics/camera-risk');
}

// CALIBRATION
export async function computeCalibration(cameraId: string, imagePoints: number[][], worldPoints: number[][]): Promise<any> {
  return fetchJson('/api/calibration/compute', {
    method: 'POST',
    body: JSON.stringify({
      camera_id: cameraId,
      image_points: imagePoints,
      world_points: worldPoints,
    }),
  });
}

// DEMO SCENARIOS
export async function triggerDemoScenario(scenario: string, cameraId: string = 'CAM_01', workerId: number = 7): Promise<any> {
  return fetchJson('/api/demo/trigger', {
    method: 'POST',
    body: JSON.stringify({
      scenario,
      camera_id: cameraId,
      worker_id: workerId,
    }),
  });
}

// MOBILE USB DEVICES
export interface MobileStatus {
  adb_available: boolean;
  scrcpy_available: boolean;
  platform: string;
  device_count: number;
  connected_count: number;
}

export interface MobileDevice {
  serial: string;
  model: string;
  manufacturer: string;
  os: string;
  os_version: string;
  connection_mode: string;
  is_connected: boolean;
  video_device_index: number | null;
  forwarded_port: number | null;
  error_message: string;
  last_heartbeat: number;
}

export interface MobileConnectResponse {
  success: boolean;
  serial: string;
  model: string;
  connection_mode: string;
  error_message: string;
}

export async function getMobileStatus(): Promise<MobileStatus> {
  return fetchJson<MobileStatus>('/api/mobile/status');
}

export async function scanMobileDevices(): Promise<MobileDevice[]> {
  return fetchJson<MobileDevice[]>('/api/mobile/scan', { method: 'POST' });
}

export async function getMobileDevices(): Promise<MobileDevice[]> {
  return fetchJson<MobileDevice[]>('/api/mobile/devices');
}

export async function connectMobileDevice(
  serial: string,
  mode: string = 'auto',
  cameraId?: string
): Promise<MobileConnectResponse> {
  return fetchJson<MobileConnectResponse>('/api/mobile/connect', {
    method: 'POST',
    body: JSON.stringify({ serial, mode, camera_id: cameraId }),
  });
}

export async function disconnectMobileDevice(serial: string): Promise<{ success: boolean }> {
  return fetchJson<{ success: boolean }>('/api/mobile/disconnect', {
    method: 'POST',
    body: JSON.stringify({ serial }),
  });
}

export async function getHostInfo(): Promise<{ local_ip: string; web_cam_url: string; api_url: string }> {
  return fetchJson<{ local_ip: string; web_cam_url: string; api_url: string }>('/api/mobile/host-info');
}

export async function launchCameraOnPhone(serial?: string): Promise<{ success: boolean; message: string }> {
  return fetchJson<{ success: boolean; message: string }>('/api/mobile/launch-camera', {
    method: 'POST',
    body: JSON.stringify({ serial }),
  });
}

export async function openBrowserCamOnPhone(serial?: string, url?: string): Promise<{ success: boolean; url: string }> {
  return fetchJson<{ success: boolean; url: string }>('/api/mobile/open-browser-cam', {
    method: 'POST',
    body: JSON.stringify({ serial, url }),
  });
}

export async function startDirectUsbStream(serial?: string): Promise<{ success: boolean; mode: string; url: string }> {
  return fetchJson<{ success: boolean; mode: string; url: string }>('/api/mobile/direct-usb-stream', {
    method: 'POST',
    body: JSON.stringify({ serial }),
  });
}

export async function connectRtspCamera(url: string, cameraId: string = 'CAM_MOB_24151JEG', name: string = 'Mobile RTSP Camera'): Promise<any> {
  return fetchJson<any>('/api/mobile/rtsp-connect', {
    method: 'POST',
    body: JSON.stringify({ url, camera_id: cameraId, name }),
  });
}

export function getMobileStreamUrl(serial: string, fps: number = 15): string {
  const base = getApiBase();
  return `${base}/api/mobile/stream/${serial}?fps=${fps}`;
}

export async function getSystemMode(): Promise<{ ai_enabled: boolean; mode: string; message: string }> {
  return fetchJson<{ ai_enabled: boolean; mode: string; message: string }>('/api/system/mode');
}

export async function toggleSystemAi(enabled?: boolean): Promise<{ ai_enabled: boolean; mode: string; message: string }> {
  return fetchJson<{ ai_enabled: boolean; mode: string; message: string }>('/api/system/toggle-ai', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  });
}

export async function getPerceptionMode(): Promise<{ perception_mode: string; mode_label: string; available_modes: string[]; is_default?: boolean }> {
  return fetchJson<{ perception_mode: string; mode_label: string; available_modes: string[]; is_default?: boolean }>('/api/system/perception-mode');
}

export async function setPerceptionMode(mode: 'YOLO' | 'QWEN_VL' | 'HYBRID', permanent: boolean = true): Promise<{ success: boolean; perception_mode: string; message: string; is_permanent?: boolean }> {
  return fetchJson<{ success: boolean; perception_mode: string; message: string; is_permanent?: boolean }>('/api/system/perception-mode', {
    method: 'POST',
    body: JSON.stringify({ mode, permanent }),
  });
}

export async function getDemoMode(): Promise<{ demo_mode: boolean; mode_label: string }> {
  return fetchJson<{ demo_mode: boolean; mode_label: string }>('/api/system/demo-mode');
}

export async function toggleDemoMode(enabled?: boolean): Promise<{ demo_mode: boolean; mode_label: string; message: string }> {
  return fetchJson<{ demo_mode: boolean; mode_label: string; message: string }>('/api/system/toggle-demo-mode', {
    method: 'POST',
    body: JSON.stringify({ enabled }),
  });
}

export function getMediaUrl(path?: string | null): string {
  if (!path) return '';
  if (path.startsWith('http')) return path;
  return `${getApiBase()}${path.startsWith('/') ? '' : '/'}${path}`;
}

// ---------------------------------------------------------------------------
// 60-Second Video Retrospective & Sequence Intelligence
// ---------------------------------------------------------------------------
export interface TimelineEvent {
  timestamp_sec: number;
  timestamp_str: string;
  label: string;
  description: string;
  category: 'ACTION' | 'PROCEDURE' | 'HAZARD' | 'STATUS';
  risk_level: 'SAFE' | 'WARNING' | 'DANGER';
  keyframe_index: number;
  keyframe_url?: string;
}

export interface RetrospectiveReport {
  id: string;
  camera_id: string;
  domain: string;
  custom_goal?: string | null;
  what_happened: string;
  what_went_wrong: string;
  evidence_timeline: TimelineEvent[];
  possible_explanation: string;
  recommended_next_steps: string[];
  keyframe_paths: string[];
  clip_path?: string | null;
  analysis_duration_sec: number;
  severity: 'SAFE' | 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL';
  reasoning_engine: string;
  created_at: string;
}

export interface CameraTimelineData {
  camera_id: string;
  buffered_seconds: number;
  total_snapshots: number;
  timeline: TimelineEvent[];
  max_risk_60s: number;
  active_hazards: string[];
}

export async function analyzeRetrospective(
  cameraId: string,
  domain: string = 'INDUSTRIAL_SOP',
  customGoal?: string,
  seconds: number = 60.0
): Promise<RetrospectiveReport> {
  return fetchJson<RetrospectiveReport>(`/api/retrospective/${cameraId}/analyze`, {
    method: 'POST',
    body: JSON.stringify({
      domain,
      custom_goal: customGoal || null,
      seconds,
    }),
  });
}

export async function getCameraTimeline(
  cameraId: string,
  seconds: number = 60.0
): Promise<CameraTimelineData> {
  return fetchJson<CameraTimelineData>(`/api/retrospective/${cameraId}/timeline?seconds=${seconds}`);
}

export async function listRetrospectiveReports(
  cameraId?: string,
  limit: number = 20
): Promise<{ total: number; reports: RetrospectiveReport[] }> {
  const query = new URLSearchParams();
  if (cameraId) query.set('camera_id', cameraId);
  query.set('limit', String(limit));
  return fetchJson<{ total: number; reports: RetrospectiveReport[] }>(`/api/retrospective/reports?${query.toString()}`);
}

export async function getRetrospectiveReport(reportId: string): Promise<RetrospectiveReport> {
  return fetchJson<RetrospectiveReport>(`/api/retrospective/reports/${reportId}`);
}

