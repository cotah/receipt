import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Badge from '../ui/Badge';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';

interface Item {
  id: string;
  normalized_name: string;
  category: string;
  quantity: number;
  unit: string | null;
  unit_price: number;
  total_price: number;
  is_on_offer: boolean;
  collective_price: {
    cheapest_store: string;
    cheapest_price: number;
    difference: number;
  } | null;
}

interface ProductListProps {
  items: Item[];
  showComparison?: boolean;
}

function ProductRow({ item, showComparison }: { item: Item; showComparison: boolean }) {
  const qty = item.quantity !== 1 ? `${item.quantity}${item.unit ? ` ${item.unit}` : 'x'}` : null;

  return (
    <View style={styles.row}>
      <View style={styles.left}>
        <Text style={styles.name}>{item.normalized_name}</Text>
        <View style={styles.meta}>
          {qty && <Text style={styles.qty}>{qty}</Text>}
          <Badge text={item.category} variant="neutral" size="sm" />
          {item.is_on_offer && <Badge text="OFFER" variant="success" size="sm" />}
        </View>
        {showComparison && item.collective_price && item.collective_price.difference < 0 && (
          <Badge
            text={`${formatCurrency(Math.abs(item.collective_price.difference))} cheaper at ${item.collective_price.cheapest_store}`}
            variant="danger"
            size="sm"
          />
        )}
      </View>
      <Text style={styles.price}>{formatCurrency(item.total_price)}</Text>
    </View>
  );
}

export default function ProductList({ items, showComparison = false }: ProductListProps) {
  return (
    <View>
      {items.map((item) => (
        <ProductRow key={item.id} item={item} showComparison={showComparison} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    paddingVertical: Spacing.sm,
    borderBottomWidth: 1,
    borderBottomColor: Colors.surface.alt,
  },
  left: { flex: 1, marginRight: Spacing.md },
  name: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  meta: { flexDirection: 'row', gap: Spacing.xs, marginTop: 4, flexWrap: 'wrap' },
  qty: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary },
  price: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 15, color: Colors.accent.amber },
});
