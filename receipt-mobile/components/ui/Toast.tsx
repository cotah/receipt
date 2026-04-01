import React, { useEffect, useRef } from 'react';
import { Animated, Text, StyleSheet, Pressable } from 'react-native';
import { Colors, Shadows } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

type ToastType = 'success' | 'error' | 'info';

interface ToastProps {
  message: string;
  type?: ToastType;
  visible: boolean;
  onDismiss: () => void;
  duration?: number;
}

const BORDER_COLORS: Record<ToastType, string> = {
  success: Colors.accent.green,
  error: Colors.accent.red,
  info: Colors.accent.blue,
};

export default function Toast({ message, type = 'info', visible, onDismiss, duration = 3000 }: ToastProps) {
  const translateY = useRef(new Animated.Value(-100)).current;

  useEffect(() => {
    if (visible) {
      Animated.spring(translateY, { toValue: 0, useNativeDriver: true }).start();
      const timer = setTimeout(onDismiss, duration);
      return () => clearTimeout(timer);
    } else {
      Animated.timing(translateY, { toValue: -100, duration: 200, useNativeDriver: true }).start();
    }
  }, [visible]);

  if (!visible) return null;

  return (
    <Animated.View style={[styles.container, { transform: [{ translateY }] }]}>
      <Pressable
        onPress={onDismiss}
        style={[styles.toast, Shadows.float, { borderLeftColor: BORDER_COLORS[type] }]}
      >
        <Text style={styles.message}>{message}</Text>
      </Pressable>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  container: {
    position: 'absolute',
    top: 60,
    left: Spacing.md,
    right: Spacing.md,
    zIndex: 1000,
  },
  toast: {
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderRadius: BorderRadius.md,
    padding: Spacing.md,
    borderLeftWidth: 4,
    borderWidth: 0.5,
    borderColor: 'rgba(255,255,255,0.10)',
  },
  message: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 14,
    color: Colors.text.primary,
  },
});
