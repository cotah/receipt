import { create } from 'zustand';
import api from '../services/api';

export interface Alert {
  id: string;
  type: 'restock' | 'price_drop' | 'price_spike' | 'weekly_report';
  product_name: string | null;
  store_name: string | null;
  message: string;
  data: Record<string, any> | null;
  is_read: boolean;
  created_at: string;
}

interface AlertState {
  alerts: Alert[];
  unreadCount: number;
  isLoading: boolean;
  fetchAlerts: (unreadOnly?: boolean) => Promise<void>;
  markAsRead: (alertId: string) => Promise<void>;
  markAllAsRead: () => Promise<void>;
  addAlert: (alert: Alert) => void;
}

export const useAlertStore = create<AlertState>((set, get) => ({
  alerts: [],
  unreadCount: 0,
  isLoading: false,

  fetchAlerts: async (unreadOnly = false) => {
    set({ isLoading: true });
    try {
      const { data } = await api.get('/alerts', { params: { unread_only: unreadOnly } });
      set({ alerts: data.data, unreadCount: data.unread_count });
    } finally {
      set({ isLoading: false });
    }
  },

  markAsRead: async (alertId: string) => {
    await api.patch(`/alerts/${alertId}/read`);
    set({
      alerts: get().alerts.map((a) => (a.id === alertId ? { ...a, is_read: true } : a)),
      unreadCount: Math.max(0, get().unreadCount - 1),
    });
  },

  markAllAsRead: async () => {
    await api.patch('/alerts/read-all');
    set({
      alerts: get().alerts.map((a) => ({ ...a, is_read: true })),
      unreadCount: 0,
    });
  },

  addAlert: (alert: Alert) => {
    set({
      alerts: [alert, ...get().alerts],
      unreadCount: get().unreadCount + 1,
    });
  },
}));
