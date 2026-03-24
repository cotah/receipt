import React, { useState } from 'react';
import { View, Text, StyleSheet, KeyboardAvoidingView, Platform } from 'react-native';
import { Link, useRouter } from 'expo-router';
import * as Linking from 'expo-linking';
import { SafeAreaView } from 'react-native-safe-area-context';
import Input from '../../components/ui/Input';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { supabase } from '../../services/supabase';

export default function RegisterScreen() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const router = useRouter();

  const handleRegister = async () => {
    if (!email.trim()) return;
    setLoading(true);
    setError('');
    const { error: err } = await supabase.auth.signInWithOtp({
      email: email.trim(),
      options: {
        emailRedirectTo: Linking.createURL('auth/callback'),
        data: { full_name: name.trim() },
      },
    });
    setLoading(false);
    if (err) {
      setError(err.message);
    } else {
      setSent(true);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={styles.content}>
        <View style={styles.header}>
          <Text style={styles.title}>Create Account</Text>
          <Text style={styles.subtitle}>Start tracking your grocery spending</Text>
        </View>

        {sent ? (
          <View style={styles.sentBox}>
            <Text style={styles.sentTitle}>Check your email!</Text>
            <Text style={styles.sentText}>We sent you a magic link to {email}.</Text>
          </View>
        ) : (
          <View style={styles.form}>
            <Input label="Name" placeholder="Your name" value={name} onChangeText={setName} leftIcon="user" />
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
            <Button title="Create Account" onPress={handleRegister} loading={loading} fullWidth icon="user-plus" />
            <Link href="/(auth)/login" asChild>
              <Text style={styles.link}>Already have an account? Sign in</Text>
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
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 32, color: Colors.primary.dark },
  subtitle: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: Colors.text.secondary, marginTop: 4 },
  form: { gap: Spacing.md },
  link: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.primary.default, textAlign: 'center', marginTop: Spacing.md },
  sentBox: { alignItems: 'center', padding: Spacing.lg },
  sentTitle: { fontFamily: 'DMSans_700Bold', fontSize: 20, color: Colors.text.primary, marginBottom: Spacing.sm },
  sentText: { fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.secondary, textAlign: 'center' },
});
