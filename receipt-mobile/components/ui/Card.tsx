import React from 'react';
import { Pressable, View, StyleSheet, ViewStyle } from 'react-native';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  onPress?: () => void;
  variant?: 'default' | 'elevated' | 'glass';
}

export default function Card({ children, style, onPress, variant = 'default' }: CardProps) {
  const shadow = variant === 'elevated' ? Shadows.float : Shadows.card;
  const bg = variant === 'glass'
    ? Colors.surface.cardGlass
    : Colors.surface.card;

  const content = (
    <View style={[styles.card, shadow, { backgroundColor: bg }, style]}>
      {children}
    </View>
  );

  if (onPress) {
    return (
      <Pressable onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.95 : 1, transform: [{ scale: pressed ? 0.98 : 1 }] })}>
        {content}
      </Pressable>
    );
  }
  return content;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface.card,
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    borderWidth: 1,
    borderColor: 'rgba(255,255,255,0.7)',
  },
});
