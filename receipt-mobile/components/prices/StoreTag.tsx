import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { STORE_COLORS, StoreName } from '../../constants/stores';
import { Colors } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

interface StoreTagProps {
  storeName: string;
  size?: 'sm' | 'md';
}

export default function StoreTag({ storeName, size = 'sm' }: StoreTagProps) {
  const colors = STORE_COLORS[storeName as StoreName] ?? {
    primary: Colors.text.secondary,
    light: Colors.surface.alt,
  };
  const fontSize = size === 'sm' ? 11 : 13;
  const padV = size === 'sm' ? 2 : 4;
  const padH = size === 'sm' ? 8 : 12;

  return (
    <View style={[styles.tag, { backgroundColor: colors.light, paddingVertical: padV, paddingHorizontal: padH }]}>
      <Text style={[styles.text, { color: colors.primary, fontSize }]}>{storeName}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: { borderRadius: BorderRadius.full, alignSelf: 'flex-start' },
  text: { fontFamily: 'DMSans_600SemiBold' },
});
