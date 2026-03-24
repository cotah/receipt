import React from 'react';
import { View, Text, StyleSheet } from 'react-native';
import Card from '../ui/Card';
import Badge from '../ui/Badge';
import StoreTag from './StoreTag';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';
import { formatRelativeDate } from '../../utils/formatDate';

interface StorePrice {
  store_name: string;
  unit_price: number;
  is_on_offer: boolean;
  last_seen: string;
  confirmations: number;
  is_cheapest: boolean;
  saving_vs_most_expensive: number | null;
}

interface PriceCompareProps {
  product_name: string;
  unit: string | null;
  stores: StorePrice[];
}

export default function PriceCompare({ product_name, unit, stores }: PriceCompareProps) {
  return (
    <View>
      <Text style={styles.title}>{product_name}</Text>
      {unit && <Text style={styles.unit}>per {unit}</Text>}

      {stores.map((store, i) => (
        <Card key={store.store_name} style={styles.card}>
          <View style={styles.row}>
            <View style={styles.left}>
              <StoreTag storeName={store.store_name} size="md" />
              <Text style={styles.meta}>
                {store.confirmations} confirmations · {formatRelativeDate(store.last_seen)}
              </Text>
            </View>
            <View style={styles.right}>
              <Text style={styles.price}>{formatCurrency(store.unit_price)}</Text>
              {store.is_cheapest && <Badge text="CHEAPEST" variant="success" size="sm" />}
              {store.is_on_offer && <Badge text="ON OFFER" variant="warning" size="sm" />}
            </View>
          </View>
          {!store.is_cheapest && store.saving_vs_most_expensive !== null && i === stores.length - 1 && (
            <Text style={styles.diff}>
              Save {formatCurrency(stores[stores.length - 1].unit_price - stores[0].unit_price)} vs cheapest
            </Text>
          )}
        </Card>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 22, color: Colors.text.primary, marginBottom: 4 },
  unit: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, marginBottom: Spacing.md },
  card: { marginBottom: Spacing.sm },
  row: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  left: { flex: 1 },
  meta: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, marginTop: 4 },
  right: { alignItems: 'flex-end', gap: 4 },
  price: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 20, color: Colors.accent.amber },
  diff: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.accent.red, marginTop: Spacing.xs },
});
