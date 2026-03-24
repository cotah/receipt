import React from 'react';
import { View, Text, StyleSheet, Dimensions } from 'react-native';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';

interface DataPoint {
  date: string;
  price: number;
  store: string;
}

interface PriceHistoryProps {
  data: DataPoint[];
}

export default function PriceHistory({ data }: PriceHistoryProps) {
  if (data.length === 0) {
    return <Text style={styles.empty}>No price history yet</Text>;
  }

  const prices = data.map((d) => d.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;
  const chartW = Dimensions.get('window').width - 64;
  const chartH = 120;

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Price History</Text>
      <View style={[styles.chart, { width: chartW, height: chartH }]}>
        {/* Simple bar chart */}
        {data.map((point, i) => {
          const barH = ((point.price - min) / range) * (chartH - 20) + 20;
          const barW = Math.max(4, (chartW - data.length * 2) / data.length);
          return (
            <View key={i} style={styles.barWrap}>
              <View style={[styles.bar, { height: barH, width: barW, backgroundColor: Colors.accent.green }]} />
              <Text style={styles.barLabel}>{point.date.slice(5)}</Text>
            </View>
          );
        })}
      </View>
      <View style={styles.range}>
        <Text style={styles.rangeText}>€{min.toFixed(2)}</Text>
        <Text style={styles.rangeText}>€{max.toFixed(2)}</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginVertical: Spacing.md },
  title: { fontFamily: 'DMSans_600SemiBold', fontSize: 16, color: Colors.text.primary, marginBottom: Spacing.sm },
  chart: { flexDirection: 'row', alignItems: 'flex-end', gap: 2 },
  barWrap: { alignItems: 'center' },
  bar: { borderRadius: 2 },
  barLabel: { fontFamily: 'DMSans_400Regular', fontSize: 9, color: Colors.text.tertiary, marginTop: 2 },
  range: { flexDirection: 'row', justifyContent: 'space-between', marginTop: Spacing.xs },
  rangeText: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 11, color: Colors.text.tertiary },
  empty: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.tertiary, textAlign: 'center' },
});
