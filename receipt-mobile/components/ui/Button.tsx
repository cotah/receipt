import React from 'react';
import { Pressable, Text, StyleSheet, ActivityIndicator, ViewStyle } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

type Variant = 'primary' | 'secondary' | 'ghost';
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
  const bgColor = variant === 'primary' ? Colors.primary.default
    : variant === 'secondary' ? Colors.primary.pale : 'transparent';
  const textColor = variant === 'primary' ? Colors.text.inverse
    : Colors.primary.dark;
  const padV = size === 'sm' ? 10 : size === 'lg' ? 18 : 14;
  const padH = size === 'sm' ? 18 : size === 'lg' ? 36 : 28;
  const fontSize = size === 'sm' ? 13 : size === 'lg' ? 17 : 15;
  const shadow = variant === 'primary' ? Shadows.card : {};

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        shadow as ViewStyle,
        {
          backgroundColor: bgColor,
          paddingVertical: padV,
          paddingHorizontal: padH,
          opacity: disabled ? 0.5 : pressed ? 0.85 : 1,
          transform: [{ scale: pressed ? 0.97 : 1 }],
          width: fullWidth ? '100%' : undefined,
          borderWidth: variant === 'secondary' ? 1.5 : 0,
          borderColor: variant === 'secondary' ? Colors.primary.default : 'transparent',
        },
      ]}
    >
      {loading ? (
        <ActivityIndicator size="small" color={textColor} />
      ) : (
        <>
          {icon && <Feather name={icon} size={fontSize + 2} color={textColor} style={{ marginRight: Spacing.sm }} />}
          <Text style={[styles.text, { color: textColor, fontSize }]}>{title}</Text>
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
