import React from 'react';
import { View, Text, Pressable, StyleSheet } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius } from '../../constants/typography';
import { formatRelativeDate } from '../../utils/formatDate';

const ICON_MAP: Record<string, { name: keyof typeof Feather.glyphMap; color: string }> = {
  restock: { name: 'shopping-cart', color: Colors.accent.amber },
  price_drop: { name: 'trending-down', color: Colors.accent.green },
  price_spike: { name: 'trending-up', color: Colors.accent.red },
  weekly_report: { name: 'bar-chart-2', color: Colors.accent.blue },
};

interface AlertCardProps {
  alert: {
    id: string;
    type: string;
    message: string;
    is_read: boolean;
    created_at: string;
  };
  onPress: () => void;
}

export default function AlertCard({ alert, onPress }: AlertCardProps) {
  const icon = ICON_MAP[alert.type] ?? { name: 'bell' as const, color: Colors.text.secondary };

  return (
    <Pressable onPress={onPress} style={[styles.card, !alert.is_read && styles.unread]}>
      <View style={[styles.iconWrap, { backgroundColor: icon.color + '20' }]}>
        <Feather name={icon.name} size={20} color={icon.color} />
      </View>
      <View style={styles.content}>
        <Text style={styles.message} numberOfLines={3}>{alert.message}</Text>
        <Text style={styles.time}>{formatRelativeDate(alert.created_at)}</Text>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flexDirection: 'row',
    padding: Spacing.md,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderRadius: BorderRadius.md,
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.12)',
    marginBottom: Spacing.sm,
  },
  unread: {
    borderLeftWidth: 3,
    borderLeftColor: Colors.accent.green,
    backgroundColor: 'rgba(80,200,120,0.10)',
  },
  iconWrap: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: 'center',
    justifyContent: 'center',
    marginRight: Spacing.sm,
  },
  content: { flex: 1 },
  message: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: '#FFFFFF', lineHeight: 20 },
  time: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: 'rgba(255,255,255,0.35)', marginTop: 4 },
});
