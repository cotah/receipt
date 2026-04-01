import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

type Variant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface BadgeProps {
  text: string;
  variant?: Variant;
  size?: 'sm' | 'md';
}

const COLORS: Record<Variant, { bg: string; text: string; border: string }> = {
  success: { bg: 'rgba(80,200,120,0.15)', text: '#7DDFAA', border: 'rgba(80,200,120,0.25)' },
  warning: { bg: 'rgba(212,168,67,0.12)', text: '#F0D68A', border: 'rgba(212,168,67,0.20)' },
  danger: { bg: 'rgba(240,149,149,0.12)', text: '#F09595', border: 'rgba(240,149,149,0.20)' },
  info: { bg: 'rgba(133,183,235,0.12)', text: '#85B7EB', border: 'rgba(133,183,235,0.20)' },
  neutral: { bg: 'rgba(255,255,255,0.08)', text: 'rgba(255,255,255,0.55)', border: 'rgba(255,255,255,0.12)' },
};

export default function Badge({ text, variant = 'neutral', size = 'sm' }: BadgeProps) {
  const colors = COLORS[variant];
  const fontSize = size === 'sm' ? 11 : 13;
  const padV = size === 'sm' ? 2 : 4;
  const padH = size === 'sm' ? 8 : 12;

  return (
    <View style={[styles.badge, { backgroundColor: colors.bg, borderColor: colors.border, paddingVertical: padV, paddingHorizontal: padH }]}>
      <Text style={[styles.text, { color: colors.text, fontSize }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: BorderRadius.full,
    alignSelf: 'flex-start',
    borderWidth: 0.5,
  },
  text: {
    fontFamily: 'DMSans_600SemiBold',
  },
});
