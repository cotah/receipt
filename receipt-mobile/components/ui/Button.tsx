import React from 'react';
import { Pressable, Text, StyleSheet, ActivityIndicator, ViewStyle } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
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
  const bgColor = variant === 'primary' ? Colors.primary.dark
    : variant === 'secondary' ? Colors.primary.pale : 'transparent';
  const textColor = variant === 'primary' ? Colors.text.inverse
    : Colors.primary.dark;
  const padV = size === 'sm' ? 8 : size === 'lg' ? 16 : 12;
  const padH = size === 'sm' ? 16 : size === 'lg' ? 32 : 24;
  const fontSize = size === 'sm' ? 13 : size === 'lg' ? 17 : 15;

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        {
          backgroundColor: bgColor,
          paddingVertical: padV,
          paddingHorizontal: padH,
          opacity: disabled ? 0.5 : pressed ? 0.8 : 1,
          width: fullWidth ? '100%' : undefined,
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
    fontFamily: 'DMSans_600SemiBold',
  },
});
