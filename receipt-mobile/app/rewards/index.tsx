import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Share, TextInput, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';
import api from '../../services/api';

const LEVELS = [
  { name: 'Starter', emoji: '🌱', min: 0, color: '#9CA3AF' },
  { name: 'Saver', emoji: '💚', min: 100, color: '#3CB371' },
  { name: 'Smart Shopper', emoji: '⭐', min: 500, color: '#E8A020' },
  { name: 'Price Hunter', emoji: '🔥', min: 1000, color: '#EF4444' },
  { name: 'Grocery Pro', emoji: '👑', min: 2500, color: '#8B5CF6' },
];

const EARN_METHODS = [
  { icon: 'camera', title: 'Scan a receipt', points: '10-25', desc: 'Free: 10 pts · Pro: 25 pts' },
  { icon: 'users', title: 'Refer a friend', points: '50', desc: 'Both you and your friend earn 50' },
  { icon: 'check-circle', title: 'Confirm a saving', points: '10', desc: 'Confirm SmartDocket helped you save' },
  { icon: 'tag', title: 'Report a price', points: 'Coming soon', desc: 'Photo shelf labels for bonus points' },
];

function getCurrentLevel(points: number) {
  for (let i = LEVELS.length - 1; i >= 0; i--) {
    if (points >= LEVELS[i].min) return { current: LEVELS[i], next: LEVELS[i + 1] || null, index: i };
  }
  return { current: LEVELS[0], next: LEVELS[1], index: 0 };
}

