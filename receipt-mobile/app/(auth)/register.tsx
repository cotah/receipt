import React, { useState } from 'react';
import { View, Text, Image, StyleSheet, KeyboardAvoidingView, Platform, Pressable, ScrollView } from 'react-native';

const googleLogo = require('../../assets/images/google-logo.png');
import { Link } from 'expo-router';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Feather } from '@expo/vector-icons';
import Input from '../../components/ui/Input';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';
import { supabase } from '../../services/supabase';

export default function RegisterScreen() {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [password, setPassword] = useState('');
  const [referralCode, setReferralCode] = useState('');
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  const signUp = useAuthStore((s) => s.signUpWithPassword);
  const signInOAuth = useAuthStore((s) => s.signInWithOAuth);

  const handleRegister = async () => {
    if (!name.trim() || !email.trim() || !password.trim()) {
      setError('Name, email and password are required');
      return;
    }
    if (password.length < 6) {
      setError('Password must be at least 6 characters');
      return;
    }
    setLoading(true);
    setError('');

    const result = await signUp(email.trim(), password, name.trim(), phone.trim() || undefined);
    if (result.error) {
      setError(result.error.message);
      setLoading(false);
      return;
    }

    // Redeem referral code if provided
    if (referralCode.trim()) {
      try {
        const { data: { session } } = await supabase.auth.getSession();
        if (session) {
          const apiUrl = process.env.EXPO_PUBLIC_API_URL;
          await fetch(`${apiUrl}/users/me/redeem-referral`, {
            method: 'POST',
            headers: {
              'Authorization': `Bearer ${session.access_token}`,
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ referral_code: referralCode.trim().toUpperCase() }),
          });
        }
      } catch {
        // Referral is optional — don't block registration
      }
    }

    setLoading(false);
    setSuccess(true);
  };

  const handleOAuth = async (provider: 'apple' | 'google') => {
    setError('');
    const result = await signInOAuth(provider);
    if (result.error) setError(result.error.message);
  };

  return (
    <SafeAreaView style={styles.container}>
      <KeyboardAvoidingView behavior={Platform.OS === 'ios' ? 'padding' : 'height'} style={{ flex: 1 }}>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.header}>
            <Text style={styles.title}>Create Account</Text>
            <Text style={styles.subtitle}>Start tracking your grocery spending</Text>
          </View>

          {success ? (
            <View style={styles.sentBox}>
              <Text style={styles.sentTitle}>Welcome to SmartDocket!</Text>
              <Text style={styles.sentText}>
                Please check your email to verify your account, then sign in.
              </Text>
            </View>
          ) : (
            <View style={styles.form}>
              {/* OAuth buttons */}
              <Pressable style={styles.oauthBtnApple} onPress={() => handleOAuth('apple')}>
                <Feather name="smartphone" size={18} color="#FFF" />
                <Text style={styles.oauthBtnAppleText}>Continue with Apple</Text>
              </Pressable>
              <Pressable style={styles.oauthBtnGoogle} onPress={() => handleOAuth('google')}>
                <Image source={googleLogo} style={styles.googleIcon} />
                <Text style={styles.oauthBtnGoogleText}>Continue with Google</Text>
              </Pressable>

              <View style={styles.dividerRow}>
                <View style={styles.dividerLine} />
                <Text style={styles.dividerText}>or sign up with email</Text>
                <View style={styles.dividerLine} />
              </View>

              <Input
                label="Full Name"
                placeholder="Your name"
                value={name}
                onChangeText={setName}
                leftIcon="user"
              />
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
                label="Phone (optional)"
                placeholder="+353 86 123 4567"
                value={phone}
                onChangeText={setPhone}
                keyboardType="phone-pad"
                leftIcon="phone"
              />
              <Input
                label="Password"
                placeholder="At least 6 characters"
                value={password}
                onChangeText={setPassword}
                secureTextEntry
                leftIcon="lock"
              />
              <Input
                label="Referral Code (optional)"
                placeholder="e.g. SMART-ABC123"
                value={referralCode}
                onChangeText={setReferralCode}
                autoCapitalize="characters"
                leftIcon="gift"
              />

              <Button title="Create Account" onPress={handleRegister} loading={loading} fullWidth icon="user-plus" />

              <Link href="/(auth)/login" asChild>
                <Text style={styles.link}>Already have an account? Sign in</Text>
              </Link>
            </View>
          )}
        </ScrollView>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  content: { flexGrow: 1, justifyContent: 'center', paddingHorizontal: Spacing.lg, paddingVertical: Spacing.lg },
  header: { alignItems: 'center', marginBottom: Spacing.xl },
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 32, color: Colors.primary.dark },
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
  googleIcon: { width: 20, height: 20 },
  oauthBtnGoogleText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#333' },
  dividerRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 4 },
  dividerLine: { flex: 1, height: 1, backgroundColor: '#E5E7EB' },
  dividerText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.tertiary, marginHorizontal: 12 },
  link: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.primary.default, textAlign: 'center', marginTop: Spacing.sm },
  sentBox: { alignItems: 'center', padding: Spacing.lg },
  sentTitle: { fontFamily: 'DMSans_700Bold', fontSize: 20, color: Colors.text.primary, marginBottom: Spacing.sm },
  sentText: { fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.secondary, textAlign: 'center', lineHeight: 22 },
});
