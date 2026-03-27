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

interface StoreTagProps {
  storeName: string;
  size?: 'sm' | 'md' | 'lg';
}

export default function StoreTag({ storeName, size = 'sm' }: StoreTagProps) {
  const colors = STORE_COLORS[storeName as StoreName] ?? {
    primary: Colors.text.secondary,
    light: Colors.surface.alt,
  };

  const logo = STORE_LOGOS[storeName] || null;
  const logoSize = size === 'lg' ? 24 : size === 'md' ? 18 : 14;
  const fontSize = size === 'lg' ? 15 : size === 'md' ? 13 : 11;
  const padV = size === 'lg' ? 6 : size === 'md' ? 4 : 2;
  const padH = size === 'lg' ? 14 : size === 'md' ? 12 : 8;

  return (
    <View style={[styles.tag, { backgroundColor: colors.light, paddingVertical: padV, paddingHorizontal: padH }]}>
      {logo && (
        <Image source={logo} style={{ width: logoSize, height: logoSize, borderRadius: 3 }} resizeMode="contain" />
      )}
      <Text style={[styles.text, { color: colors.primary, fontSize }]}>{storeName}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  tag: { borderRadius: BorderRadius.full, alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 5 },
  text: { fontFamily: 'DMSans_600SemiBold' },
});
