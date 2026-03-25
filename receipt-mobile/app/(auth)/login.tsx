import React, { useState } from 'react';
import { View, Text, Image, StyleSheet, KeyboardAvoidingView, Platform, Pressable } from 'react-native';

let wordmarkSource: ReturnType<typeof require> | null = null;
try {
  wordmarkSource = require('../../assets/smartdocket-wordmark.png');
} catch {
  wordmarkSource = null;
}
import { Link } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather } from '@expo/vector-icons';
import Input from '../../components/ui/Input';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [magicLinkSent, setMagicLinkSent] = useState(false);
  const [useMagicLink, setUseMagicLink] = useState(false);
  const [error, setError] = useState('');

  const signInMagic = useAuthStore((s) => s.signInWithMagicLink);
  const signInPassword = useAuthStore((s) => s.signInWithPassword);
  const signInOAuth = useAuthStore((s) => s.signInWithOAuth);

  const handlePasswordLogin = async () => {
    if (!email.trim() || !password.trim()) return;
    setLoading(true);
    setError('');
    const result = await signInPassword(email.trim(), password);
    setLoading(false);
    if (result.error) setError(result.error.message);
  };

  const handleMagicLink = async () => {
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    const result = await signInMagic(email.trim());
    setLoading(false);
    if (result.error) {
      setError(result.error.message);
    } else {
      setMagicLinkSent(true);
    }
  };

  const handleOAuth = async (provider: 'apple' | 'google') => {
    setError('');
    const result = await signInOAuth(provider);
    if (result.error) setError(result.error.message);
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.content}>
        <View style={styles.header}>
          {wordmarkSource ? (
            <Image source={wordmarkSource} style={styles.wordmark} resizeMode="contain" />
          ) : (
            <Text style={styles.logo}>SmartDocket</Text>
          )}
          <Text style={styles.subtitle}>Smart grocery spending</Text>
        </View>

        {magicLinkSent ? (
          <View style={styles.sentBox}>
            <Text style={styles.sentTitle}>Check your email!</Text>
            <Text style={styles.sentText}>
              We sent a magic link to {email}. Tap the link to sign in.{'\n\n'}
              If it doesn't work, use email + password instead.
            </Text>
            <Pressable style={styles.backBtn} onPress={() => { setMagicLinkSent(false); setUseMagicLink(false); }}>
              <Text style={styles.backBtnText}>Back to sign in</Text>
            </Pressable>
          </View>
        ) : (
          <View style={styles.form}>
            {/* OAuth buttons */}
            <Pressable style={styles.oauthBtnApple} onPress={() => handleOAuth('apple')}>
              <Feather name="smartphone" size={18} color="#FFF" />
              <Text style={styles.oauthBtnAppleText}>Continue with Apple</Text>
            </Pressable>
            <Pressable style={styles.oauthBtnGoogle} onPress={() => handleOAuth('google')}>
              <Feather name="globe" size={18} color="#333" />
              <Text style={styles.oauthBtnGoogleText}>Continue with Google</Text>
            </Pressable>

            <View style={styles.dividerRow}>
              <View style={styles.dividerLine} />
              <Text style={styles.dividerText}>or</Text>
              <View style={styles.dividerLine} />
            </View>

            {useMagicLink ? (
              <>
                <Input
                  label="Email"
                  placeholder="you@example.com"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  leftIcon="mail"
                  error={error}
                />
                <Button title="Send Magic Link" onPress={handleMagicLink} loading={loading} fullWidth icon="send" />
                <Pressable onPress={() => { setUseMagicLink(false); setError(''); }}>
                  <Text style={styles.toggleText}>Use password instead</Text>
                </Pressable>
              </>
            ) : (
              <>
                <Input
                  label="Email"
                  placeholder="you@example.com"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  leftIcon="mail"
                  error={error}
                />
                <Input
                  label="Password"
                  placeholder="Your password"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry
                  leftIcon="lock"
                />
                <Button title="Sign In" onPress={handlePasswordLogin} loading={loading} fullWidth icon="log-in" />
                <Pressable onPress={() => { setUseMagicLink(true); setError(''); }}>
                  <Text style={styles.toggleText}>Use magic link instead</Text>
                </Pressable>
              </>
            )}

            <Link href="/(auth)/register" asChild>
              <Text style={styles.link}>Don't have an account? Sign up</Text>
            </Link>
          </View>
        )}
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  content: { flex: 1, justifyContent: 'center', paddingHorizontal: Spacing.lg },
  header: { alignItems: 'center', marginBottom: Spacing.xxl },
  wordmark: { width: 260, height: 80 },
  logo: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 48, color: Colors.primary.dark },
  subtitle: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: Colors.text.secondary, marginTop: 4 },
  form: { gap: Spacing.sm },
  oauthBtnApple: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    backgroundColor: '#000', paddingVertical: 14, borderRadius: 12,
  },
  oauthBtnAppleText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#FFF' },
  oauthBtnGoogle: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10,
    backgroundColor: '#FFF', paddingVertical: 14, borderRadius: 12,
    borderWidth: 1, borderColor: '#E5E7EB',
  },
  oauthBtnGoogleText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#333' },
  dividerRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 4 },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#E5E7EB' },
  dividerText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.tertiary, marginHorizontal: 12 },
  toggleText: {
    fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.tertiary,
    textAlign: 'center', textDecorationLine: 'underline',
  },
  link: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.primary.default, textAlign: 'center', marginTop: Spacing.sm },
  sentBox: { alignItems: 'center', padding: Spacing.lg },
  sentTitle: { fontFamily: 'DMSans_700Bold', fontSize: 20, color: Colors.text.primary, marginBottom: Spacing.sm },
  sentText: { fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.secondary, textAlign: 'center', lineHeight: 22 },
  backBtn: { marginTop: Spacing.md, paddingVertical: 10, paddingHorizontal: 20, borderRadius: 10, backgroundColor: Colors.primary.default },
  backBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: '#FFF' },
});
