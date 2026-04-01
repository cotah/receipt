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

  if (diffDays < 0) return null;

  let label: string;
  let bg: string;
  let border: string;
  let textColor: string;

  if (diffDays <= 1) {
    label = 'Ends tomorrow';
    bg = 'rgba(240,123,123,0.15)';
    border = 'rgba(240,123,123,0.25)';
    textColor = '#F07B7B';
  } else if (diffDays <= 3) {
    label = `Ends in ${diffDays} days`;
    bg = 'rgba(240,214,138,0.15)';
    border = 'rgba(240,214,138,0.25)';
    textColor = '#F0D68A';
  } else {
    label = `${diffDays} days left`;
    bg = 'rgba(80,200,120,0.12)';
    border = 'rgba(80,200,120,0.25)';
    textColor = '#7DDFAA';
  }

  const fontSize = size === 'sm' ? 10 : 12;
  const padV = size === 'sm' ? 3 : 4;
  const padH = size === 'sm' ? 8 : 10;

  return (
    <View style={[styles.badge, { backgroundColor: bg, borderColor: border, paddingVertical: padV, paddingHorizontal: padH }]}>
      <Text style={[styles.text, { color: textColor, fontSize }]}>{label}</Text>
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
