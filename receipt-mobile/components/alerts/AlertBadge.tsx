import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Colors } from '../../constants/colors';

interface AlertBadgeProps {
  count: number;
}

export default function AlertBadge({ count }: AlertBadgeProps) {
  if (count <= 0) return null;
  const display = count > 99 ? '99+' : String(count);

  return (
    <View style={styles.badge}>
      <Text style={styles.text}>{display}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    position: 'absolute',
    top: -4,
    right: -8,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    backgroundColor: Colors.accent.red,
    alignItems: 'center',
    justifyContent: 'center',
    paddingHorizontal: 4,
  },
  text: {
    fontFamily: 'DMSans_700Bold',
    fontSize: 10,
    color: '#FFFFFF',
  },
});
