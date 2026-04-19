import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator, Image, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import * as Haptics from 'expo-haptics';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';
import api from '../../services/api';

const PRIZE_IMAGES: Record<number, any> = {
  1: require('../../assets/raffle/rooney-jersey.jpeg'),
  2: require('../../assets/raffle/boots-card.jpeg'),
  3: require('../../assets/raffle/one4all-card.jpeg'),
};

const EARN_METHODS = [
  { icon: 'camera', title: 'Scan a receipt', points: '10–75', desc: 'Bigger shop = more points (up to 75 for Pro!)' },
  { icon: 'maximize', title: 'Link barcodes', points: '30', desc: 'Scan product barcodes after a receipt (2x points!)' },
  { icon: 'plus-circle', title: 'Add a product', points: '10', desc: 'Add a new product by scanning its barcode' },
  { icon: 'users', title: 'Refer a friend', points: '50', desc: 'You earn when your friend goes Pro' },
  { icon: 'thumbs-up', title: 'Confirm a saving', points: '10', desc: 'Confirm SmartDocket helped you save' },
  { icon: 'gift', title: 'Monthly Draw', points: '', desc: 'Enter to win: Jersey (1500 pts), Boots €30 (1000 pts), One4All €30 (800 pts)' },
];

interface ContributeData {
  points: number;
  level: { name: string; emoji: string; min: number };
  challenge: { title: string; description: string; progress: number; target: number; bonus_points: number; complete: boolean };
  leaderboard: { rank: number; name: string; points: number; is_me: boolean }[];
  my_rank: number | null;
}

interface Prize {
  tier: number;
  name: string;
  points: number;
  emoji: string;
  description: string;
  my_tickets: number;
  can_afford: boolean;
}

interface PrizesData {
  month: string;
  month_label: string;
  prizes: Prize[];
  user_points: number;
  next_draw: string;
}

interface Ticket {
  id: string;
  ticket_number: string;
  prize_tier: number;
  prize_name: string;
  points_spent: number;
  month: string;
  created_at: string;
}

interface MyTicketsData {
  month: string;
  tickets: Ticket[];
  total_tickets: number;
}

