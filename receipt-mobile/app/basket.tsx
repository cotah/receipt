import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, Pressable, TextInput, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../components/ui/Card';
import StoreTag from '../components/prices/StoreTag';
import { Colors } from '../constants/colors';
import { Spacing } from '../constants/typography';
import { formatCurrency } from '../utils/formatCurrency';
import api from '../services/api';

export default function BasketScreen() {
  const router = useRouter();
  const [items, setItems] = useState<string[]>([]);
  const [inputText, setInputText] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingList, setIsLoadingList] = useState(true);
  const [result, setResult] = useState<any>(null);

  // Auto-load items from shopping list
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
    if (!trimmed) return;
    if (items.includes(trimmed)) return;
    setItems(prev => [...prev, trimmed]);
    setInputText('');
    setResult(null); // Clear previous results
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
    try {
      const { data } = await api.post('/prices/basket', { items });
      setResult(data);
    } catch {
      Alert.alert('Error', 'Could not optimize basket');
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoadingList) {
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
                  Split your shop across stores for {formatCurrency(result.split_recommendation.total_with_split)}
                </Text>
                <Text style={styles.splitDetail}>{result.split_recommendation.message}</Text>
                {result.summary.length > 0 && (
                  <Text style={styles.splitSaving}>
                    Save {formatCurrency(result.summary[0].total_estimated - result.split_recommendation.total_with_split)} vs best single store
                  </Text>
                )}
              </Card>
            )}

            {/* Store comparison */}
            <Text style={styles.resultsTitle}>Store Comparison</Text>

            {result.summary?.map((store: any, i: number) => (
              <Card key={store.store} style={[styles.storeCard, i === 0 && styles.cheapestCard] as any}>
                <View style={styles.storeRow}>
                  <View style={styles.storeLeft}>
                    <StoreTag storeName={store.store} size="md" />
                    <View style={styles.storeStats}>
                      <Text style={styles.storeAvail}>
                        {store.items_available}/{items.length} items found
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
                    {store.savings_vs_most_expensive > 0 && i === 0 && (
                      <Text style={styles.savingLabel}>
                        Save {formatCurrency(store.savings_vs_most_expensive)}
                      </Text>
                    )}
                  </View>
                </View>
              </Card>
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
  headerTitle: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 24, color: Colors.primary.dark },
  scroll: { padding: Spacing.md, paddingBottom: 100 },

  // Input
  inputRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.sm },
  input: {
    flex: 1, backgroundColor: Colors.surface.card, borderRadius: 12,
    paddingHorizontal: Spacing.md, paddingVertical: 12,
    fontFamily: 'DMSans_400Regular', fontSize: 15, color: Colors.text.primary,
    borderWidth: 1, borderColor: Colors.surface.border,
  },
  addBtn: {
    width: 44, height: 44, borderRadius: 12, backgroundColor: Colors.primary.default,
    alignItems: 'center', justifyContent: 'center',
  },

  // Item chips
  itemsList: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, marginBottom: Spacing.md },
  itemChip: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    backgroundColor: Colors.surface.card, borderRadius: 20,
    paddingHorizontal: 12, paddingVertical: 6,
    borderWidth: 1, borderColor: Colors.surface.border,
  },
  itemChipText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.primary, maxWidth: 150 },

  // Optimize button
  optimizeBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: Colors.primary.default, borderRadius: 12,
    paddingVertical: 14, marginBottom: Spacing.lg,
  },
  optimizeBtnDisabled: { opacity: 0.5 },
  optimizeBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 16, color: '#fff' },

  // Results
  results: { marginTop: Spacing.sm },
  resultsTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },

  // Split card
  splitCard: { marginBottom: Spacing.md, padding: Spacing.md, borderWidth: 1, borderColor: '#A8D5B8', backgroundColor: '#F0F9F4' },
  splitHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 6 },
  splitTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: Colors.text.primary },
  splitTotal: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 18, color: Colors.accent.green, marginBottom: 4 },
  splitDetail: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, lineHeight: 18, marginBottom: 4 },
  splitSaving: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: Colors.accent.green },

  // Store cards
  storeCard: { marginBottom: Spacing.xs, padding: Spacing.sm },
  cheapestCard: { borderWidth: 1, borderColor: Colors.accent.green },
  storeRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  storeLeft: { flex: 1, gap: 4 },
  storeStats: { flexDirection: 'row', gap: 8, marginTop: 2 },
  storeAvail: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary },
  storeMissing: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: '#E85D3A' },
  storeRight: { alignItems: 'flex-end' },
  storePrice: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 20, color: Colors.text.primary },
  cheapestPrice: { color: Colors.accent.green },
  cheapestLabel: { fontFamily: 'DMSans_600SemiBold', fontSize: 10, color: Colors.accent.green, marginTop: 2 },
  savingLabel: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.accent.green, marginTop: 2 },

  noResultCard: { padding: Spacing.md },
  noResultText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center' },

  // Empty state
  emptyState: { alignItems: 'center', paddingTop: 40 },
  emptyEmoji: { fontSize: 48, marginBottom: Spacing.md },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 20, color: Colors.text.primary, marginBottom: Spacing.xs },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center', paddingHorizontal: Spacing.xl },
});
