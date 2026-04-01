import React from 'react';
import { View, Text, Image, StyleSheet } from 'react-native';
import { STORE_COLORS, StoreName } from '../../constants/stores';
import { Colors } from '../../constants/colors';
import { BorderRadius } from '../../constants/typography';

const STORE_LOGOS: Record<string, any> = {
  Tesco: require('../../assets/stores/tesco.png'),
  Lidl: require('../../assets/stores/lidl.png'),
  Aldi: require('../../assets/stores/aldi.png'),
  SuperValu: require('../../assets/stores/supervalu.png'),
  Dunnes: require('../../assets/stores/dunnes.png'),
  'Dunnes Stores': require('../../assets/stores/dunnes.png'),
};

// Normalize store names — OCR may return LIDL, lidl, TESCO, etc
function normalizeStoreName(name: string): string {
  const lower = name.toLowerCase().trim();
  if (lower.includes('lidl')) return 'Lidl';
  if (lower.includes('tesco')) return 'Tesco';
  if (lower.includes('aldi')) return 'Aldi';
  if (lower.includes('supervalu') || lower.includes('super valu')) return 'SuperValu';
  if (lower.includes('dunnes')) return 'Dunnes';
  // Return original with first letter capitalized
  return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
}

interface StoreTagProps {
  storeName: string;
  size?: 'sm' | 'md' | 'lg';
}

export default function StoreTag({ storeName, size = 'sm' }: StoreTagProps) {
  const normalized = normalizeStoreName(storeName);
  const colors = STORE_COLORS[normalized as StoreName] ?? {
    primary: Colors.text.secondary,
    light: Colors.surface.alt,
  };

  const logo = STORE_LOGOS[normalized] || null;
  const displayName = normalized;
  const logoSize = size === 'lg' ? 32 : size === 'md' ? 18 : 14;
  const fontSize = size === 'lg' ? 20 : size === 'md' ? 13 : 11;
  const padV = size === 'lg' ? 10 : size === 'md' ? 4 : 2;
  const padH = size === 'lg' ? 18 : size === 'md' ? 12 : 8;

  return (
    <View style={[styles.tag, { backgroundColor: colors.light, paddingVertical: padV, paddingHorizontal: padH }]}>
      {logo && (
        <Image source={logo} style={{ width: logoSize, height: logoSize, borderRadius: 3 }} resizeMode="contain" />
      )}
      <Text style={[styles.text, { color: colors.primary, fontSize }]}>{displayName}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: { borderRadius: BorderRadius.full, alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 5 },
  text: { fontFamily: 'DMSans_600SemiBold' },
});
