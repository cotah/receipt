import React from 'react';
import { Pressable, View, StyleSheet, ViewStyle, StyleProp } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

interface CardProps {
  children: React.ReactNode;
  style?: StyleProp<ViewStyle>;
  onPress?: () => void;
  variant?: 'default' | 'elevated' | 'glass' | 'accent' | 'gold' | 'rewardHero' | 'rewardOffer';
}

const GLASS_VARIANTS = new Set(['default', 'elevated', 'glass']);
const GLASS_GRADIENT: [string, string] = ['rgba(27,94,59,0.5)', 'rgba(13,40,24,0.9)'];
const REWARD_HERO_GRADIENT: [string, string] = ['rgba(240,214,138,0.15)', 'rgba(212,168,67,0.05)'];
const REWARD_OFFER_GRADIENT: [string, string] = ['rgba(240,214,138,0.08)', 'rgba(212,168,67,0.02)'];

export default function Card({ children, style, onPress, variant = 'default' }: CardProps) {
  const shadow = variant === 'elevated' ? Shadows.float : Shadows.card;
  const isGlass = GLASS_VARIANTS.has(variant);
  const isRewardHero = variant === 'rewardHero';
  const isRewardOffer = variant === 'rewardOffer';

  const variantStyles: Record<string, ViewStyle> = {
    default: {},
    elevated: {},
    glass: {},
    accent: { backgroundColor: Colors.glass.bgAccent, borderColor: Colors.glass.borderAccent, borderWidth: 0.5 },
    gold: { backgroundColor: Colors.glass.bgGold, borderColor: Colors.glass.borderGold, borderWidth: 0.5 },
    rewardHero: {
      backgroundColor: 'rgba(13,40,24,0.9)',
      borderTopWidth: StyleSheet.hairlineWidth,
      borderTopColor: 'rgba(240,214,138,0.30)',
    },
    rewardOffer: {
      backgroundColor: 'rgba(13,40,24,0.9)',
      borderWidth: 1,
      borderColor: 'rgba(240,214,138,0.40)',
    },
  };

  const baseStyle = isGlass ? styles.glassCard : styles.card;

  const content = (
    <View style={[baseStyle, shadow, variantStyles[variant], style]}>
      {isGlass && (
        <LinearGradient
          colors={GLASS_GRADIENT}
          start={{ x: 0.5, y: 0 }}
          end={{ x: 0.5, y: 1 }}
          style={StyleSheet.absoluteFill}
        />
      )}
      {isRewardHero && (
        <LinearGradient
          colors={REWARD_HERO_GRADIENT}
          start={{ x: 0.5, y: 0 }}
          end={{ x: 0.5, y: 1 }}
          style={StyleSheet.absoluteFill}
          pointerEvents="none"
        />
      )}
      {isRewardOffer && (
        <LinearGradient
          colors={REWARD_OFFER_GRADIENT}
          start={{ x: 0.5, y: 0 }}
          end={{ x: 0.5, y: 1 }}
          style={StyleSheet.absoluteFill}
          pointerEvents="none"
        />
      )}
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
    overflow: 'hidden',
  },
  glassCard: {
    borderRadius: BorderRadius.xl,
    padding: Spacing.md,
    backgroundColor: 'rgba(13,40,24,0.9)',
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(125,223,170,0.15)',
    overflow: 'hidden',
  },
});
