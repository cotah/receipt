import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Card from '../ui/Card';
import Badge from '../ui/Badge';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';
import { formatRelativeDate } from '../../utils/formatDate';

const STATUS_COLORS: Record<string, string> = {
  done: Colors.accent.green,
  failed: Colors.accent.red,
  processing: Colors.accent.amber,
};

interface ReceiptCardProps {
  id: string;
  store_name: string;
  store_branch: string | null;
  purchased_at: string;
  total_amount: number;
  discount_total: number;
  items_count: number;
  status: string;
  onPress: () => void;
}

export default function ReceiptCard({
  store_name, store_branch, purchased_at,
  total_amount, discount_total, items_count, status, onPress,
}: ReceiptCardProps) {
  const dotColor = STATUS_COLORS[status] ?? Colors.text.tertiary;

  return (
    <Card onPress={onPress} style={styles.card}>
      <View style={styles.row}>
        <View style={styles.left}>
          <View style={[styles.dot, { backgroundColor: dotColor }]} />
          <View>
            <Text style={styles.storeName}>{store_name}</Text>
            {store_branch && <Text style={styles.branch}>{store_branch}</Text>}
          </View>
        </View>
        <View style={styles.right}>
          <Text style={styles.amount}>{formatCurrency(total_amount)}</Text>
          <Text style={styles.itemsCount}>{items_count} items</Text>
        </View>
      </View>
      <View style={styles.footer}>
        <Text style={styles.date}>{formatRelativeDate(purchased_at)}</Text>
        <View style={styles.badges}>
          {status === 'processing' && <Badge text="Processing..." variant="info" />}
          {status === 'failed' && <Badge text="Failed" variant="danger" />}
          {discount_total > 0 && <Badge text={`Saved ${formatCurrency(discount_total)}`} variant="success" />}
        </View>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginBottom: Spacing.sm },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  left: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: Spacing.sm },
  storeName: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: Colors.text.primary },
  branch: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary },
  right: { alignItems: 'flex-end' },
  amount: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 16, color: Colors.accent.amber },
  itemsCount: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary },
  footer: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm },
  date: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary },
  badges: { flexDirection: 'row', gap: Spacing.xs },
});
