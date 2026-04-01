import React from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useAuthStore } from '../../stores/authStore';

const LEVELS = [
  { name: 'Starter', emoji: '🌱', min: 0, color: 'rgba(255,255,255,0.35)', perks: 'Welcome to SmartDocket!' },
  { name: 'Saver', emoji: '💚', min: 100, color: '#3CB371', perks: 'Price drop alerts unlocked' },
  { name: 'Smart Shopper', emoji: '⭐', min: 500, color: '#E8A020', perks: 'Priority deal notifications' },
  { name: 'Price Hunter', emoji: '🔥', min: 1000, color: '#EF4444', perks: 'Exclusive golden deals' },
  { name: 'Grocery Pro', emoji: '👑', min: 2500, color: '#8B5CF6', perks: 'Maximum rewards + badges' },
];

function getCurrentLevel(points: number) {
  for (let i = LEVELS.length - 1; i >= 0; i--) {
    if (points >= LEVELS[i].min) return { current: LEVELS[i], next: LEVELS[i + 1] || null, index: i };
  }
  return { current: LEVELS[0], next: LEVELS[1], index: 0 };
}

export default function LevelsScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const points = profile?.points || 0;
  const { current, next, index } = getCurrentLevel(points);
  const progressToNext = next
    ? Math.min((points - current.min) / (next.min - current.min), 1)
    : 1;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        <Pressable onPress={() => router.back()} style={styles.backBtn}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
          <Text style={styles.backText}>Level</Text>
        </Pressable>

        {/* Current level hero */}
        <Card variant="elevated" style={styles.heroCard}>
          <Text style={styles.heroEmoji}>{current.emoji}</Text>
          <Text style={[styles.heroLevel, { color: current.color }]}>{current.name}</Text>
          <Text style={styles.heroPoints}>{points} points</Text>

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
        <Text style={styles.sectionTitle}>All Levels</Text>
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
                  <Text style={styles.levelPerks}>{level.perks}</Text>
                </View>
              </View>
              {index >= i ? (
                <Feather name="check-circle" size={20} color={level.color} />
              ) : (
                <Feather name="circle" size={20} color={Colors.text.tertiary} />
              )}
            </View>
          ))}
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
  heroEmoji: { fontSize: 56 },
  heroLevel: { fontFamily: 'DMSans_700Bold', fontSize: 24, marginTop: 8 },
  heroPoints: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 16, color: 'rgba(255,255,255,0.6)', marginTop: 4 },
  progressSection: { width: '80%', marginTop: 20 },
  progressBar: { height: 8, backgroundColor: 'rgba(255,255,255,0.15)', borderRadius: 4, overflow: 'hidden' },
  progressFill: { height: '100%', borderRadius: 4 },
  progressText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.5)', textAlign: 'center', marginTop: 8 },
  maxLevel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: 'rgba(255,255,255,0.6)', marginTop: 16 },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  levelsCard: { marginBottom: Spacing.md },
  levelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 14 },
  levelRowBorder: { borderBottomWidth: 1, borderBottomColor: Colors.surface.alt },
  levelLeft: { flexDirection: 'row', alignItems: 'center', gap: 14, flex: 1 },
  levelEmoji: { fontSize: 28 },
  levelName: { fontFamily: 'DMSans_500Medium', fontSize: 16, color: Colors.text.primary },
  levelMin: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, marginTop: 1 },
  levelPerks: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary, marginTop: 1, fontStyle: 'italic' },
});
