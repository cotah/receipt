import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '../../constants/colors';
import { BorderRadius } from '../../constants/typography';

type Variant = 'success' | 'warning' | 'danger' | 'info' | 'neutral';

interface BadgeProps {
  text: string;
  variant?: Variant;
  size?: 'sm' | 'md';
}

// Liquid Glass pill colors — translucent fills with luminous text
const COLORS: Record<Variant, { bg: string; border: string; text: string }> = {
  success: { bg: 'rgba(80,200,120,0.15)',  border: 'rgba(80,200,120,0.25)',  text: '#7DDFAA' },
  warning: { bg: 'rgba(240,214,138,0.15)', border: 'rgba(240,214,138,0.25)', text: '#F0D68A' },
  danger:  { bg: 'rgba(240,123,123,0.15)', border: 'rgba(240,123,123,0.25)', text: '#F07B7B' },
  info:    { bg: 'rgba(133,183,235,0.15)', border: 'rgba(133,183,235,0.25)', text: '#85B7EB' },
  neutral: { bg: 'rgba(255,255,255,0.06)', border: 'rgba(255,255,255,0.10)', text: 'rgba(255,255,255,0.50)' },
};

export default function Badge({ text, variant = 'neutral', size = 'sm' }: BadgeProps) {
  const colors = COLORS[variant];
  const fontSize = size === 'sm' ? 11 : 13;
  const padV = size === 'sm' ? 3 : 5;
  const padH = size === 'sm' ? 10 : 14;

  return (
    <View
      style={[
        styles.badge,
        {
          backgroundColor: colors.bg,
          borderColor: colors.border,
          paddingVertical: padV,
          paddingHorizontal: padH,
        },
      ]}
    >
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
