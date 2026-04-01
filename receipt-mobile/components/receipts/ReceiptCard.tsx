import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Card from '../ui/Card';
import Badge from '../ui/Badge';
import { Colors } from '../../constants/colors';
import { STORE_COLORS, StoreName } from '../../constants/stores';
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
  error_reason?: string | null;
  onPress: () => void;
}

function shortErrorReason(reason?: string | null): string {
  if (!reason) return 'Failed';
  const lower = reason.toLowerCase();
  if (lower.includes('duplicate')) return 'Duplicate';
  if (lower.includes('too old')) return 'Too old';
  if (lower.includes('not a') || lower.includes('invalid') || lower.includes('supported')) return 'Invalid store';
  return 'Failed';
}

function normalizeStore(name: string): string {
  const l = name.toLowerCase().trim();
  if (l.includes('lidl')) return 'Lidl';
  if (l.includes('tesco')) return 'Tesco';
  if (l.includes('aldi')) return 'Aldi';
  if (l.includes('supervalu') || l.includes('super valu')) return 'SuperValu';
  if (l.includes('dunnes')) return 'Dunnes';
  return name;
}

export default function ReceiptCard({
  store_name, store_branch, purchased_at,
  total_amount, discount_total, items_count, status, error_reason, onPress,
}: ReceiptCardProps) {
  const dotColor = STATUS_COLORS[status] ?? Colors.text.tertiary;
  const nStore = normalizeStore(store_name);
  const storeColor = STORE_COLORS[nStore as StoreName]?.primary ?? Colors.accent.green;

  return (
    <Card onPress={onPress} style={[styles.card, { borderLeftColor: storeColor }]}>
      <View style={styles.row}>
        <View style={styles.left}>
          <View style={[styles.dot, { backgroundColor: dotColor }]} />
          <View>
            <Text style={styles.storeName}>{nStore}</Text>
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
          {status === 'failed' && <Badge text={shortErrorReason(error_reason)} variant="danger" />}
          {discount_total > 0 && <Badge text={`Saved ${formatCurrency(discount_total)}`} variant="success" />}
        </View>
      </View>
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { marginBottom: Spacing.sm, borderLeftWidth: 3 },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  left: { flexDirection: 'row', alignItems: 'center', flex: 1 },
  dot: { width: 10, height: 10, borderRadius: 5, marginRight: Spacing.sm },
  storeName: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: '#FFFFFF' },
  branch: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.50)' },
  right: { alignItems: 'flex-end' },
  amount: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 17, color: Colors.accent.amber },
  itemsCount: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: 'rgba(255,255,255,0.35)' },
  footer: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm },
  date: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: 'rgba(255,255,255,0.35)' },
  badges: { flexDirection: 'row', gap: Spacing.xs },
});
