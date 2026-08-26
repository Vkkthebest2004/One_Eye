import { useEffect, useRef, useState, useCallback } from 'react';
import { SafetyEvent, LiveDetection, LiveTrack } from '@/types';

interface WebSocketMessage {
  type: string;
  [key: string]: any;
}

export function useOneEyeWebSocket() {
  const [isConnected, setIsConnected] = useState(false);
  const [activeAlerts, setActiveAlerts] = useState<SafetyEvent[]>([]);
  const [cameraTracks, setCameraTracks] = useState<Record<string, LiveTrack[]>>({});
  const [cameraDetections, setCameraDetections] = useState<Record<string, LiveDetection[]>>({});
  const [cameraFps, setCameraFps] = useState<Record<string, number>>({});
  const [lastEvent, setLastEvent] = useState<SafetyEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current && (wsRef.current.readyState === WebSocket.OPEN || wsRef.current.readyState === WebSocket.CONNECTING)) {
      return;
    }

    let wsUrl = process.env.NEXT_PUBLIC_WS_URL;
    if (!wsUrl && typeof window !== 'undefined') {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const host = window.location.hostname || 'localhost';
      wsUrl = `${proto}//${host}:8001/ws`;
    }
    wsUrl = wsUrl || 'ws://localhost:8001/ws';
    
    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        console.log('[ONE EYE WS] Connected to safety event stream');
      };

      ws.onclose = () => {
        setIsConnected(false);
        if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
        reconnectTimeoutRef.current = setTimeout(connect, 4000);
      };

      ws.onerror = () => {
        try { ws.close(); } catch {}
      };

      ws.onmessage = (event) => {
        try {
          const msg: WebSocketMessage = JSON.parse(event.data);
          
          if (msg.type === 'SAFETY_EVENT') {
            const safetyEvt: SafetyEvent = {
              id: msg.event_id || `EVT-${Date.now()}`,
              camera_id: msg.camera_id || 'CAM_01',
              worker_id: msg.worker_id || 0,
              hazard_types: msg.hazard_types || msg.hazards || [msg.primary_hazard || 'HAZARD'],
              primary_hazard: msg.primary_hazard || 'SAFETY_VIOLATION',
              risk_score: msg.risk_score || 0,
              severity: msg.severity || 'MEDIUM',
              confidence: msg.confidence || 0.9,
              started_at: msg.timestamp || new Date().toISOString(),
              updated_at: msg.timestamp || new Date().toISOString(),
              status: msg.status || 'ALERTING',
              evidence_path: msg.evidence_path || msg.evidence_url,
              distance_m: msg.distance_m,
              exposure_seconds: msg.exposure_seconds || 0,
              description: msg.description,
              rule_triggered: msg.rule_triggered,
              recommended_action: msg.recommended_action,
              is_demo: true,
            };

            setLastEvent(safetyEvt);
            setActiveAlerts((prev) => {
              // Update if already in list, or add if new
              const existingIdx = prev.findIndex((e) => e.id === safetyEvt.id || (e.camera_id === safetyEvt.camera_id && e.worker_id === safetyEvt.worker_id));
              let updated = [...prev];
              if (existingIdx >= 0) {
                updated[existingIdx] = { ...updated[existingIdx], ...safetyEvt };
              } else {
                updated = [safetyEvt, ...updated];
              }
              // Sort by priority (Critical > High > Medium > Advisory)
              const priorityMap: Record<string, number> = { CRITICAL: 4, HIGH: 3, MEDIUM: 2, ADVISORY: 1 };
              return updated.sort((a, b) => (priorityMap[b.severity] || 0) - (priorityMap[a.severity] || 0));
            });
          } else if (msg.type === 'EVENT_UPDATED') {
            const { event_id, status } = msg;
            if (status === 'RESOLVED' || status === 'FALSE_POSITIVE') {
              setActiveAlerts((prev) => prev.filter((e) => e.id !== event_id));
            } else {
              setActiveAlerts((prev) =>
                prev.map((e) => (e.id === event_id ? { ...e, status, ...msg } : e))
              );
            }
          } else if (msg.type === 'DETECTION_UPDATE') {
            const camId = msg.camera_id;
            if (camId) {
              setCameraDetections((prev) => ({ ...prev, [camId]: msg.detections || [] }));
              setCameraTracks((prev) => ({ ...prev, [camId]: msg.tracks || [] }));
              if (msg.fps) {
                setCameraFps((prev) => ({ ...prev, [camId]: msg.fps }));
              }
            }
          } else if (msg.type === 'CAMERA_STATUS') {
            if (msg.camera_id && msg.fps !== undefined) {
              setCameraFps((prev) => ({ ...prev, [msg.camera_id]: msg.fps }));
            }
          }
        } catch (e) {
          console.error('Error parsing WS message:', e);
        }
      };
    } catch (e) {
      console.warn('WS connection failed:', e);
      reconnectTimeoutRef.current = setTimeout(connect, 3000);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      if (reconnectTimeoutRef.current) clearTimeout(reconnectTimeoutRef.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, [connect]);

  return {
    isConnected,
    activeAlerts,
    cameraTracks,
    cameraDetections,
    cameraFps,
    lastEvent,
    setActiveAlerts,
  };
}
