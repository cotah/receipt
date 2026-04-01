import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';

import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import StoreTag from '../components/prices/StoreTag';
import ExpiryBadge from '../components/prices/ExpiryBadge';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../constants/typography';
import { formatCurrency } from '../utils/formatCurrency';
import api from '../services/api';

interface StorePrice {
  store_name: string;
  unit_price: number;
  is_on_offer: boolean;
  promotion_text: string | null;
  image_url: string | null;
}

interface UsualItem {
  product_name: string;
  product_key: string;
  category: string;
  purchase_count: number;
  avg_price_paid: number | null;
  cheapest_price: number | null;
  cheapest_store: string | null;
  price_dropped: boolean;
  stores: StorePrice[];
}

interface StoreTotal {
  store_name: string;
  total: number;
  item_count: number;
}

interface UsualShopData {
  items: UsualItem[];
  store_totals: StoreTotal[];
  cheapest_store: string | null;
  cheapest_total: number | null;
  total_saving: number;
  item_count: number;
}

export default function UsualShopScreen() {
  const [data, setData] = useState<UsualShopData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const { data: res } = await api.get<UsualShopData>('/prices/my-usual-shop');
      setData(res);
    } catch (e: any) {
      setError('Could not load your usual shop');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
        {/* Header */}
        <View style={styles.header}>
          <Pressable onPress={() => router.back()} style={styles.backBtn}>
            <Feather name="arrow-left" size={22} color={Colors.text.primary} />
          </Pressable>
          <Text style={styles.title}>My usual shop</Text>
          <Pressable onPress={fetchData} style={styles.refreshBtn}>
            <Feather name="refresh-cw" size={18} color={Colors.text.secondary} />
          </Pressable>
        </View>
        <Text style={styles.subtitle}>Based on your receipts</Text>

        {isLoading && (
          <View style={styles.loadingRow}>
            <ActivityIndicator size="small" color={Colors.primary.default} />
            <Text style={styles.loadingText}>Analysing your shopping habits...</Text>
          </View>
        )}

        {error && (
          <Card style={styles.errorCard}>
            <Text style={styles.errorText}>{error}</Text>
            <Pressable onPress={fetchData} style={styles.retryBtn}>
              <Text style={styles.retryText}>Try again</Text>
            </Pressable>
          </Card>
        )}

        {data && !isLoading && data.items.length === 0 && (
          <Card style={styles.emptyCard}>
            <Feather name="shopping-bag" size={40} color={Colors.text.tertiary} />
            <Text style={styles.emptyTitle}>No shopping history yet</Text>
            <Text style={styles.emptyText}>
              Scan a few receipts and we'll show you where to find your usual items cheapest.
            </Text>
          </Card>
        )}

        {data && !isLoading && data.items.length > 0 && (
          <>
            {/* Summary card */}
            <Card style={styles.summaryCard}>
              <Text style={styles.summaryLabel}>
                Your {data.item_count} usual items this week
              </Text>
              <View style={styles.summaryRow}>
                <View>
                  <Text style={styles.summaryPrice}>
                    {data.cheapest_total ? formatCurrency(data.cheapest_total) : '—'}
                  </Text>
                  <Text style={styles.summaryStore}>
                    at {data.cheapest_store || '—'}
                  </Text>
                </View>
                {data.total_saving > 0 && (
                  <View style={styles.savingBox}>
                    <Text style={styles.savingText}>
                      Save {formatCurrency(data.total_saving)}
                    </Text>
                  </View>
                )}
              </View>

              {/* Store comparison mini bars */}
              {data.store_totals.length > 1 && (
                <View style={styles.storeBars}>
                  {data.store_totals.map((st, i) => (
                    <View key={st.store_name} style={styles.storeBarRow}>
                      <Text style={styles.storeBarName}>{st.store_name}</Text>
                      <View style={styles.storeBarTrack}>
                        <View
                          style={[
                            styles.storeBarFill,
                            {
                              width: `${Math.min(100, (st.total / (data.store_totals[data.store_totals.length - 1]?.total || 1)) * 100)}%`,
                              backgroundColor: i === 0 ? Colors.primary.default : Colors.surface.alt,
                            },
                          ]}
                        />
                      </View>
                      <Text style={[styles.storeBarPrice, i === 0 && styles.storeBarCheapest]}>
                        {formatCurrency(st.total)}
                      </Text>
                    </View>
                  ))}
                </View>
              )}
            </Card>

            {/* Product list */}
            <Text style={styles.sectionTitle}>YOUR FREQUENT ITEMS</Text>

            {data.items.map((item) => (
              <Card key={item.product_key} style={styles.itemCard}>
                <View style={styles.itemRow}>
                  <View style={styles.itemLeft}>
                    <Text style={styles.itemName} numberOfLines={2}>
                      {item.product_name}
                    </Text>
                    <View style={styles.itemMeta}>
                      {item.cheapest_store && (
                        <Text style={styles.itemStore}>
                          Cheapest: {item.cheapest_store}
                        </Text>
                      )}
                      {item.price_dropped && (
                        <Badge text="price dropped" variant="success" size="sm" />
                      )}
                      {item.stores.some((s) => s.is_on_offer) && (
                        <Badge text="on offer" variant="warning" size="sm" />
                      )}
                    </View>
                  </View>
                  <View style={styles.itemRight}>
                    {item.cheapest_price ? (
                      <Text
                        style={[
                          styles.itemPrice,
                          item.price_dropped && styles.itemPriceDropped,
                        ]}
                      >
                        {formatCurrency(item.cheapest_price)}
                      </Text>
                    ) : (
                      <Text style={styles.itemPriceNA}>—</Text>
                    )}
                    {item.avg_price_paid && item.cheapest_price && item.cheapest_price < item.avg_price_paid && (
                      <Text style={styles.itemWas}>
                        was {formatCurrency(item.avg_price_paid)}
                      </Text>
                    )}
                  </View>
                </View>
              </Card>
            ))}
          </>
        )}

        <View style={{ height: 40 }} />
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: Colors.surface.background },
  scroll: { flex: 1 },
  content: { padding: Spacing.lg },
  header: {
    flexDirection: 'row',
    alignItems: 'center',
    marginBottom: 4,
  },
  backBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: Colors.surface.alt,
    alignItems: 'center', justifyContent: 'center',
    marginRight: Spacing.sm,
  },
  title: {
    fontSize: 22,
    fontFamily: Fonts.display,
    color: Colors.text.primary,
    flex: 1,
  },
  refreshBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: Colors.surface.alt,
    alignItems: 'center', justifyContent: 'center',
  },
  subtitle: {
    fontSize: 13,
    fontFamily: Fonts.body,
    color: Colors.text.secondary,
    marginBottom: Spacing.lg,
    marginLeft: 48,
  },
  loadingRow: {
    flexDirection: 'row', alignItems: 'center',
    gap: 8, paddingVertical: Spacing.xl,
    justifyContent: 'center',
  },
  loadingText: {
    fontFamily: Fonts.body,
    color: Colors.text.secondary,
    fontSize: 14,
  },
  errorCard: { alignItems: 'center', padding: Spacing.lg },
  errorText: { fontFamily: Fonts.body, color: Colors.text.secondary, marginBottom: Spacing.sm },
  retryBtn: {
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.xs,
    borderRadius: BorderRadius.md,
    backgroundColor: Colors.primary.default,
  },
  retryText: { fontFamily: Fonts.bodyBold, color: '#FFF', fontSize: 13 },
  emptyCard: {
    alignItems: 'center', padding: Spacing.xl, gap: Spacing.sm,
  },
  emptyTitle: {
    fontFamily: Fonts.bodyBold, fontSize: 16,
    color: Colors.text.primary, marginTop: Spacing.sm,
  },
  emptyText: {
    fontFamily: Fonts.body, fontSize: 13,
    color: Colors.text.secondary, textAlign: 'center',
  },
  summaryCard: {
    backgroundColor: Colors.primary.default,
    padding: Spacing.lg,
    marginBottom: Spacing.lg,
  },
  summaryLabel: {
    fontFamily: Fonts.body, fontSize: 13,
    color: 'rgba(255,255,255,0.7)', marginBottom: 4,
  },
  summaryRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: Spacing.md,
  },
  summaryPrice: {
    fontFamily: 'CourierPrime_700Bold',
    fontSize: 28, color: '#FFF',
  },
  summaryStore: {
    fontFamily: Fonts.body, fontSize: 13,
    color: 'rgba(255,255,255,0.7)',
  },
  savingBox: {
    backgroundColor: 'rgba(60,179,113,0.25)',
    borderRadius: BorderRadius.sm,
    paddingHorizontal: 10, paddingVertical: 4,
  },
  savingText: {
    fontFamily: Fonts.bodyBold, fontSize: 14,
    color: '#7DDFAA',
  },
  storeBars: { gap: 6 },
  storeBarRow: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
  },
  storeBarName: {
    fontFamily: Fonts.body, fontSize: 11,
    color: 'rgba(255,255,255,0.6)', width: 70,
  },
  storeBarTrack: {
    flex: 1, height: 6, borderRadius: 3,
    backgroundColor: 'rgba(255,255,255,0.15)',
  },
  storeBarFill: { height: 6, borderRadius: 3 },
  storeBarPrice: {
    fontFamily: Fonts.bodyBold, fontSize: 12,
    color: 'rgba(255,255,255,0.7)', width: 55, textAlign: 'right',
  },
  storeBarCheapest: { color: '#FFF' },
  sectionTitle: {
    fontFamily: Fonts.bodyBold, fontSize: 12,
    color: Colors.text.secondary, letterSpacing: 0.5,
    marginBottom: Spacing.sm,
  },
  itemCard: { marginBottom: Spacing.xs },
  itemRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  itemLeft: { flex: 1, marginRight: Spacing.sm },
  itemName: {
    fontFamily: Fonts.bodyBold, fontSize: 14,
    color: Colors.text.primary,
  },
  itemMeta: {
    flexDirection: 'row', alignItems: 'center',
    gap: 6, marginTop: 4,
    flexWrap: 'wrap',
  },
  itemStore: {
    fontFamily: Fonts.body, fontSize: 12,
    color: Colors.text.secondary,
  },
  itemRight: { alignItems: 'flex-end' },
  itemPrice: {
    fontFamily: 'CourierPrime_700Bold',
    fontSize: 16, color: Colors.text.primary,
  },
  itemPriceDropped: { color: '#7DDFAA' },
  itemPriceNA: {
    fontFamily: Fonts.body, fontSize: 14,
    color: Colors.text.tertiary,
  },
  itemWas: {
    fontFamily: Fonts.body, fontSize: 11,
    color: Colors.text.tertiary, marginTop: 2,
  },
});