export default function RewardsScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const points = profile?.points || 0;
  const referralCode = profile?.referral_code || 'SMART';
  const [redeemCode, setRedeemCode] = useState('');
  const [redeemLoading, setRedeemLoading] = useState(false);

  const { current, next, index } = getCurrentLevel(points);
  const progressToNext = next
    ? Math.min((points - current.min) / (next.min - current.min), 1)
    : 1;

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
      // Refresh profile
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
        {/* Header */}
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
          <Text style={styles.backText}>Rewards</Text>
        </Pressable>

        {/* Points + Level hero */}
        <Card variant="elevated" style={styles.heroCard}>
          <Text style={styles.heroEmoji}>{current.emoji}</Text>
          <Text style={styles.heroPoints}>{points}</Text>
          <Text style={styles.heroLabel}>points</Text>
          <View style={styles.levelBadge}>
            <Text style={[styles.levelText, { color: current.color }]}>
              {current.name} {current.emoji}
            </Text>
          </View>

          {/* Progress to next level */}
          {next && (
            <View style={styles.progressSection}>
              <View style={styles.progressBar}>
                <View style={[styles.progressFill, { width: `${progressToNext * 100}%`, backgroundColor: next.color }]} />
              </View>
              <Text style={styles.progressText}>
                {next.min - points} pts to {next.name} {next.emoji}
              </Text>
            </View>
          )}
          {!next && (
            <Text style={styles.maxLevel}>You've reached the highest level! 🏆</Text>
          )}
        </Card>

        {/* All levels */}
        <Text style={styles.sectionTitle}>Levels</Text>
        <Card style={styles.levelsCard}>
          {LEVELS.map((level, i) => (
            <View key={level.name} style={[styles.levelRow, i < LEVELS.length - 1 && styles.levelRowBorder]}>
              <View style={styles.levelLeft}>
                <Text style={styles.levelEmoji}>{level.emoji}</Text>
                <View>
                  <Text style={[styles.levelName, index >= i && { fontFamily: 'DMSans_700Bold', color: level.color }]}>
                    {level.name}
                  </Text>
                  <Text style={styles.levelMin}>{level.min}+ points</Text>
                </View>
              </View>
              {index >= i ? (
                <Feather name="check-circle" size={18} color={level.color} />
              ) : (
                <Feather name="circle" size={18} color={Colors.text.tertiary} />
              )}
            </View>
          ))}
        </Card>

        {/* How to earn */}
        <Text style={styles.sectionTitle}>How to earn</Text>
        {EARN_METHODS.map((method) => (
          <Card key={method.title} style={styles.earnCard}>
            <View style={styles.earnRow}>
              <View style={styles.earnIcon}>
                <Feather name={method.icon as any} size={20} color={Colors.primary.default} />
              </View>
              <View style={styles.earnContent}>
                <Text style={styles.earnTitle}>{method.title}</Text>
                <Text style={styles.earnDesc}>{method.desc}</Text>
              </View>
              <View style={styles.earnPoints}>
                <Text style={styles.earnPts}>{method.points}</Text>
                <Text style={styles.earnPtsLabel}>pts</Text>
              </View>
            </View>
          </Card>
        ))}

        {/* Refer a friend */}
        <Text style={styles.sectionTitle}>Refer a friend</Text>
        <Card style={styles.referCard}>
          <Text style={styles.referDesc}>
            Share your code and you both earn <Text style={{ fontFamily: 'DMSans_700Bold', color: Colors.accent.green }}>50 points</Text> when they sign up!
          </Text>
          <View style={styles.codeRow}>
            <Text style={styles.codeText}>{referralCode}</Text>
            <Pressable onPress={handleShare} style={styles.shareBtn}>
              <Feather name="share-2" size={16} color="#FFF" />
              <Text style={styles.shareBtnText}>Share</Text>
            </Pressable>
          </View>
        </Card>

        {/* Redeem a code */}
        <Card style={styles.redeemCard}>
          <Text style={styles.redeemTitle}>Have a friend's code?</Text>
          <View style={styles.redeemRow}>
            <TextInput
              style={styles.redeemInput}
              placeholder="Enter code"
              value={redeemCode}
              onChangeText={setRedeemCode}
              autoCapitalize="characters"
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
  heroEmoji: { fontSize: 48, marginBottom: 8 },
  heroPoints: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 56, color: Colors.accent.amber },
  heroLabel: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: 'rgba(255,255,255,0.5)', marginTop: -4 },
  levelBadge: {
    marginTop: 12, paddingHorizontal: 16, paddingVertical: 6,
    backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 20,
  },
  levelText: { fontFamily: 'DMSans_700Bold', fontSize: 14 },
  progressSection: { width: '80%', marginTop: 20 },
  progressBar: { height: 6, backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 3, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 3 },
  progressText: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: 'rgba(255,255,255,0.5)', textAlign: 'center', marginTop: 8 },
  maxLevel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: 'rgba(255,255,255,0.6)', marginTop: 16 },

  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm, marginTop: Spacing.sm },

  levelsCard: { marginBottom: Spacing.md },
  levelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 12 },
  levelRowBorder: { borderBottomWidth: 1, borderBottomColor: Colors.surface.alt },
  levelLeft: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  levelEmoji: { fontSize: 24 },
  levelName: { fontFamily: 'DMSans_500Medium', fontSize: 15, color: Colors.text.primary },
  levelMin: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary },

  earnCard: { marginBottom: Spacing.xs },
  earnRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  earnIcon: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: Colors.accent.greenSoft,
    alignItems: 'center', justifyContent: 'center',
  },
  earnContent: { flex: 1 },
  earnTitle: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  earnDesc: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary, marginTop: 2 },
  earnPoints: { alignItems: 'center' },
  earnPts: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 18, color: Colors.accent.amber },
  earnPtsLabel: { fontFamily: 'DMSans_400Regular', fontSize: 10, color: Colors.text.tertiary },

  referCard: { marginBottom: Spacing.sm },
  referDesc: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, lineHeight: 20, marginBottom: 12 },
  codeRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  codeText: {
    flex: 1, fontFamily: 'JetBrainsMono_700Bold', fontSize: 20, color: Colors.primary.dark,
    backgroundColor: Colors.surface.alt, paddingVertical: 12, paddingHorizontal: 16,
    borderRadius: BorderRadius.md, textAlign: 'center', letterSpacing: 2,
  },
  shareBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: Colors.primary.default, paddingVertical: 12, paddingHorizontal: 20,
    borderRadius: BorderRadius.md,
  },
  shareBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: '#FFF' },

  redeemCard: { marginBottom: Spacing.lg },
  redeemTitle: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary, marginBottom: 8 },
  redeemRow: { flexDirection: 'row', gap: 8 },
  redeemInput: {
    flex: 1, fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 16,
    borderWidth: 1.5, borderColor: Colors.surface.border, borderRadius: BorderRadius.md,
    paddingHorizontal: 14, paddingVertical: 10, letterSpacing: 1,
  },
  redeemBtn: {
    backgroundColor: Colors.accent.green, paddingHorizontal: 20, paddingVertical: 12,
    borderRadius: BorderRadius.md, justifyContent: 'center',
  },
  redeemBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: '#FFF' },
});
