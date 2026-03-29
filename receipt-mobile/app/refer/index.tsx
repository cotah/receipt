import React, { useState } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Share, TextInput, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';
import api from '../../services/api';

export default function ReferScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const referralCode = profile?.referral_code || 'SMART';
  const [redeemCode, setRedeemCode] = useState('');
  const [redeemLoading, setRedeemLoading] = useState(false);

  const handleShare = async () => {
    try {
      await Share.share({
        message:
          `Join me on SmartDocket — the smart way to save on groceries in Ireland! 🛒\n\n` +
          `Use my code ${referralCode} and we both get 50 bonus points.\n\n` +
          `Download: https://smartdocket.ie`,
      });
    } catch {}
  };

  const handleRedeem = async () => {
    const code = redeemCode.trim().toUpperCase();
    if (!code) return;
    setRedeemLoading(true);
    try {
      await api.post('/users/me/redeem-referral', { code });
      Alert.alert('🎉 Success!', 'You earned 50 bonus points!');
      setRedeemCode('');
      const { data } = await api.get('/users/me');
      useAuthStore.getState().setProfile(data);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || 'Invalid or already used code';
      Alert.alert('Oops', msg);
    } finally {
      setRedeemLoading(false);
    }
  };

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
          <Text style={styles.backText}>Refer a Friend</Text>
        </Pressable>

        {/* Hero */}
        <Card variant="elevated" style={styles.heroCard}>
          <Text style={styles.heroEmoji}>🎁</Text>
          <Text style={styles.heroTitle}>Earn 50 points each</Text>
          <Text style={styles.heroDesc}>Share your code with a friend. When they sign up, you both earn 50 bonus points!</Text>
        </Card>

        {/* Your code */}
        <Text style={styles.sectionTitle}>Your referral code</Text>
        <Card style={styles.codeCard}>
          <Text style={styles.codeText}>{referralCode}</Text>
          <Pressable onPress={handleShare} style={styles.shareBtn}>
            <Feather name="share-2" size={18} color="#FFF" />
            <Text style={styles.shareBtnText}>Share with friends</Text>
          </Pressable>
        </Card>

        {/* How it works */}
        <Text style={styles.sectionTitle}>How it works</Text>
        <Card style={styles.stepsCard}>
          <View style={styles.step}>
            <View style={styles.stepNum}><Text style={styles.stepNumText}>1</Text></View>
            <Text style={styles.stepText}>Share your code with a friend</Text>
          </View>
          <View style={styles.step}>
            <View style={styles.stepNum}><Text style={styles.stepNumText}>2</Text></View>
            <Text style={styles.stepText}>They sign up and enter your code</Text>
          </View>
          <View style={styles.step}>
            <View style={[styles.stepNum, { backgroundColor: Colors.accent.greenSoft }]}>
              <Text style={[styles.stepNumText, { color: Colors.accent.green }]}>✓</Text>
            </View>
            <Text style={styles.stepText}>You both earn 50 bonus points!</Text>
          </View>
        </Card>

        {/* Redeem a code */}
        <Text style={styles.sectionTitle}>Have a friend's code?</Text>
        <Card style={styles.redeemCard}>
          <View style={styles.redeemRow}>
            <TextInput
              style={styles.redeemInput}
              placeholder="Enter code"
              value={redeemCode}
              onChangeText={setRedeemCode}
              autoCapitalize="characters"
              placeholderTextColor={Colors.text.tertiary}
            />
            <Pressable
              onPress={handleRedeem}
              disabled={redeemLoading || !redeemCode.trim()}
              style={[styles.redeemBtn, (!redeemCode.trim() || redeemLoading) && { opacity: 0.5 }]}
            >
              <Text style={styles.redeemBtnText}>{redeemLoading ? '...' : 'Redeem'}</Text>
            </Pressable>
          </View>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  scroll: { padding: Spacing.md, paddingBottom: 40 },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: Spacing.lg, paddingVertical: 4 },
  backText: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: Colors.primary.dark },
  heroCard: {
    alignItems: 'center', paddingVertical: 32,
    backgroundColor: Colors.primary.dark, borderRadius: 24, marginBottom: Spacing.lg,
  },
  heroEmoji: { fontSize: 48 },
  heroTitle: { fontFamily: 'DMSans_700Bold', fontSize: 22, color: Colors.accent.amber, marginTop: 12 },
  heroDesc: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: 'rgba(255,255,255,0.6)', textAlign: 'center', lineHeight: 20, marginTop: 8, paddingHorizontal: 20 },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm, marginTop: Spacing.sm },
  codeCard: { alignItems: 'center', paddingVertical: 24 },
  codeText: {
    fontFamily: 'JetBrainsMono_700Bold', fontSize: 28, color: Colors.primary.dark,
    backgroundColor: Colors.surface.alt, paddingVertical: 14, paddingHorizontal: 28,
    borderRadius: BorderRadius.md, letterSpacing: 3, overflow: 'hidden',
  },
  shareBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: Colors.primary.default, paddingVertical: 14, paddingHorizontal: 28,
    borderRadius: BorderRadius.md, marginTop: 16,
  },
  shareBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: '#FFF' },
  stepsCard: { marginBottom: Spacing.md, gap: 16 },
  step: { flexDirection: 'row', alignItems: 'center', gap: 14 },
  stepNum: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: Colors.accent.amberSoft, alignItems: 'center', justifyContent: 'center',
  },
  stepNumText: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: Colors.accent.amber },
  stepText: { fontFamily: 'DMSans_500Medium', fontSize: 15, color: Colors.text.primary, flex: 1 },
  redeemCard: { marginBottom: Spacing.lg },
  redeemRow: { flexDirection: 'row', gap: 8 },
  redeemInput: {
    flex: 1, fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 16,
    borderWidth: 1.5, borderColor: Colors.surface.border, borderRadius: BorderRadius.md,
    paddingHorizontal: 14, paddingVertical: 12, letterSpacing: 1, color: Colors.text.primary,
  },
  redeemBtn: {
    backgroundColor: Colors.accent.green, paddingHorizontal: 22, paddingVertical: 14,
    borderRadius: BorderRadius.md, justifyContent: 'center',
  },
  redeemBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: '#FFF' },
});
