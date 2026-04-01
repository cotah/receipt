import React, { useEffect } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import AlertCard from '../../components/alerts/AlertCard';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAlertStore } from '../../stores/alertStore';
import api from '../../services/api';

export default function AlertsScreen() {
  const router = useRouter();
  const { alerts, unreadCount, isLoading, fetchAlerts, markAsRead, markAllAsRead } = useAlertStore();

  useEffect(() => {
    fetchAlerts();
  }, []);

  const handleAlertPress = async (alert: any) => {
    if (!alert.is_read) {
      await markAsRead(alert.id);
    }

    // If it's a price drop alert with confirmation pending, ask user
    if (alert.type === 'price_drop' && alert.data?.needs_confirmation) {
      try {
        await api.post(`/alerts/${alert.id}/confirm`);
        fetchAlerts(); // Refresh
      } catch {}
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
        </Pressable>
        <Text style={styles.title}>Notifications</Text>
        {unreadCount > 0 && (
          <Pressable onPress={markAllAsRead} style={styles.markAll}>
            <Text style={styles.markAllText}>Mark all read</Text>
          </Pressable>
        )}
      </View>

      {isLoading ? (
        <View style={styles.center}>
          <ActivityIndicator size="large" color={Colors.accent.green} />
        </View>
      ) : alerts.length === 0 ? (
        <View style={styles.center}>
          <Feather name="bell-off" size={48} color={Colors.text.tertiary} />
          <Text style={styles.emptyTitle}>No notifications yet</Text>
          <Text style={styles.emptyDesc}>
            You'll see price drop alerts, restock reminders, and savings confirmations here.
          </Text>
        </View>
      ) : (
        <ScrollView
          showsVerticalScrollIndicator={false}
          contentContainerStyle={styles.scroll}
        >
          {alerts.map((alert) => (
            <AlertCard
              key={alert.id}
              alert={alert}
              onPress={() => handleAlertPress(alert)}
            />
          ))}
        </ScrollView>
      )}
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
  },
  backBtn: { marginRight: Spacing.sm },
  title: {
    flex: 1,
    fontFamily: 'DMSerifDisplay_400Regular',
    fontSize: 24,
    color: Colors.text.primary,
  },
  markAll: { paddingVertical: 4, paddingHorizontal: 8 },
  markAllText: {
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 13,
    color: Colors.accent.green,
  },
  scroll: { padding: Spacing.md },
  center: {
    flex: 1,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: Spacing.xl,
  },
  emptyTitle: {
    fontFamily: 'DMSans_600SemiBold',
    fontSize: 18,
    color: Colors.text.primary,
    marginTop: Spacing.md,
  },
  emptyDesc: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 14,
    color: Colors.text.secondary,
    textAlign: 'center',
    marginTop: Spacing.xs,
    lineHeight: 20,
  },
});
