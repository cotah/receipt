import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import { BarChart } from 'react-native-gifted-charts';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';

interface ChartData {
  name: string;
  total: number;
  percentage: number;
}

interface SpendingChartProps {
  data: ChartData[];
  period: string;
}

export default function SpendingChart({ data, period }: SpendingChartProps) {
  if (data.length === 0) return null;

  const barData = data.slice(0, 6).map((item) => ({
    value: item.total,
    label: item.name.split(' ')[0],
    frontColor: Colors.accent.green,
    topLabelComponent: () => (
      <Text style={styles.barValue}>{formatCurrency(item.total)}</Text>
    ),
  }));

  return (
    <View style={styles.container}>
      <Text style={styles.title}>Spending by Category</Text>
      <BarChart
        data={barData}
        barWidth={28}
        barBorderRadius={4}
        noOfSections={4}
        height={120}
        spacing={16}
        hideRules
        hideYAxisText
        yAxisThickness={0}
        xAxisThickness={0}
        xAxisLabelTextStyle={styles.barLabel}
        disablePress
      />
    </View>
  );
}

const styles = StyleSheet.create({
  container: { marginVertical: Spacing.md },
  title: { fontFamily: 'DMSans_600SemiBold', fontSize: 16, color: Colors.text.primary, marginBottom: Spacing.md },
  barValue: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 10, color: Colors.text.secondary, marginBottom: 4 },
  barLabel: { fontFamily: 'DMSans_400Regular', fontSize: 10, color: Colors.text.tertiary },
});
