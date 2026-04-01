import React from 'react';
import { Pressable, View, StyleSheet, ViewStyle, StyleProp } from 'react-native';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

interface CardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  variant?: 'default' | 'elevated' | 'glass' | 'accent' | 'gold';
}

export default function Card({ children, style, onPress, variant = 'default' }: CardProps) {
  const shadow = variant === 'elevated' ? Shadows.float : Shadows.card;

  const variantStyles: Record<string, ViewStyle> = {
    default: { backgroundColor: Colors.glass.bg, borderColor: Colors.glass.border },
    elevated: { backgroundColor: Colors.glass.bgBright, borderColor: Colors.glass.borderBright },
    glass: { backgroundColor: Colors.glass.bg, borderColor: Colors.glass.border },
    accent: { backgroundColor: Colors.glass.bgAccent, borderColor: Colors.glass.borderAccent },
    gold: { backgroundColor: Colors.glass.bgGold, borderColor: Colors.glass.borderGold },
  };

  const content = (
    <View style={[styles.card, shadow, variantStyles[variant], style]}>
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
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    borderWidth: 0.5,
    overflow: 'hidden',
  },
});
