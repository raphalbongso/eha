/** Hook for WebSocket connection to receive real-time alerts. */

import { useCallback, useEffect, useRef } from 'react';

import { API_BASE_URL } from '../utils/constants';
import { getAccessToken } from '../services/storage';

interface UseWebSocketOptions {
  onNewAlert?: (payload: Record<string, unknown>) => void;
}

export function useWebSocket({ onNewAlert }: UseWebSocketOptions = {}) {
  const wsRef = useRef<WebSocket | null>(null);
  const pingIntervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const connect = useCallback(async () => {
    const token = await getAccessToken();
    if (!token) return;

    // Derive WS URL from API base URL
    const base = API_BASE_URL.replace(/\/api\/v1$/, '').replace(/^http/, 'ws');
    const url = `${base}/ws/alerts?token=${token}`;

    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      // Start 30s ping heartbeat
      pingIntervalRef.current = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ type: 'ping' }));
        }
      }, 30_000);
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'pong') return;
        if (data.type === 'new_alert' && onNewAlert) {
          onNewAlert(data);
        }
      } catch {
        // Ignore malformed messages
      }
    };

    ws.onclose = () => {
      cleanup();
      // Auto-reconnect after 5 seconds
      reconnectTimeoutRef.current = setTimeout(connect, 5_000);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [onNewAlert]);

  const cleanup = useCallback(() => {
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  useEffect(() => {
    connect();

    return () => {
      cleanup();
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, [connect, cleanup]);
}
