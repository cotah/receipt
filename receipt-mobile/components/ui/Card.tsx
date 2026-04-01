import React from 'react';
import { Pressable, View, StyleSheet, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

type GlassVariant = 'default' | 'elevated' | 'glass' | 'bright' | 'accent' | 'gold';

interface CardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  variant?: GlassVariant;
}

const VARIANT_STYLES: Record<GlassVariant, { bg: string; border: string }> = {
  default:  { bg: Colors.surface.card,       border: Colors.surface.border },
  elevated: { bg: Colors.surface.elevated,   border: Colors.surface.borderBright },
  glass:    { bg: Colors.surface.card,       border: Colors.surface.border },
  bright:   { bg: Colors.surface.cardBright, border: Colors.surface.borderBright },
  accent:   { bg: Colors.surface.cardAccent, border: Colors.accent.greenBorder },
  gold:     { bg: Colors.surface.cardGold,   border: Colors.accent.amberBorder },
};

export default function Card({ children, style, onPress, variant = 'default' }: CardProps) {
  const v = VARIANT_STYLES[variant];
  const shadow = variant === 'elevated' ? Shadows.float : Shadows.card;

  const content = (
    <View
      style={[
        styles.card,
        shadow,
        {
          backgroundColor: v.bg,
          borderColor: v.border,
        },
        style,
      ]}
    >
      {/* Glass refraction highlight — subtle gradient overlay at the top */}
      <View style={styles.glassOverlay} pointerEvents="none">
        <LinearGradient
          colors={[Colors.glass.highlight, Colors.glass.highlightEnd]}
          style={StyleSheet.absoluteFill}
          start={{ x: 0, y: 0 }}
          end={{ x: 0, y: 1 }}
        />
      </View>
      {children}
    </View>
  );

  if (onPress) {
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => ({
          opacity: pressed ? 0.92 : 1,
          transform: [{ scale: pressed ? 0.98 : 1 }],
        })}
      >
        {content}
      </Pressable>
    );
  }
  return content;
}

const styles = StyleSheet.create({
  card: {
    borderRadius: BorderRadius.lg,
    padding: Spacing.md,
    borderWidth: 0.5,
    overflow: 'hidden',
  },
  glassOverlay: {
    ...StyleSheet.absoluteFillObject,
    height: '50%',
    borderRadius: BorderRadius.lg,
  },
});
