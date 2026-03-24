import { useEffect } from 'react';
import { useAlertStore, Alert } from '../stores/alertStore';
import { useAuthStore } from '../stores/authStore';
import { supabase } from '../services/supabase';
import * as Haptics from 'expo-haptics';

export function useAlerts() {
  const store = useAlertStore();
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    if (!user) return;

    // Subscribe to new alerts via Supabase Realtime
    const channel = supabase
      .channel('alerts-realtime')
      .on(
        'postgres_changes',
        {
          event: 'INSERT',
          schema: 'public',
          table: 'alerts',
          filter: `user_id=eq.${user.id}`,
        },
        (payload) => {
          const newAlert = payload.new as Alert;
          store.addAlert(newAlert);
          Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning);
        }
      )
      .subscribe();

    return () => {
      supabase.removeChannel(channel);
    };
  }, [user?.id]);

  return {
    alerts: store.alerts,
    unreadCount: store.unreadCount,
    isLoading: store.isLoading,
    fetchAlerts: store.fetchAlerts,
    markAsRead: store.markAsRead,
    markAllAsRead: store.markAllAsRead,
  };
}
