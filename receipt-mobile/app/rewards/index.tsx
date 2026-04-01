import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';
import api from '../../services/api';

const EARN_METHODS = [
  { icon: 'camera', title: 'Scan a receipt', points: '10–75', desc: 'Bigger shop = more points (up to 75 for Pro!)' },
  { icon: 'maximize', title: 'Link barcodes', points: '30', desc: 'Scan product barcodes after a receipt (2x points!)' },
  { icon: 'plus-circle', title: 'Add a product', points: '10', desc: 'Add a new product by scanning its barcode' },
  { icon: 'users', title: 'Refer a friend', points: '50', desc: 'You earn when your friend goes Pro' },
  { icon: 'thumbs-up', title: 'Confirm a saving', points: '10', desc: 'Confirm SmartDocket helped you save' },
  { icon: 'gift', title: 'Monthly raffle', points: '', desc: '200 pts = 1 ticket to win a signed jersey!' },
];

interface ContributeData {
  points: number;
  level: { name: string; emoji: string; min: number };
  challenge: { title: string; description: string; progress: number; target: number; bonus_points: number; complete: boolean };
  leaderboard: { rank: number; name: string; points: number; is_me: boolean }[];
  my_rank: number | null;
}

export default function RewardsScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const points = profile?.points || 0;
  const [data, setData] = useState<ContributeData | null>(null);

  const fetchContribute = useCallback(async () => {
    try {
      const { data: res } = await api.get<ContributeData>('/users/me/contribute');
      setData(res);
    } catch {}
  }, []);

  useEffect(() => { fetchContribute(); }, [fetchContribute]);

  const displayPoints = data?.points ?? points;
  const level = data?.level;
  const challenge = data?.challenge;
  const leaderboard = data?.leaderboard ?? [];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
          <Text style={styles.backText}>Rewards</Text>
        </Pressable>

        {/* Points hero */}
        <Card variant="elevated" style={styles.heroCard}>
          <Feather name="star" size={36} color={Colors.accent.amber} />
          <Text style={styles.heroPoints}>{displayPoints}</Text>
          <Text style={styles.heroLabel}>points earned</Text>
          {level && (
            <View style={styles.levelPill}>
              <Text style={styles.levelText}>{level.emoji} {level.name}</Text>
            </View>
          )}
        </Card>

        {/* Weekly Challenge */}
        {challenge && (
          <>
            <Text style={styles.sectionTitle}>Weekly Challenge</Text>
            <Card style={styles.challengeCard}>
              <View style={styles.challengeHeader}>
                <View style={{ flex: 1 }}>
                  <Text style={styles.challengeTitle}>{challenge.title}</Text>
                  <Text style={styles.challengeDesc}>{challenge.description}</Text>
                </View>
                <View style={styles.challengeRight}>
                  <Text style={styles.challengeCount}>{challenge.progress}/{challenge.target}</Text>
                  <Text style={styles.challengeBonus}>+{challenge.bonus_points} bonus</Text>
                </View>
              </View>
              <View style={styles.progressTrack}>
                <View style={[styles.progressFill, { width: `${Math.min(100, (challenge.progress / challenge.target) * 100)}%` }]} />
              </View>
              {challenge.complete && <Badge text="Challenge complete!" variant="success" size="sm" />}
            </Card>
          </>
        )}

        {/* How to earn */}
        <Text style={styles.sectionTitle}>Earn points</Text>
        {EARN_METHODS.map((method) => (
          <Card key={method.title} style={styles.earnCard}>
            <View style={styles.earnRow}>
              <View style={styles.earnIcon}>
                <Feather name={method.icon as any} size={20} color={Colors.accent.green} />
              </View>
              <View style={styles.earnContent}>
                <Text style={styles.earnTitle}>{method.title}</Text>
                <Text style={styles.earnDesc}>{method.desc}</Text>
              </View>
              <View style={styles.earnPoints}>
                <Text style={styles.earnPts}>+{method.points}</Text>
              </View>
            </View>
          </Card>
        ))}

        {/* Leaderboard */}
        {leaderboard.length > 0 && (
          <>
            <Text style={styles.sectionTitle}>Top Contributors</Text>
            <Card style={styles.leaderCard}>
              {leaderboard.map((entry, i) => (
                <View key={entry.rank} style={[styles.leaderRow, entry.is_me && styles.leaderRowMe, i < leaderboard.length - 1 && styles.leaderBorder]}>
                  <Text style={[styles.leaderRank, entry.rank === 1 && { color: 'rgba(212,168,67,0.30)' }, entry.rank === 2 && { color: 'rgba(255,255,255,0.35)' }, entry.rank === 3 && { color: '#CD7F32' }]}>{entry.rank}</Text>
                  <Text style={[styles.leaderName, entry.is_me && styles.leaderNameMe]}>{entry.is_me ? 'You' : entry.name}</Text>
                  <Text style={[styles.leaderPts, entry.is_me && styles.leaderPtsMe]}>{entry.points} pts</Text>
                </View>
              ))}
            </Card>
          </>
        )}

        {/* Prizes */}
        <Text style={styles.sectionTitle}>Prizes & Rewards</Text>
        <Card style={styles.prizesCard}>
          <Feather name="gift" size={32} color={Colors.text.tertiary} />
          <Text style={styles.prizeTitle}>Coming soon!</Text>
          <Text style={styles.prizeDesc}>
            We're preparing exciting prizes you can redeem with your points. Keep scanning and collecting!
          </Text>
        </Card>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  scroll: { padding: Spacing.md, paddingBottom: 40 },
  backBtn: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: Spacing.lg, paddingVertical: 4 },
  backText: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: '#FFFFFF' },
  heroCard: {
    alignItems: 'center', paddingVertical: 32,
    backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 24, marginBottom: Spacing.lg,
  },
  heroPoints: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 56, color: Colors.accent.amber, marginTop: 8 },
  heroLabel: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: 'rgba(255,255,255,0.5)', marginTop: -4 },
  levelPill: {
    backgroundColor: 'rgba(255,255,255,0.1)', borderRadius: 20,
    paddingHorizontal: 14, paddingVertical: 4, marginTop: 8,
  },
  levelText: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: 'rgba(255,255,255,0.7)' },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm, marginTop: Spacing.sm },
  challengeCard: { marginBottom: Spacing.sm, backgroundColor: 'rgba(80,200,120,0.20)', padding: Spacing.md },
  challengeHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing.sm },
  challengeTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: '#FFF' },
  challengeDesc: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  challengeRight: { alignItems: 'flex-end' },
  challengeCount: { fontFamily: 'DMSans_700Bold', fontSize: 22, color: '#FFF' },
  challengeBonus: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: 'rgba(255,255,255,0.6)' },
  progressTrack: { height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.2)', marginBottom: Spacing.xs },
  progressFill: { height: 6, borderRadius: 3, backgroundColor: 'rgba(212,168,67,0.30)' },
  earnCard: { marginBottom: Spacing.xs },
  earnRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  earnIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.accent.greenSoft, alignItems: 'center', justifyContent: 'center' },
  earnContent: { flex: 1 },
  earnTitle: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  earnDesc: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary, marginTop: 2 },
  earnPoints: { alignItems: 'center' },
  earnPts: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 16, color: Colors.accent.amber },
  leaderCard: { marginBottom: Spacing.sm, paddingVertical: 0, paddingHorizontal: 0 },
  leaderRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 10, paddingHorizontal: Spacing.md },
  leaderRowMe: { backgroundColor: 'rgba(80,200,120,0.12)' },
  leaderBorder: { borderBottomWidth: 1, borderBottomColor: Colors.surface.border },
  leaderRank: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: Colors.text.tertiary, width: 24 },
  leaderName: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary, flex: 1 },
  leaderNameMe: { color: Colors.accent.green },
  leaderPts: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: Colors.text.secondary },
  leaderPtsMe: { color: Colors.accent.green },
  prizesCard: { alignItems: 'center', paddingVertical: 32 },
  prizeTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginTop: 12 },
  prizeDesc: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center', lineHeight: 20, marginTop: 8, paddingHorizontal: 16 },
});
