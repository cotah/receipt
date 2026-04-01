import React from 'react';
import { Pressable, Text, StyleSheet, ActivityIndicator, ViewStyle } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger';
type Size = 'sm' | 'md' | 'lg';

interface ButtonProps {
  title: string;
  onPress: () => void;
  variant?: Variant;
  size?: Size;
  disabled?: boolean;
  loading?: boolean;
  icon?: keyof typeof Feather.glyphMap;
  fullWidth?: boolean;
}

export default function Button({
  title, onPress, variant = 'primary', size = 'md',
  disabled = false, loading = false, icon, fullWidth = false,
}: ButtonProps) {
  const colors: Record<Variant, { bg: string; text: string; border: string }> = {
    primary: { bg: 'rgba(80,200,120,0.20)', text: '#7DDFAA', border: 'rgba(80,200,120,0.30)' },
    secondary: { bg: 'rgba(255,255,255,0.08)', text: '#FFFFFF', border: 'rgba(255,255,255,0.15)' },
    ghost: { bg: 'transparent', text: '#7DDFAA', border: 'transparent' },
    danger: { bg: 'rgba(240,149,149,0.08)', text: '#F09595', border: 'rgba(240,149,149,0.25)' },
  };
  const c = colors[variant];
  const padV = size === 'sm' ? 10 : size === 'lg' ? 18 : 14;
  const padH = size === 'sm' ? 18 : size === 'lg' ? 36 : 28;
  const fontSize = size === 'sm' ? 13 : size === 'lg' ? 17 : 15;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        {
          backgroundColor: c.bg,
          paddingVertical: padV,
          paddingHorizontal: padH,
          opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
          transform: [{ scale: pressed ? 0.97 : 1 }],
          width: fullWidth ? '100%' : undefined,
          borderWidth: variant === 'ghost' ? 0 : 0.5,
          borderColor: c.border,
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={c.text} />
      ) : (
        <>
          {icon && <Feather name={icon} size={fontSize + 2} color={c.text} style={{ marginRight: Spacing.sm }} />}
          <Text style={[styles.text, { color: c.text, fontSize }]}>{title}</Text>
        </>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  base: {
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    borderRadius: BorderRadius.lg,
  },
  text: {
    fontFamily: 'DMSans_700Bold',
    letterSpacing: 0.3,
  },
});
