import React from 'react';
import { View, Pressable, StyleSheet, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';

type Variant = 'standard' | 'hero';

interface GlassCardProps {
  variant?: Variant;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  children: React.ReactNode;
}

const GRADIENT_COLORS: Record<Variant, [string, string]> = {
  standard: ['rgba(27,94,59,0.5)', 'rgba(13,40,24,0.9)'],
  hero: ['rgba(27,94,59,0.8)', 'rgba(13,40,24,0.95)'],
};

export default function GlassCard({ variant = 'standard', style, onPress, children }: GlassCardProps) {
  const inner = (
    <>
      <LinearGradient
        colors={GRADIENT_COLORS[variant]}
        start={{ x: 0.5, y: 0 }}
        end={{ x: 0.5, y: 1 }}
        style={StyleSheet.absoluteFill}
      />
      {variant === 'hero' && (
        <>
          <LinearGradient
            colors={['rgba(125,223,170,0.08)', 'rgba(125,223,170,0)']}
            start={{ x: 0.5, y: 0 }}
            end={{ x: 0.5, y: 1 }}
            style={styles.heroGlow}
            pointerEvents="none"
          />
          <LinearGradient
            colors={['rgba(0,0,0,0)', 'rgba(0,0,0,0.12)']}
            start={{ x: 0.5, y: 0 }}
            end={{ x: 0.5, y: 1 }}
            style={styles.heroShadow}
            pointerEvents="none"
          />
        </>
      )}
      {children}
    </>
  );

  if (onPress) {
    return (
      <Pressable
        onPress={onPress}
        style={({ pressed }) => [
          styles.base,
          style,
          pressed && styles.pressed,
        ]}
      >
        {inner}
      </Pressable>
    );
  }

  return <View style={[styles.base, style]}>{inner}</View>;
}

const styles = StyleSheet.create({
  base: {
    borderRadius: 18,
    backgroundColor: 'rgba(13,40,24,0.9)',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(125,223,170,0.15)',
    padding: 16,
    overflow: 'hidden',
  },
  pressed: { opacity: 0.95, transform: [{ scale: 0.98 }] },
  heroGlow: { position: 'absolute', top: 0, left: 0, right: 0, height: '55%' },
  heroShadow: { position: 'absolute', bottom: 0, left: 0, right: 0, height: '45%' },
});
