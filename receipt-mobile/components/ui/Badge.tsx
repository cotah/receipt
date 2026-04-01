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

const COLORS: Record<Variant, { bg: string; text: string }> = {
  success: { bg: 'rgba(60,179,113,0.12)', text: '#22A95B' },
  warning: { bg: 'rgba(232,160,32,0.12)', text: '#C28716' },
  danger: { bg: 'rgba(217,79,79,0.10)', text: '#C74343' },
  info: { bg: 'rgba(45,110,168,0.10)', text: '#2567A0' },
  neutral: { bg: Colors.surface.alt, text: Colors.text.secondary },
};

export default function Badge({ text, variant = 'neutral', size = 'sm' }: BadgeProps) {
  const colors = COLORS[variant];
  const fontSize = size === 'sm' ? 11 : 13;
  const padV = size === 'sm' ? 2 : 4;
  const padH = size === 'sm' ? 8 : 12;

  return (
    <View style={[styles.badge, { backgroundColor: colors.bg, paddingVertical: padV, paddingHorizontal: padH }]}>
      <Text style={[styles.text, { color: colors.text, fontSize }]}>{text}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    borderRadius: BorderRadius.full,
    alignSelf: 'flex-start',
  },
  text: {
    fontFamily: 'DMSans_600SemiBold',
  },
});
