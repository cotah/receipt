import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';

import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../constants/typography';
import api from '../services/api';

interface Challenge {
  title: string;
  description: string;
  progress: number;
  target: number;
  bonus_points: number;
  complete: boolean;
}

interface PointAction {
  action: string;
  points: number;
  icon: string;
  description: string;
}

interface LeaderboardEntry {
  rank: number;
  name: string;
  points: number;
  is_me: boolean;
}

interface Level {
  name: string;
  emoji: string;
  min: number;
}

interface ContributeData {
  points: number;
  level: Level;
  challenge: Challenge;
  actions: PointAction[];
  leaderboard: LeaderboardEntry[];
  my_rank: number | null;
}

export default function ContributeScreen() {
  const [data, setData] = useState<ContributeData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    try {
      const { data: res } = await api.get<ContributeData>('/users/me/contribute');
      setData(res);
    } catch {
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { fetchData(); }, [fetchData]);

  const iconMap: Record<string, keyof typeof Feather.glyphMap> = {
    'camera': 'camera',
    'check-circle': 'check-circle',
    'tag': 'tag',
    'users': 'users',
  };

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn}>
            <Feather name="arrow-left" size={22} color={Colors.text.primary} />
          </Pressable>
          <Text style={styles.title}>Contribute</Text>
          {data && (
            <View style={styles.pointsPill}>
              <Feather name="star" size={14} color="#F0D68A" />
              <Text style={styles.pointsPillText}>{data.points} pts</Text>
            </View>
          )}
        </View>

        {isLoading && (
          <View style={styles.loadingRow}>
            <ActivityIndicator size="small" color={Colors.primary.default} />
          </View>
        )}

        {data && !isLoading && (
          <>
            {/* Weekly Challenge */}
            <Card style={styles.challengeCard}>
              <View style={styles.challengeHeader}>
                <View>
                  <Text style={styles.challengeLabel}>WEEKLY CHALLENGE</Text>
                  <Text style={styles.challengeTitle}>{data.challenge.title}</Text>
                  <Text style={styles.challengeDesc}>{data.challenge.description}</Text>
                </View>
                <View style={styles.challengeProgress}>
                  <Text style={styles.challengeCount}>
                    {data.challenge.progress}/{data.challenge.target}
                  </Text>
                  <Text style={styles.challengeBonus}>+{data.challenge.bonus_points} bonus</Text>
                </View>
              </View>

              {/* Progress bar */}
              <View style={styles.progressTrack}>
                <View
                  style={[
                    styles.progressFill,
                    { width: `${Math.min(100, (data.challenge.progress / data.challenge.target) * 100)}%` },
                  ]}
                />
              </View>

              {data.challenge.complete && (
                <Badge text="Challenge complete! Bonus claimed" variant="success" size="md" />
              )}
            </Card>

            {/* Earn Points */}
            <Text style={styles.sectionTitle}>EARN POINTS</Text>

            {data.actions.map((action) => (
              <Card key={action.action} style={styles.actionCard}>
                <View style={styles.actionRow}>
                  <View style={styles.actionIcon}>
                    <Feather
                      name={iconMap[action.icon] || 'award'}
                      size={20}
                      color={Colors.primary.default}
                    />
                  </View>
                  <View style={styles.actionInfo}>
                    <Text style={styles.actionName}>{action.action}</Text>
                    <Text style={styles.actionDesc}>{action.description}</Text>
                  </View>
                  <Text style={styles.actionPoints}>+{action.points}</Text>
                </View>
              </Card>
            ))}

            {/* Leaderboard */}
            {data.leaderboard.length > 0 && (
              <>
                <Text style={styles.sectionTitle}>TOP CONTRIBUTORS</Text>
                <Card style={styles.leaderCard}>
                  {data.leaderboard.map((entry) => (
                    <View
                      key={entry.rank}
                      style={[
                        styles.leaderRow,
                        entry.is_me && styles.leaderRowMe,
                        entry.rank < data.leaderboard.length && styles.leaderRowBorder,
                      ]}
                    >
                      <Text style={[
                        styles.leaderRank,
                        entry.rank === 1 && { color: '#F0D68A' },
                        entry.rank === 2 && { color: 'rgba(255,255,255,0.35)' },
                        entry.rank === 3 && { color: '#CD7F32' },
                      ]}>
                        {entry.rank}
                      </Text>
                      <Text style={[styles.leaderName, entry.is_me && styles.leaderNameMe]}>
                        {entry.is_me ? 'You' : entry.name}
                      </Text>
                      <Text style={[styles.leaderPoints, entry.is_me && styles.leaderPointsMe]}>
                        {entry.points} pts
                      </Text>
                    </View>
                  ))}
                </Card>
              </>
            )}

            {/* Level */}
            <Card style={styles.levelCard}>
              <Text style={styles.levelEmoji}>{data.level.emoji}</Text>
              <Text style={styles.levelName}>{data.level.name}</Text>
              <Text style={styles.levelPoints}>{data.points} points</Text>
            </Card>
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.surface.background },
  scroll: { flex: 1 },
  content: { padding: Spacing.lg },
  header: {
    flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.lg,
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: Colors.surface.alt,
    alignItems: 'center', justifyContent: 'center',
    marginRight: Spacing.sm,
  },
  title: {
    fontSize: 22, fontFamily: Fonts.display,
    color: Colors.text.primary, flex: 1,
  },
  pointsPill: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(232,160,32,0.12)',
    borderRadius: 20, paddingHorizontal: 12, paddingVertical: 5,
  },
  pointsPillText: {
    fontFamily: Fonts.bodyBold, fontSize: 14, color: '#F0D68A',
  },
  loadingRow: {
    paddingVertical: Spacing.xl * 2, alignItems: 'center',
  },
  challengeCard: {
    backgroundColor: Colors.primary.default, padding: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  challengeHeader: {
    flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing.md,
  },
  challengeLabel: {
    fontFamily: Fonts.bodyBold, fontSize: 11, letterSpacing: 0.5,
    color: 'rgba(255,255,255,0.6)',
  },
  challengeTitle: {
    fontFamily: Fonts.bodyBold, fontSize: 18, color: '#FFF', marginTop: 4,
  },
  challengeDesc: {
    fontFamily: Fonts.body, fontSize: 13, color: 'rgba(255,255,255,0.8)', marginTop: 2,
  },
  challengeProgress: { alignItems: 'flex-end' },
  challengeCount: {
    fontFamily: Fonts.bodyBold, fontSize: 24, color: '#FFF',
  },
  challengeBonus: {
    fontFamily: Fonts.body, fontSize: 11, color: 'rgba(255,255,255,0.6)',
  },
  progressTrack: {
    height: 6, borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.2)',
    marginBottom: Spacing.sm,
  },
  progressFill: {
    height: 6, borderRadius: 3, backgroundColor: '#F0D68A',
  },
  sectionTitle: {
    fontFamily: Fonts.bodyBold, fontSize: 12, color: Colors.text.secondary,
    letterSpacing: 0.5, marginBottom: Spacing.sm,
  },
  actionCard: { marginBottom: Spacing.xs },
  actionRow: {
    flexDirection: 'row', alignItems: 'center', gap: Spacing.sm,
  },
  actionIcon: {
    width: 42, height: 42, borderRadius: 12,
    backgroundColor: Colors.primary.pale,
    alignItems: 'center', justifyContent: 'center',
  },
  actionInfo: { flex: 1 },
  actionName: {
    fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.text.primary,
  },
  actionDesc: {
    fontFamily: Fonts.body, fontSize: 12, color: Colors.text.secondary,
  },
  actionPoints: {
    fontFamily: Fonts.bodyBold, fontSize: 16, color: '#F0D68A',
  },
  leaderCard: { marginBottom: Spacing.lg, paddingVertical: 0, paddingHorizontal: 0 },
  leaderRow: {
    flexDirection: 'row', alignItems: 'center',
    paddingVertical: 10, paddingHorizontal: Spacing.md,
  },
  leaderRowMe: { backgroundColor: Colors.primary.pale },
  leaderRowBorder: { borderBottomWidth: 1, borderBottomColor: Colors.surface.border },
  leaderRank: {
    fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.text.tertiary,
    width: 24,
  },
  leaderName: {
    fontFamily: Fonts.bodySemiBold, fontSize: 14, color: Colors.text.primary, flex: 1,
  },
  leaderNameMe: { color: Colors.primary.default, fontFamily: Fonts.bodyBold },
  leaderPoints: {
    fontFamily: Fonts.bodySemiBold, fontSize: 13, color: Colors.text.secondary,
  },
  leaderPointsMe: { color: Colors.primary.default },
  levelCard: {
    alignItems: 'center', padding: Spacing.lg,
  },
  levelEmoji: { fontSize: 32, marginBottom: 4 },
  levelName: {
    fontFamily: Fonts.bodyBold, fontSize: 16, color: Colors.text.primary,
  },
  levelPoints: {
    fontFamily: Fonts.body, fontSize: 13, color: Colors.text.secondary,
  },
});
