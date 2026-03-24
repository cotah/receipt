import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { PieChart } from 'react-native-gifted-charts';
import { STORE_COLORS, StoreName } from '../../constants/stores';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';

interface StoreData {
  store: string;
  total: number;
  visits: number;
  percentage: number;
}

interface StoreBreakdownProps {
  data: StoreData[];
}

export default function StoreBreakdown({ data }: StoreBreakdownProps) {
  const total = data.reduce((sum, d) => sum + d.total, 0);

  const pieData = data.map((d) => ({
    value: d.total,
    color: STORE_COLORS[d.store as StoreName]?.primary ?? Colors.text.secondary,
  }));

  return (
    <View style={styles.container}>
      <Text style={styles.title}>By Store</Text>

      {/* Donut chart */}
      <View style={styles.chartWrap}>
        <PieChart
          data={pieData}
          donut
          radius={60}
          innerRadius={36}
          centerLabelComponent={() => (
            <Text style={styles.centerLabel}>{formatCurrency(total)}</Text>
          )}
        />
      </View>

      {/* Legend */}
      {data.map((d) => {
        const color = STORE_COLORS[d.store as StoreName]?.primary ?? Colors.text.secondary;
        return (
          <View key={d.store} style={styles.legendRow}>
            <View style={styles.legendLeft}>
              <View style={[styles.dot, { backgroundColor: color }]} />
              <Text style={styles.storeName}>{d.store}</Text>
            </View>
            <View style={styles.legendRight}>
              <Text style={styles.amount}>{formatCurrency(d.total)}</Text>
              <Text style={styles.pct}>{d.percentage.toFixed(0)}%</Text>
            </View>
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginVertical: Spacing.md },
  title: { fontFamily: 'DMSans_600SemiBold', fontSize: 16, color: Colors.text.primary, marginBottom: Spacing.md },
  chartWrap: { alignItems: 'center', marginBottom: Spacing.md },
  centerLabel: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 14, color: Colors.text.primary },
  legendRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingVertical: 6 },
  legendLeft: { flexDirection: 'row', alignItems: 'center' },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: Spacing.sm },
  storeName: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.text.primary },
  legendRight: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  amount: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 14, color: Colors.text.primary },
  pct: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, width: 32, textAlign: 'right' },
});
