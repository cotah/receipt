import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { BorderRadius } from '../../constants/typography';

interface ExpiryBadgeProps {
  validUntil: string;
  size?: 'sm' | 'md';
}

/**
 * Shows how much time is left on a deal.
 * Red = ends tomorrow, Amber = 2-3 days, Green = 4+ days, Hidden = expired/invalid
 */
export default function ExpiryBadge({ validUntil, size = 'sm' }: ExpiryBadgeProps) {
  if (!validUntil) return null;

  const now = new Date();
  const expires = new Date(validUntil);
  const diffMs = expires.getTime() - now.getTime();
  const diffDays = Math.ceil(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays < 0) return null; // Already expired

  let label: string;
  let bg: string;
  let textColor: string;

  if (diffDays <= 1) {
    label = 'Ends tomorrow';
    bg = 'rgba(217,79,79,0.10)';
    textColor = '#C74343';
  } else if (diffDays <= 3) {
    label = `Ends in ${diffDays} days`;
    bg = 'rgba(232,160,32,0.12)';
    textColor = '#C28716';
  } else {
    label = `${diffDays} days left`;
    bg = 'rgba(60,179,113,0.08)';
    textColor = '#1A7D45';
  }

  const fontSize = size === 'sm' ? 10 : 12;
  const padV = size === 'sm' ? 2 : 3;
  const padH = size === 'sm' ? 6 : 8;

  return (
    <View style={[styles.badge, { backgroundColor: bg, paddingVertical: padV, paddingHorizontal: padH }]}>
      <Text style={[styles.text, { color: textColor, fontSize }]}>{label}</Text>
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
