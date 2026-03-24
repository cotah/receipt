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
  success: { bg: Colors.accent.green, text: '#FFFFFF' },
  warning: { bg: Colors.accent.amber, text: '#FFFFFF' },
  danger: { bg: Colors.accent.red, text: '#FFFFFF' },
  info: { bg: Colors.accent.blue, text: '#FFFFFF' },
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
