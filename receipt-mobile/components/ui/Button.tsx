import React from 'react';
import { Pressable, Text, View, StyleSheet, ActivityIndicator, ViewStyle } from 'react-native';
import { LinearGradient } from 'expo-linear-gradient';
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
  // Glass button styles per variant
  const isPrimary = variant === 'primary';
  const isGhost = variant === 'ghost';

  const bgColor = isPrimary
    ? Colors.accent.greenBtn           // rgba(80,200,120,0.20)
    : isGhost
    ? 'transparent'
    : Colors.surface.card;             // rgba(255,255,255,0.08)

  const borderColor = isPrimary
    ? Colors.accent.greenBtnBorder     // rgba(80,200,120,0.30)
    : isGhost
    ? 'transparent'
    : Colors.surface.border;           // rgba(255,255,255,0.15)

  const textColor = '#FFFFFF';

  const padV = size === 'sm' ? 10 : size === 'lg' ? 18 : 14;
  const padH = size === 'sm' ? 18 : size === 'lg' ? 36 : 28;
  const fontSize = size === 'sm' ? 13 : size === 'lg' ? 17 : 15;
  const shadow = isPrimary ? Shadows.glow : {};

  return (
    <Pressable
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        styles.base,
        shadow as ViewStyle,
        {
          backgroundColor: bgColor,
          borderColor: borderColor,
          borderWidth: isGhost ? 0 : 0.5,
          paddingVertical: padV,
          paddingHorizontal: padH,
          opacity: disabled ? 0.4 : pressed ? 0.80 : 1,
          transform: [{ scale: pressed ? 0.97 : 1 }],
          width: fullWidth ? '100%' : undefined,
        },
      ]}
    >
      {/* Glass light effect on top */}
      {!isGhost && (
        <View style={styles.glassHighlight} pointerEvents="none">
          <LinearGradient
            colors={['rgba(255,255,255,0.08)', 'transparent']}
            style={StyleSheet.absoluteFill}
            start={{ x: 0, y: 0 }}
            end={{ x: 0, y: 1 }}
          />
        </View>
      )}
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
    borderRadius: BorderRadius.md, // 14px
    overflow: 'hidden',
    position: 'relative',
  },
  glassHighlight: {
    ...StyleSheet.absoluteFillObject,
    height: '50%',
  },
  text: {
    fontFamily: 'DMSans_700Bold',
    letterSpacing: 0.3,
  },
});
