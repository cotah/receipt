import React, { useEffect } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { GestureDetector } from 'react-native-gesture-handler';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import ReceiptCard from '../../components/receipts/ReceiptCard';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { useTabSwipe } from '../../hooks/useTabSwipe';
import { formatCurrency, formatCurrencyChange } from '../../utils/formatCurrency';
import { useAuthStore } from '../../stores/authStore';
import { useReceipts } from '../../hooks/useReceipts';
import { useProducts } from '../../hooks/useProducts';

export default function HomeScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const { receipts, fetchReceipts } = useReceipts();
  const { runningLow, fetchRunningLow } = useProducts();

  useEffect(() => {
    fetchReceipts(1);
    fetchRunningLow();
  }, []);

  const hour = new Date().getHours();
  const greeting = hour < 12 ? 'Good morning' : hour < 18 ? 'Good afternoon' : 'Good evening';
  const name = profile?.full_name?.split(' ')[0] ?? '';

  // Calculate month total from receipts
  const now = new Date();
  const monthReceipts = receipts.filter((r) => {
    const d = new Date(r.purchased_at);
    return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
  });
  const monthTotal = monthReceipts.reduce((s, r) => s + r.total_amount, 0);
  const monthDiscounts = monthReceipts.reduce((s, r) => s + (r.discount_total ?? 0), 0);

  const swipe = useTabSwipe(0);

  return (
    <GestureDetector gesture={swipe}>
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {/* Header */}
        <View style={styles.headerRow}>
          <Text style={styles.greeting}>{greeting}, {name}</Text>
          <Pressable onPress={() => router.push('/(tabs)/profile')} hitSlop={12}>
            <Feather name="user" size={22} color={Colors.text.secondary} />
          </Pressable>
        </View>

        {/* Main card */}
        <Card variant="elevated" style={styles.mainCard}>
          <Text style={styles.mainLabel}>Spent this month</Text>
          <Text style={styles.mainAmount}>{formatCurrency(monthTotal)}</Text>
          <Text style={styles.mainSub}>{monthReceipts.length} shops</Text>
        </Card>

        {/* Stats row */}
        <View style={styles.statsRow}>
          <Card style={styles.statCard}>
            <Text style={styles.statValue}>{monthReceipts.length}</Text>
            <Text style={styles.statLabel}>Shops</Text>
          </Card>
          <Card style={styles.statCard}>
            <Text style={styles.statValue}>{formatCurrency(monthDiscounts)}</Text>
            <Text style={styles.statLabel}>Discounts</Text>
          </Card>
          <Card style={styles.statCard}>
            <Text style={[styles.statValue, { color: Colors.text.tertiary }]}>{formatCurrency(0)}</Text>
            <Text style={styles.statLabel}>Saved with SD</Text>
            <Text style={styles.comingSoon}>Track your savings</Text>
          </Card>
        </View>

        {/* Running Low */}
        {runningLow.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Running Low</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: Spacing.sm }}>
              {runningLow.slice(0, 5).map((item) => (
                <Card key={item.product_name} style={styles.lowCard}>
                  <Text style={styles.lowName}>{item.product_name}</Text>
                  <Badge text={`${item.overdue_by_days}d overdue`} variant={item.urgency === 'high' ? 'danger' : 'warning'} size="sm" />
                  {item.best_current_price && (
                    <Text style={styles.lowPrice}>{formatCurrency(item.best_current_price.price)} at {item.best_current_price.store}</Text>
                  )}
                </Card>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Recent Receipts */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Recent Receipts</Text>
          {receipts.slice(0, 3).map((r) => (
            <ReceiptCard
              key={r.id}
              {...r}
              onPress={() => router.push(`/receipt/${r.id}`)}
            />
          ))}
        </View>
      </ScrollView>

    </SafeAreaView>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  scroll: { padding: Spacing.md, paddingBottom: 100 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.md },
  greeting: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: Colors.primary.dark },
  mainCard: { marginBottom: Spacing.md, alignItems: 'center', paddingVertical: Spacing.lg },
  mainLabel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.text.secondary },
  mainAmount: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 40, color: Colors.accent.amber, marginVertical: 4 },
  mainSub: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.tertiary },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.lg },
  statCard: { flex: 1, alignItems: 'center', paddingVertical: Spacing.md },
  statValue: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 20, color: Colors.text.primary },
  statLabel: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, marginTop: 2 },
  comingSoon: { fontFamily: 'DMSans_400Regular', fontSize: 9, color: Colors.text.tertiary, marginTop: 1 },
  section: { marginBottom: Spacing.lg },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  lowCard: { width: 140, padding: Spacing.sm, gap: 4 },
  lowName: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary },
  lowPrice: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 11, color: Colors.accent.green },
});
