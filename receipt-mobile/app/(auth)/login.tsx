import React, { useState } from 'react';
import { View, Text, Image, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { Link } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import Input from '../../components/ui/Input';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';

export default function LoginScreen() {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const signIn = useAuthStore((s) => s.signInWithMagicLink);

  const handleSignIn = async () => {
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    const result = await signIn(email.trim());
    setLoading(false);
    if (result.error) {
      setError(result.error.message);
    } else {
      setSent(true);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.content}>
        <View style={styles.header}>
          <Image
            source={require('../../assets/smartdocket-wordmark.png')}
            style={styles.wordmark}
            resizeMode="contain"
          />
          <Text style={styles.subtitle}>Smart grocery spending</Text>
        </View>

        {sent ? (
          <View style={styles.sentBox}>
            <Text style={styles.sentTitle}>Check your email!</Text>
            <Text style={styles.sentText}>We sent you a magic link to {email}. Tap the link to sign in.</Text>
          </View>
        ) : (
          <View style={styles.form}>
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
            <Button
              title="Send Magic Link"
              onPress={handleSignIn}
              loading={loading}
              fullWidth
              icon="send"
            />
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
  subtitle: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: Colors.text.secondary, marginTop: 4 },
  form: { gap: Spacing.md },
  link: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.primary.default, textAlign: 'center', marginTop: Spacing.md },
  sentBox: { alignItems: 'center', padding: Spacing.lg },
  sentTitle: { fontFamily: 'DMSans_700Bold', fontSize: 20, color: Colors.text.primary, marginBottom: Spacing.sm },
  sentText: { fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.secondary, textAlign: 'center', lineHeight: 22 },
});
