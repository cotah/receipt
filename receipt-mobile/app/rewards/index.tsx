import React from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';

const EARN_METHODS = [
  { icon: 'camera', title: 'Scan a receipt', points: '10-25', desc: 'Free: 10 pts · Pro: 25 pts' },
  { icon: 'users', title: 'Refer a friend', points: '50', desc: 'Both you and your friend earn 50' },
  { icon: 'check-circle', title: 'Confirm a saving', points: '10', desc: 'Confirm SmartDocket helped you save' },
  { icon: 'tag', title: 'Report a price', points: 'Soon', desc: 'Photo shelf labels for bonus points' },
];

export default function RewardsScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const points = profile?.points || 0;

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
          <Text style={styles.heroPoints}>{points}</Text>
          <Text style={styles.heroLabel}>points earned</Text>
        </Card>

        {/* How to earn */}
        <Text style={styles.sectionTitle}>How to earn points</Text>
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

        {/* Prizes */}
        <Text style={styles.sectionTitle}>Prizes & Rewards</Text>
        <Card style={styles.prizesCard}>
          <Feather name="gift" size={32} color={Colors.text.tertiary} />
          <Text style={styles.prizeTitle}>Coming soon!</Text>
          <Text style={styles.prizeDesc}>
            We're preparing exciting prizes you can redeem with your points. Stay tuned — scan receipts and collect points now!
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
  backText: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: Colors.primary.dark },
  heroCard: {
    alignItems: 'center', paddingVertical: 32,
    backgroundColor: Colors.primary.dark, borderRadius: 24, marginBottom: Spacing.lg,
  },
  heroPoints: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 56, color: Colors.accent.amber, marginTop: 8 },
  heroLabel: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: 'rgba(255,255,255,0.5)', marginTop: -4 },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm, marginTop: Spacing.sm },
  earnCard: { marginBottom: Spacing.xs },
  earnRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  earnIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: Colors.accent.greenSoft, alignItems: 'center', justifyContent: 'center' },
  earnContent: { flex: 1 },
  earnTitle: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  earnDesc: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary, marginTop: 2 },
  earnPoints: { alignItems: 'center' },
  earnPts: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 18, color: Colors.accent.amber },
  earnPtsLabel: { fontFamily: 'DMSans_400Regular', fontSize: 10, color: Colors.text.tertiary },
  prizesCard: { alignItems: 'center', paddingVertical: 32 },
  prizeTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginTop: 12 },
  prizeDesc: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center', lineHeight: 20, marginTop: 8, paddingHorizontal: 16 },
});
