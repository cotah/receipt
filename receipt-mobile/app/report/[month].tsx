import React, { useEffect } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import MonthSummary from '../../components/reports/MonthSummary';
import SpendingChart from '../../components/reports/SpendingChart';
import StoreBreakdown from '../../components/reports/StoreBreakdown';
import Card from '../../components/ui/Card';
import Skeleton from '../../components/ui/Skeleton';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';
import { useReport } from '../../hooks/useReport';

export default function MonthlyReportScreen() {
  const { month } = useLocalSearchParams<{ month: string }>();
  const router = useRouter();
  const { report, isLoading, fetchMonthlyReport } = useReport();

  useEffect(() => {
    fetchMonthlyReport(month);
  }, [month]);

  if (isLoading || !report) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.skeletons}>
          <Skeleton width="60%" height={32} />
          <Skeleton width="100%" height={200} style={{ marginTop: 16 }} />
          <Skeleton width="100%" height={150} style={{ marginTop: 16 }} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        <Pressable onPress={() => router.back()} style={styles.back}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
        </Pressable>

        <Text style={styles.title}>{report.period}</Text>

        <MonthSummary
          total_spent={report.summary.total_spent}
          total_saved={report.summary.total_saved}
          receipts_count={report.summary.receipts_count}
          items_count={report.summary.items_count}
          avg_basket={report.summary.avg_basket_size}
          vs_previous={report.summary.vs_previous_month}
        />

        <SpendingChart data={report.by_category} period={report.period} />
        <StoreBreakdown data={report.by_store} />

        {/* Insights */}
        {report.insights.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Insights</Text>
            {report.insights.map((insight, i) => (
              <View key={i} style={styles.insightRow}>
                <Feather name="zap" size={16} color={Colors.accent.amber} />
                <Text style={styles.insightText}>{insight}</Text>
              </View>
            ))}
          </View>
        )}

        {/* Price Wins */}
        {report.price_wins.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Price Wins</Text>
            {report.price_wins.map((win, i) => (
              <Card key={i} style={styles.winCard}>
                <Text style={styles.winProduct}>{win.product}</Text>
                <Text style={styles.winDetail}>
                  You paid {formatCurrency(win.price)} at {win.store} — market avg {formatCurrency(win.avg_market_price)}
                </Text>
                <Text style={styles.winSaved}>Saved {formatCurrency(win.saved)}</Text>
              </Card>
            ))}
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  content: { padding: Spacing.md, paddingBottom: Spacing.xxl },
  skeletons: { padding: Spacing.md },
  back: { marginBottom: Spacing.sm },
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 32, color: Colors.primary.dark, marginBottom: Spacing.md },
  section: { marginTop: Spacing.lg },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  insightRow: { flexDirection: 'row', alignItems: 'flex-start', gap: Spacing.sm, marginBottom: Spacing.sm },
  insightText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.primary, flex: 1, lineHeight: 20 },
  winCard: { marginBottom: Spacing.sm },
  winProduct: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  winDetail: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, marginTop: 2 },
  winSaved: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 14, color: Colors.accent.green, marginTop: 4 },
});
