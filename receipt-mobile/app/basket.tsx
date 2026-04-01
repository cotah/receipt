import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../components/ui/Card';
import Badge from '../components/ui/Badge';
import StoreTag from '../components/prices/StoreTag';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius } from '../constants/typography';
import { formatCurrency } from '../utils/formatCurrency';
import api from '../services/api';

interface ItemDetail {
  name: string;
  price: number | null;
  found: boolean;
}

interface StoreResult {
  store: string;
  total_estimated: number;
  items_available: number;
  items_missing: number;
  savings_vs_most_expensive: number;
  items: ItemDetail[];
}

export default function BasketScreen() {
  const router = useRouter();
  const [items, setItems] = useState<string[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [result, setResult] = useState<any>(null);
  const [expandedStore, setExpandedStore] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const { data } = await api.get('/shopping-list');
        const listItems: string[] = [];
        for (const store of data.stores || []) {
          for (const item of store.items || []) {
            if (item.product_name) listItems.push(item.product_name);
          }
        }
        if (listItems.length > 0) setItems(listItems);
      } catch {}
      setIsLoadingList(false);
    })();
  }, []);

  const addItem = () => {
    const trimmed = inputText.trim();
    if (!trimmed || items.includes(trimmed)) return;
    setItems(prev => [...prev, trimmed]);
    setInputText('');
    setResult(null);
  };

  const removeItem = (index: number) => {
    setItems(prev => prev.filter((_, i) => i !== index));
    setResult(null);
  };

  const optimize = async () => {
    if (items.length === 0) {
      Alert.alert('Add items', 'Add at least one item to your basket');
      return;
    }
    setIsLoading(true);
    setExpandedStore(null);
    try {
      const { data } = await api.post('/prices/basket', { items });
      setResult(data);
    } catch {
      Alert.alert('Error', 'Could not optimize basket');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleStore = (store: string) => {
    setExpandedStore(prev => prev === store ? null : store);
  };

  if (isLoadingList) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.centered}>
          <ActivityIndicator size="large" color={Colors.accent.green} />
        </View>
      </SafeAreaView>
    );
  }

  return (
    <SafeAreaView style={styles.container}>
      <View style={styles.header}>
        <Pressable onPress={() => router.back()} hitSlop={12}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
        </Pressable>
        <Text style={styles.headerTitle}>Basket Optimizer</Text>
        <View style={{ width: 24 }} />
      </View>

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {/* Input */}
        <View style={styles.inputRow}>
          <TextInput
            style={styles.input}
            placeholder="Add item (e.g. Milk, Bread, Chicken)"
            placeholderTextColor={Colors.text.tertiary}
            value={inputText}
            onChangeText={setInputText}
            onSubmitEditing={addItem}
            returnKeyType="done"
          />
          <Pressable style={styles.addBtn} onPress={addItem}>
            <Feather name="plus" size={20} color="#fff" />
          </Pressable>
        </View>

        {/* Items list */}
        {items.length > 0 && (
          <View style={styles.itemsList}>
            {items.map((item, i) => (
              <View key={i} style={styles.itemChip}>
                <Text style={styles.itemChipText} numberOfLines={1}>{item}</Text>
                <Pressable onPress={() => removeItem(i)} hitSlop={8}>
                  <Feather name="x" size={14} color={Colors.text.tertiary} />
                </Pressable>
              </View>
            ))}
          </View>
        )}

        {/* Optimize button */}
        <Pressable
          style={[styles.optimizeBtn, items.length === 0 && styles.optimizeBtnDisabled]}
          onPress={optimize}
          disabled={isLoading || items.length === 0}
        >
          {isLoading ? (
            <ActivityIndicator size="small" color="#fff" />
          ) : (
            <>
              <Feather name="zap" size={18} color="#fff" />
              <Text style={styles.optimizeBtnText}>
                Find cheapest stores for {items.length} item{items.length !== 1 ? 's' : ''}
              </Text>
            </>
          )}
        </Pressable>

        {/* Results */}
        {result && (
          <View style={styles.results}>
            {/* Split recommendation */}
            {result.split_recommendation && (
              <Card style={styles.splitCard}>
                <View style={styles.splitHeader}>
                  <Feather name="scissors" size={18} color={Colors.accent.green} />
                  <Text style={styles.splitTitle}>Smart Split</Text>
                </View>
                <Text style={styles.splitTotal}>
                  Split your shop for {formatCurrency(result.split_recommendation.total_with_split)}
                </Text>
                <Text style={styles.splitDetail}>{result.split_recommendation.message}</Text>
              </Card>
            )}

            {/* Store comparison */}
            <Text style={styles.resultsTitle}>Store Comparison</Text>
            <Text style={styles.resultsHint}>Tap a store to see product details</Text>

            {result.summary?.map((store: StoreResult, i: number) => (
              <View key={store.store}>
                <Pressable onPress={() => toggleStore(store.store)}>
                  <Card style={[styles.storeCard, i === 0 && styles.cheapestCard] as any}>
                    <View style={styles.storeRow}>
                      <View style={styles.storeLeft}>
                        <StoreTag storeName={store.store} size="md" />
                        <View style={styles.storeStats}>
                          <Text style={styles.storeAvail}>
                            {store.items_available}/{items.length} items
                          </Text>
                          {store.items_missing > 0 && (
                            <Text style={styles.storeMissing}>
                              {store.items_missing} missing
                            </Text>
                          )}
                        </View>
                      </View>
                      <View style={styles.storeRight}>
                        <Text style={[styles.storePrice, i === 0 && styles.cheapestPrice]}>
                          {formatCurrency(store.total_estimated)}
                        </Text>
                        {i === 0 && result.summary.length > 1 && (
                          <Text style={styles.cheapestLabel}>CHEAPEST</Text>
                        )}
                      </View>
                    </View>
                    <View style={styles.expandRow}>
                      <Feather
                        name={expandedStore === store.store ? 'chevron-up' : 'chevron-down'}
                        size={14} color={Colors.text.tertiary}
                      />
                      <Text style={styles.expandText}>
                        {expandedStore === store.store ? 'Hide details' : 'See products'}
                      </Text>
                    </View>
                  </Card>
                </Pressable>

                {/* Expanded product list */}
                {expandedStore === store.store && store.items && (
                  <Card style={styles.detailCard}>
                    {store.items.filter((d: ItemDetail) => d.found).length > 0 && (
                      <Text style={styles.detailSectionTitle}>✓ Available</Text>
                    )}
                    {store.items.filter((d: ItemDetail) => d.found).map((d: ItemDetail, j: number) => (
                      <View key={`found-${j}`} style={styles.detailRow}>
                        <View style={styles.detailIcon}>
                          <Feather name="check" size={12} color={Colors.accent.green} />
                        </View>
                        <Text style={styles.detailName} numberOfLines={1}>{d.name}</Text>
                        <Text style={styles.detailPrice}>{d.price != null ? formatCurrency(d.price) : ''}</Text>
                      </View>
                    ))}
                    {store.items.filter((d: ItemDetail) => !d.found).length > 0 && (
                      <Text style={[styles.detailSectionTitle, { marginTop: 10 }]}>✗ Not found</Text>
                    )}
                    {store.items.filter((d: ItemDetail) => !d.found).map((d: ItemDetail, j: number) => (
                      <View key={`missing-${j}`} style={styles.detailRow}>
                        <View style={[styles.detailIcon, { backgroundColor: Colors.accent.redSoft }]}>
                          <Feather name="x" size={12} color="#E85D3A" />
                        </View>
                        <Text style={[styles.detailName, { color: Colors.text.tertiary }]} numberOfLines={1}>{d.name}</Text>
                        <Text style={styles.detailMissing}>—</Text>
                      </View>
                    ))}
                  </Card>
                )}
              </View>
            ))}

            {result.summary?.length === 0 && (
              <Card style={styles.noResultCard}>
                <Text style={styles.noResultText}>
                  None of these items were found in current offers. Try different product names.
                </Text>
              </Card>
            )}
          </View>
        )}

        {/* Empty state */}
        {items.length === 0 && !result && (
          <View style={styles.emptyState}>
            <Text style={styles.emptyEmoji}>🧺</Text>
            <Text style={styles.emptyTitle}>Add your shopping list</Text>
            <Text style={styles.emptyText}>
              Type items above or they'll load automatically from your Shopping List
            </Text>
          </View>
        )}
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center' },
  header: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm,
  },
  headerTitle: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: '#FFFFFF' },
  scroll: { padding: Spacing.md, paddingBottom: 100 },
  inputRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.sm },
  input: {
    flex: 1, backgroundColor: Colors.surface.card, borderRadius: 12,
    paddingHorizontal: Spacing.md, paddingVertical: 12,
    fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.primary,
    borderWidth: 1, borderColor: Colors.surface.border,
  },
  addBtn: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(80,200,120,0.20)',
    alignItems: 'center', justifyContent: 'center',
  },
  itemsList: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: Spacing.md },
  itemChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: Colors.surface.card, borderRadius: 20,
    paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: Colors.surface.border,
  },
  itemChipText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.primary, maxWidth: 150 },
  optimizeBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: 'rgba(80,200,120,0.20)', borderRadius: 12,
    paddingVertical: 14, marginBottom: Spacing.lg,
  },
  optimizeBtnDisabled: { opacity: 0.5 },
  optimizeBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 16, color: 'rgba(255,255,255,0.08)' },
  results: { marginTop: Spacing.sm },
  resultsTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: 2 },
  resultsHint: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, marginBottom: Spacing.sm },
  splitCard: { marginBottom: Spacing.md, padding: Spacing.md, borderWidth: 1, borderColor: 'rgba(80,200,120,0.25)', backgroundColor: 'rgba(80,200,120,0.10)' },
  splitHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  splitTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: Colors.text.primary },
  splitTotal: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 18, color: Colors.accent.green, marginBottom: 4 },
  splitDetail: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, lineHeight: 18 },
  storeCard: { marginBottom: Spacing.xs },
  cheapestCard: { borderWidth: 2, borderColor: Colors.accent.green },
  storeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  storeLeft: { flex: 1, gap: 4 },
  storeStats: { flexDirection: 'row', gap: 8, marginTop: 2 },
  storeAvail: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary },
  storeMissing: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: '#F07B7B' },
  storeRight: { alignItems: 'flex-end' },
  storePrice: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 20, color: Colors.text.primary },
  cheapestPrice: { color: Colors.accent.green },
  cheapestLabel: { fontFamily: 'DMSans_600SemiBold', fontSize: 10, color: Colors.accent.green, marginTop: 2 },
  expandRow: {
    flexDirection: 'row', alignItems: 'center', gap: 4,
    marginTop: 8, paddingTop: 8, borderTopWidth: 1, borderTopColor: Colors.surface.alt,
  },
  expandText: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary },
  detailCard: { marginBottom: Spacing.sm, marginLeft: 8, borderLeftWidth: 3, borderLeftColor: Colors.primary.light },
  detailSectionTitle: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: Colors.text.secondary, marginBottom: 6 },
  detailRow: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 5 },
  detailIcon: {
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: Colors.accent.greenSoft,
    alignItems: 'center', justifyContent: 'center',
  },
  detailName: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.primary, flex: 1 },
  detailPrice: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 13, color: Colors.accent.amber },
  detailMissing: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.tertiary },
  noResultCard: { padding: Spacing.md },
  noResultText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center' },
  emptyState: { alignItems: 'center', paddingTop: 40 },
  emptyEmoji: { fontSize: 48, marginBottom: Spacing.md },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 20, color: Colors.text.primary, marginBottom: Spacing.xs },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center', paddingHorizontal: Spacing.xl },
});
