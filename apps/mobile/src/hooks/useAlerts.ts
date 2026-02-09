/** Hook for fetching and managing alerts. */

import { useCallback, useEffect, useState } from 'react';

import type { Alert } from '../types';
import api from '../services/api';

interface AlertsState {
  alerts: Alert[];
  isLoading: boolean;
  error: string | null;
  unreadCount: number;
}

export function useAlerts(unreadOnly: boolean = false) {
  const [state, setState] = useState<AlertsState>({
    alerts: [],
    isLoading: true,
    error: null,
    unreadCount: 0,
  });

  const fetchAlerts = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true, error: null }));
    try {
      const params = new URLSearchParams();
      if (unreadOnly) params.set('unread_only', 'true');

      const { data } = await api.get<Alert[]>(`/alerts?${params}`);
      const unreadCount = data.filter((a) => !a.read).length;

      setState({
        alerts: data,
        isLoading: false,
        error: null,
        unreadCount,
      });
    } catch (error) {
      setState((prev) => ({
        ...prev,
        isLoading: false,
        error: 'Failed to load alerts',
      }));
    }
  }, [unreadOnly]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  const markAsRead = useCallback(
    async (alertIds: string[]) => {
      try {
        await api.post('/alerts/mark-read', { alert_ids: alertIds });
        setState((prev) => ({
          ...prev,
          alerts: prev.alerts.map((a) =>
            alertIds.includes(a.id) ? { ...a, read: true } : a,
          ),
          unreadCount: prev.unreadCount - alertIds.length,
        }));
      } catch (error) {
        console.error('Failed to mark alerts as read:', error);
      }
    },
    [],
  );

  return {
    ...state,
    fetchAlerts,
    markAsRead,
  };
}
