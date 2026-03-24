import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { Feather } from '@expo/vector-icons';
import Card from '../ui/Card';
import Badge from '../ui/Badge';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';

interface MonthSummaryProps {
  total_spent: number;
  total_saved: number;
  receipts_count: number;
  items_count: number;
  avg_basket: number;
  vs_previous: { amount: number; percent: number; trend: string };
}

export default function MonthSummary({
  total_spent, total_saved, receipts_count, items_count, avg_basket, vs_previous,
}: MonthSummaryProps) {
  const isDown = vs_previous.trend === 'down';

  return (
    <Card variant="elevated">
      <Text style={styles.totalLabel}>Total Spent</Text>
      <Text style={styles.total}>{formatCurrency(total_spent)}</Text>
      <View style={styles.trend}>
        <Feather
          name={isDown ? 'arrow-down-right' : 'arrow-up-right'}
          size={16}
          color={isDown ? Colors.accent.green : Colors.accent.red}
        />
        <Text style={[styles.trendText, { color: isDown ? Colors.accent.green : Colors.accent.red }]}>
          {Math.abs(vs_previous.percent).toFixed(1)}% vs last month
        </Text>
      </View>

      <View style={styles.stats}>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{receipts_count}</Text>
          <Text style={styles.statLabel}>Shops</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{items_count}</Text>
          <Text style={styles.statLabel}>Items</Text>
        </View>
        <View style={styles.stat}>
          <Text style={styles.statValue}>{formatCurrency(avg_basket)}</Text>
          <Text style={styles.statLabel}>Avg basket</Text>
        </View>
      </View>

      {total_saved > 0 && (
        <Badge text={`You saved ${formatCurrency(total_saved)} this month!`} variant="success" size="md" />
      )}
    </Card>
  );
}

const styles = StyleSheet.create({
  totalLabel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.text.secondary },
  total: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 36, color: Colors.accent.amber, marginVertical: 4 },
  trend: { flexDirection: 'row', alignItems: 'center', marginBottom: Spacing.md },
  trendText: { fontFamily: 'DMSans_500Medium', fontSize: 14, marginLeft: 4 },
  stats: { flexDirection: 'row', justifyContent: 'space-around', marginBottom: Spacing.md },
  stat: { alignItems: 'center' },
  statValue: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 18, color: Colors.text.primary },
  statLabel: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary },
});
