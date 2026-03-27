import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../components/ui/Card';
import StoreTag from '../components/prices/StoreTag';
import { Colors } from '../constants/colors';
import { Spacing } from '../constants/typography';
import { formatCurrency } from '../utils/formatCurrency';
import api from '../services/api';

interface ShoppingItem {
  id: string;
  product_name: string;
  product_key: string;
  store_name: string | null;
  unit_price: number | null;
  category: string;
  source: string;
  is_checked: boolean;
}

interface StoreGroup {
  store_name: string;
  items: ShoppingItem[];
  item_count: number;
  estimated_total: number;
}

export default function ShoppingListScreen() {
  const router = useRouter();
  const [stores, setStores] = useState<StoreGroup[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [estimatedTotal, setEstimatedTotal] = useState(0);
  const [checkedCount, setCheckedCount] = useState(0);
  const [isLoading, setIsLoading] = useState(true);

  const fetchList = useCallback(async () => {
    try {
      const { data } = await api.get('/shopping-list');
      setStores(data.stores || []);
      setTotalItems(data.total_items || 0);
      setEstimatedTotal(data.estimated_total || 0);
      setCheckedCount(data.checked_count || 0);
    } catch {
      // Silent fail
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchList();
  }, []);

  const checkItem = async (itemId: string) => {
    try {
      await api.post('/shopping-list/check', { item_id: itemId, is_checked: true });
      // Remove from local state
      setStores(prev => prev.map(s => ({
        ...s,
        items: s.items.filter(i => i.id !== itemId),
        item_count: s.items.filter(i => i.id !== itemId).length,
        estimated_total: s.items.filter(i => i.id !== itemId).reduce((sum, i) => sum + (i.unit_price || 0), 0),
      })).filter(s => s.items.length > 0));
      setTotalItems(prev => prev - 1);
      setCheckedCount(prev => prev + 1);
    } catch {}
  };

  const removeItem = async (itemId: string) => {
    try {
      await api.delete(`/shopping-list/${itemId}`);
      setStores(prev => prev.map(s => ({
        ...s,
        items: s.items.filter(i => i.id !== itemId),
        item_count: s.items.filter(i => i.id !== itemId).length,
        estimated_total: s.items.filter(i => i.id !== itemId).reduce((sum, i) => sum + (i.unit_price || 0), 0),
      })).filter(s => s.items.length > 0));
      setTotalItems(prev => prev - 1);
    } catch {}
  };

  const clearChecked = async () => {
    if (checkedCount === 0) return;
    Alert.alert(
      'Clear bought items',
      `Remove ${checkedCount} checked items?`,
      [
        { text: 'Cancel', style: 'cancel' },
        {
          text: 'Clear',
          style: 'destructive',
          onPress: async () => {
            try {
              await api.post('/shopping-list/clear-checked');
              setCheckedCount(0);
            } catch {}
          },
        },
      ]
    );
  };

  if (isLoading) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.primary.default} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      {/* Header */}
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
        </Pressable>
        <Text style={styles.headerTitle}>Shopping List</Text>
        <View style={{ width: 24 }} />
      </View>

      {/* Summary bar */}
      {totalItems > 0 && (
        <View style={styles.summaryBar}>
          <Text style={styles.summaryText}>
            {totalItems} item{totalItems !== 1 ? 's' : ''} · est. {formatCurrency(estimatedTotal)}
          </Text>
          <View style={{ flexDirection: 'row', gap: 12 }}>
            {checkedCount > 0 && (
              <Pressable onPress={clearChecked}>
                <Text style={styles.clearText}>Clear {checkedCount} bought</Text>
              </Pressable>
            )}
            <Pressable onPress={() => router.push('/basket')}>
              <Text style={[styles.clearText, { color: Colors.accent.green }]}>⚡ Optimize</Text>
            </Pressable>
          </View>
        </View>
      )}

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {/* Empty state */}
        {totalItems === 0 && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyEmoji}>🛒</Text>
            <Text style={styles.emptyTitle}>Your list is empty</Text>
            <Text style={styles.emptyText}>
              Tap the + button on any deal or Price Memory card to add items here
            </Text>
            <Pressable style={styles.browseBtn} onPress={() => router.push('/(tabs)/prices')}>
              <Text style={styles.browseBtnText}>Browse Offers</Text>
            </Pressable>
          </View>
        )}

        {/* Store groups */}
        {stores.map((storeGroup) => (
          <View key={storeGroup.store_name} style={styles.storeSection}>
            <View style={styles.storeHeader}>
              <StoreTag storeName={storeGroup.store_name} size="md" />
              <Text style={styles.storeTotal}>
                {storeGroup.item_count} item{storeGroup.item_count !== 1 ? 's' : ''} · {formatCurrency(storeGroup.estimated_total)}
              </Text>
            </View>

            {storeGroup.items.map((item) => (
              <Card key={item.id} style={styles.itemCard}>
                <View style={styles.itemRow}>
                  {/* Check button */}
                  <Pressable onPress={() => checkItem(item.id)} style={styles.checkBtn}>
                    <Feather name="circle" size={22} color={Colors.text.tertiary} />
                  </Pressable>

                  {/* Product info */}
                  <View style={styles.itemInfo}>
                    <Text style={styles.itemName} numberOfLines={1}>{item.product_name}</Text>
                    <View style={styles.itemMeta}>
                      {item.unit_price && (
                        <Text style={styles.itemPrice}>{formatCurrency(item.unit_price)}</Text>
                      )}
                      <Text style={styles.itemSource}>
                        {item.source === 'deal' ? 'from offer' : item.source === 'memory' ? 'from price memory' : 'manual'}
                      </Text>
                    </View>
                  </View>

                  {/* Remove button */}
                  <Pressable onPress={() => removeItem(item.id)} style={styles.removeBtn} hitSlop={8}>
                    <Feather name="x" size={16} color={Colors.text.tertiary} />
                  </Pressable>
                </View>
              </Card>
            ))}
          </View>
        ))}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },

  // Header
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
  },
  headerTitle: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: Colors.primary.dark },

  // Summary
  summaryBar: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
    backgroundColor: Colors.surface.card, borderBottomWidth: 1, borderBottomColor: Colors.surface.border,
  },
  summaryText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary },
  clearText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.accent.blue },

  scroll: { padding: Spacing.md, paddingBottom: 100 },

  // Empty state
  emptyState: { alignItems: 'center', paddingTop: 60 },
  emptyEmoji: { fontSize: 48, marginBottom: Spacing.md },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 20, color: Colors.text.primary, marginBottom: Spacing.xs },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center', paddingHorizontal: Spacing.xl, marginBottom: Spacing.lg },
  browseBtn: { backgroundColor: Colors.primary.default, borderRadius: 12, paddingHorizontal: 24, paddingVertical: 12 },
  browseBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#fff' },

  // Store section
  storeSection: { marginBottom: Spacing.lg },
  storeHeader: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', marginBottom: Spacing.sm },
  storeTotal: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.secondary },

  // Item card
  itemCard: { marginBottom: Spacing.xs, padding: Spacing.sm },
  itemRow: { flexDirection: 'row', alignItems: 'center' },
  checkBtn: { marginRight: Spacing.sm, padding: 4 },
  itemInfo: { flex: 1 },
  itemName: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  itemMeta: { flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 2 },
  itemPrice: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 13, color: Colors.accent.green },
  itemSource: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: Colors.text.tertiary },
  removeBtn: { padding: 8 },
});
