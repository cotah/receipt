import React, { useState } from 'react';
import { View, TextInput, Text, StyleSheet, TextInputProps, Pressable } from 'react-native';
import { Feather } from '@expo/vector-icons';
import { Colors } from '../../constants/colors';
import { BorderRadius, Spacing } from '../../constants/typography';

interface InputProps extends TextInputProps {
  label?: string;
  error?: string;
  leftIcon?: keyof typeof Feather.glyphMap;
  rightIcon?: keyof typeof Feather.glyphMap;
}

export default function Input({ label, error, leftIcon, rightIcon, style, secureTextEntry, ...props }: InputProps) {
  const [focused, setFocused] = useState(false);
  const [passwordVisible, setPasswordVisible] = useState(false);

  const isPassword = secureTextEntry === true;
  const borderColor = error ? Colors.accent.red : focused ? '#7DDFAA' : 'rgba(255,255,255,0.12)';

  return (
    <View style={styles.container}>
      {label && <Text style={styles.label}>{label}</Text>}
      <View style={[styles.inputWrap, { borderColor }]}>
        {leftIcon && <Feather name={leftIcon} size={18} color="rgba(255,255,255,0.35)" style={styles.icon} />}
        <TextInput
          {...props}
          secureTextEntry={isPassword && !passwordVisible}
          style={[styles.input, style]}
          placeholderTextColor={Colors.text.tertiary}
          onFocus={(e) => { setFocused(true); props.onFocus?.(e); }}
          onBlur={(e) => { setFocused(false); props.onBlur?.(e); }}
        />
        {isPassword ? (
          <Pressable onPress={() => setPasswordVisible((v) => !v)} hitSlop={10}>
            <Feather
              name={passwordVisible ? 'eye' : 'eye-off'}
              size={18}
              color={Colors.text.tertiary}
            />
          </Pressable>
        ) : (
          rightIcon && <Feather name={rightIcon} size={18} color={Colors.text.tertiary} style={styles.icon} />
        )}
      </View>
      {error && <Text style={styles.error}>{error}</Text>}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginBottom: Spacing.md },
  label: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 13,
    color: Colors.text.secondary,
    marginBottom: Spacing.xs,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderRadius: 14,
    borderWidth: 0.5,
    paddingHorizontal: Spacing.md,
  },
  input: {
    flex: 1,
    fontFamily: 'DMSans_400Regular',
    fontSize: 16,
    color: Colors.text.primary,
    paddingVertical: Spacing.md,
  },
  icon: { marginRight: Spacing.sm },
  error: {
    fontFamily: 'DMSans_400Regular',
    fontSize: 12,
    color: Colors.accent.red,
    marginTop: Spacing.xs,
  },
});
