import React from 'react';
import { Pressable, View, StyleSheet, ViewStyle } from 'react-native';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

interface CardProps {
  children: React.ReactNode;
  style?: ViewStyle;
  onPress?: () => void;
  variant?: 'default' | 'elevated';
}

export default function Card({ children, style, onPress, variant = 'default' }: CardProps) {
  const shadow = variant === 'elevated' ? Shadows.float : Shadows.card;
  const content = (
    <View style={[styles.card, shadow, style]}>
      {children}
    </View>
  );

  if (onPress) {
    return (
      <Pressable onPress={onPress} style={({ pressed }) => ({ opacity: pressed ? 0.95 : 1 })}>
        {content}
      </Pressable>
    );
  }
  return content;
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: Colors.surface.card,
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
  },
});