export default function RewardsScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const setProfile = useAuthStore((s) => s.setProfile);
  const points = profile?.points || 0;
  const [data, setData] = useState<ContributeData | null>(null);
  const [prizesData, setPrizesData] = useState<PrizesData | null>(null);
  const [ticketsData, setTicketsData] = useState<MyTicketsData | null>(null);
  const [enteringTier, setEnteringTier] = useState<number | null>(null);

  const fetchContribute = useCallback(async () => {
    try {
      const { data: res } = await api.get<ContributeData>('/users/me/contribute');
      setData(res);
    } catch {}
  }, []);

  const fetchPrizes = useCallback(async () => {
    try {
      const { data: res } = await api.get<PrizesData>('/raffle/prizes');
      setPrizesData(res);
    } catch {}
  }, []);

  const fetchTickets = useCallback(async () => {
    try {
      const { data: res } = await api.get<MyTicketsData>('/raffle/my-tickets');
      setTicketsData(res);
    } catch {}
  }, []);

  useEffect(() => {
    fetchContribute();
    fetchPrizes();
    fetchTickets();
  }, [fetchContribute, fetchPrizes, fetchTickets]);

  const handleEnterDraw = useCallback((prize: Prize) => {
    Alert.alert(
      `Enter the ${prize.emoji} draw?`,
      `Spend ${prize.points} points for one ticket to win:\n\n${prize.name}`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Enter Draw',
          style: 'default',
          onPress: async () => {
            setEnteringTier(prize.tier);
            try {
              const { data: res } = await api.post('/raffle/enter', { prize_tier: prize.tier });
              await Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
              Alert.alert(
                '🎉 You are in the draw!',
                `Your ticket number: ${res.ticket_number}\n\nGood luck!`,
              );
              // Refresh everything in parallel
              await Promise.all([fetchPrizes(), fetchTickets(), fetchContribute()]);
              try {
                const { data: me } = await api.get('/users/me');
                setProfile(me);
              } catch {}
            } catch (e: any) {
              const msg = e?.response?.data?.detail || 'Could not enter the draw. Please try again.';
              Alert.alert('Oops', msg);
            } finally {
              setEnteringTier(null);
            }
          },
        },
      ],
    );
  }, [fetchPrizes, fetchTickets, fetchContribute, setProfile]);

  const displayPoints = data?.points ?? points;
  const level = data?.level;
  const challenge = data?.challenge;
  const leaderboard = data?.leaderboard ?? [];
  const prizes = prizesData?.prizes ?? [];
  const tickets = ticketsData?.tickets ?? [];

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
          <Text style={styles.backText}>Rewards</Text>
        </Pressable>

        {/* Points hero */}
        <Card variant="rewardHero" style={styles.heroCard}>
          <View style={styles.starHalo}>
            <Feather name="star" size={44} color={Colors.accent.amber} />
          </View>
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
            <Card variant="glass" style={styles.challengeCard}>
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
                <Feather name={method.icon as any} size={20} color={'#7DDFAA'} />
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
                  <Text style={[styles.leaderRank, entry.rank === 1 && { color: '#F0D68A' }, entry.rank === 2 && { color: 'rgba(255,255,255,0.45)' }, entry.rank === 3 && { color: '#F0997B' }]}>{entry.rank}</Text>
                  <Text style={[styles.leaderName, entry.is_me && styles.leaderNameMe]}>{entry.is_me ? 'You' : entry.name}</Text>
                  <Text style={[styles.leaderPts, entry.is_me && styles.leaderPtsMe]}>{entry.points} pts</Text>
                </View>
              ))}
            </Card>
          </>
        )}

        {/* Monthly Draw */}
        <View style={styles.drawHeader}>
          <Text style={styles.sectionTitle}>Monthly Draw</Text>
          {prizesData?.next_draw && (
            <Text style={styles.drawDate}>Next draw: {prizesData.next_draw}</Text>
          )}
        </View>

        {!prizesData && (
          <View style={styles.loadingRow}>
            <ActivityIndicator size="small" color={Colors.accent.amber} />
          </View>
        )}

        {prizes.map((prize) => {
          const isEntering = enteringTier === prize.tier;
          const disabled = !prize.can_afford || isEntering;
          const deficit = Math.max(0, prize.points - (prizesData?.user_points ?? 0));
          return (
            <Card key={prize.tier} variant="rewardOffer" style={styles.prizeCard}>
              <Image source={PRIZE_IMAGES[prize.tier]} style={styles.prizeImage} resizeMode="cover" />
              <View style={styles.prizeBody}>
                <View style={styles.prizeTitleRow}>
                  <Text style={styles.prizeEmoji}>{prize.emoji}</Text>
                  <Text style={styles.prizeName} numberOfLines={2}>{prize.name}</Text>
                </View>
                <Text style={styles.prizeDescText}>{prize.description}</Text>

                <View style={styles.prizeMetaRow}>
                  <Text style={styles.prizeCost}>{prize.points} pts</Text>
                  {prize.my_tickets > 0 && (
                    <View style={styles.prizeTicketPill}>
                      <Feather name="check" size={11} color={Colors.accent.amber} />
                      <Text style={styles.prizeTicketText}>
                        You have {prize.my_tickets} {prize.my_tickets === 1 ? 'ticket' : 'tickets'}
                      </Text>
                    </View>
                  )}
                </View>

                <Pressable
                  onPress={() => handleEnterDraw(prize)}
                  disabled={disabled}
                  style={[styles.enterBtn, disabled && styles.enterBtnDisabled]}
                >
                  {isEntering ? (
                    <ActivityIndicator size="small" color="#0d2818" />
                  ) : (
                    <Text style={[styles.enterBtnText, disabled && styles.enterBtnTextDisabled]}>
                      {prize.can_afford ? 'Enter Draw' : `Need ${deficit} more pts`}
                    </Text>
                  )}
                </Pressable>
              </View>
            </Card>
          );
        })}

        {/* My Tickets */}
        <Text style={styles.sectionTitle}>My Tickets</Text>
        {!ticketsData && (
          <View style={styles.loadingRow}>
            <ActivityIndicator size="small" color={Colors.accent.amber} />
          </View>
        )}

        {ticketsData && tickets.length === 0 && (
          <Card style={styles.ticketsEmpty}>
            <Feather name="hash" size={28} color={Colors.text.tertiary} />
            <Text style={styles.ticketsEmptyTitle}>No tickets yet</Text>
            <Text style={styles.ticketsEmptyDesc}>
              Enter a draw above to get your first ticket this month.
            </Text>
          </Card>
        )}

        {tickets.length > 0 && (
          <Card style={styles.ticketsCard}>
            {tickets.map((ticket, i) => (
              <View
                key={ticket.id}
                style={[styles.ticketRow, i < tickets.length - 1 && styles.ticketRowBorder]}
              >
                <View style={styles.ticketLeft}>
                  <Text style={styles.ticketNumber}>{ticket.ticket_number}</Text>
                  <Text style={styles.ticketPrize} numberOfLines={1}>{ticket.prize_name}</Text>
                </View>
                <Text style={styles.ticketDate}>
                  {new Date(ticket.created_at).toLocaleDateString('en-IE', { day: 'numeric', month: 'short' })}
                </Text>
              </View>
            ))}
          </Card>
        )}
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
    borderRadius: 24, marginBottom: Spacing.lg,
  },
  starHalo: {
    width: 88, height: 88, borderRadius: 44,
    backgroundColor: 'rgba(240,214,138,0.20)',
    alignItems: 'center', justifyContent: 'center',
    shadowColor: '#F0D68A',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.35,
    shadowRadius: 18,
  },
  heroPoints: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 56, color: Colors.accent.amber, marginTop: 8 },
  heroLabel: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: 'rgba(255,255,255,0.5)', marginTop: -4 },
  levelPill: {
    backgroundColor: 'rgba(240,214,138,0.15)',
    borderWidth: 0.5,
    borderColor: 'rgba(240,214,138,0.30)',
    borderRadius: 20,
    paddingHorizontal: 14, paddingVertical: 4, marginTop: 10,
  },
  levelText: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: 'rgba(255,255,255,0.85)' },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm, marginTop: Spacing.sm },
  challengeCard: {
    marginBottom: Spacing.sm,
    padding: Spacing.md,
    borderTopWidth: StyleSheet.hairlineWidth,
    borderTopColor: 'rgba(240,214,138,0.20)',
  },
  challengeHeader: { flexDirection: 'row', justifyContent: 'space-between', marginBottom: Spacing.sm },
  challengeTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: '#FFF' },
  challengeDesc: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.8)', marginTop: 2 },
  challengeRight: { alignItems: 'flex-end' },
  challengeCount: { fontFamily: 'DMSans_700Bold', fontSize: 22, color: '#FFF' },
  challengeBonus: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: 'rgba(255,255,255,0.6)' },
  progressTrack: { height: 6, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.2)', marginBottom: Spacing.xs },
  progressFill: { height: 6, borderRadius: 3, backgroundColor: '#F0D68A' },
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
  leaderRowMe: { backgroundColor: Colors.primary.pale },
  leaderBorder: { borderBottomWidth: 1, borderBottomColor: Colors.surface.border },
  leaderRank: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: Colors.text.tertiary, width: 24 },
  leaderName: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary, flex: 1 },
  leaderNameMe: { color: '#7DDFAA' },
  leaderPts: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: Colors.text.secondary },
  leaderPtsMe: { color: '#7DDFAA' },
  loadingRow: { paddingVertical: Spacing.md, alignItems: 'center' },

  // Monthly Draw
  drawHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-end', marginTop: Spacing.sm, marginBottom: Spacing.sm },
  drawDate: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: 'rgba(240,214,138,0.85)', marginBottom: 2 },

  prizeCard: {
    marginBottom: Spacing.md,
    padding: 0,
    overflow: 'hidden',
  },
  prizeImage: {
    width: '100%',
    height: 180,
    backgroundColor: 'rgba(255,255,255,0.04)',
  },
  prizeBody: { padding: Spacing.md, gap: 8 },
  prizeTitleRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  prizeEmoji: { fontSize: 22 },
  prizeName: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: Colors.text.primary, flex: 1 },
  prizeDescText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, lineHeight: 18 },
  prizeMetaRow: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 4, flexWrap: 'wrap' },
  prizeCost: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 20, color: Colors.accent.amber },
  prizeTicketPill: {
    flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: 'rgba(240,214,138,0.15)',
    borderWidth: 0.5, borderColor: 'rgba(240,214,138,0.30)',
    borderRadius: 20, paddingHorizontal: 10, paddingVertical: 3,
  },
  prizeTicketText: { fontFamily: 'DMSans_600SemiBold', fontSize: 11, color: Colors.accent.amber },
  enterBtn: {
    marginTop: 6,
    backgroundColor: Colors.accent.amber,
    borderRadius: BorderRadius.md,
    paddingVertical: 13,
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#F0D68A',
    shadowOffset: { width: 0, height: 0 },
    shadowOpacity: 0.4,
    shadowRadius: 10,
  },
  enterBtnDisabled: {
    backgroundColor: 'rgba(240,214,138,0.15)',
    shadowOpacity: 0,
  },
  enterBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: '#0d2818' },
  enterBtnTextDisabled: { color: 'rgba(240,214,138,0.75)' },

  // My Tickets
  ticketsEmpty: { alignItems: 'center', paddingVertical: 28, marginBottom: Spacing.md },
  ticketsEmptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: Colors.text.primary, marginTop: 10 },
  ticketsEmptyDesc: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, textAlign: 'center', marginTop: 6, paddingHorizontal: 24 },
  ticketsCard: { marginBottom: Spacing.md, paddingVertical: 0, paddingHorizontal: 0 },
  ticketRow: { flexDirection: 'row', alignItems: 'center', paddingVertical: 12, paddingHorizontal: Spacing.md, gap: Spacing.sm },
  ticketRowBorder: { borderBottomWidth: 0.5, borderBottomColor: 'rgba(255,255,255,0.08)' },
  ticketLeft: { flex: 1, gap: 2 },
  ticketNumber: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 15, color: Colors.accent.amber, letterSpacing: 0.5 },
  ticketPrize: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.text.secondary },
  ticketDate: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.text.tertiary },
});
