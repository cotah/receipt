import React, { useEffect, useState } from 'react';
import { View, Text, Pressable, StyleSheet, RefreshControl } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { GestureDetector } from 'react-native-gesture-handler';
import { useRouter } from 'expo-router';
import { FlashList } from '@shopify/flash-list';
import ReceiptCard from '../../components/receipts/ReceiptCard';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { STORE_NAMES } from '../../constants/stores';
import { useReceipts } from '../../hooks/useReceipts';
import { useTabSwipe } from '../../hooks/useTabSwipe';

export default function HistoryScreen() {
  const router = useRouter();
  const { receipts, isLoading, pagination, fetchReceipts } = useReceipts();
  const [selectedStore, setSelectedStore] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    fetchReceipts(1, selectedStore ?? undefined);
  }, [selectedStore]);

  const onRefresh = async () => {
    setRefreshing(true);
    await fetchReceipts(1, selectedStore ?? undefined);
    setRefreshing(false);
  };

  const loadMore = () => {
    if (pagination.page < pagination.totalPages && !isLoading) {
      fetchReceipts(pagination.page + 1, selectedStore ?? undefined);
    }
  };

  const swipe = useTabSwipe(1);

  return (
    <GestureDetector gesture={swipe}>
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>History</Text>

      {/* Store filter — pill grid (max 2 lines) */}
      <View style={styles.filters}>
        <Pressable onPress={() => setSelectedStore(null)} style={[styles.filterChip, !selectedStore && styles.filterActive]}>
          <Text style={[styles.filterText, !selectedStore && styles.filterTextActive]}>All</Text>
        </Pressable>
        {STORE_NAMES.map((store) => (
          <Pressable key={store} onPress={() => setSelectedStore(store === selectedStore ? null : store)} style={[styles.filterChip, store === selectedStore && styles.filterActive]}>
            <Text style={[styles.filterText, store === selectedStore && styles.filterTextActive]}>{store}</Text>
          </Pressable>
        ))}
      </View>

      {receipts.length === 0 && !isLoading ? (
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>No receipts yet</Text>
          <Text style={styles.emptyText}>Scan your first receipt to get started!</Text>
        </View>
      ) : (
        <FlashList
          data={receipts}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <View style={{ paddingHorizontal: Spacing.md }}>
              <ReceiptCard {...item} onPress={() => router.push(`/receipt/${item.id}`)} />
            </View>
          )}
          estimatedItemSize={90}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={Colors.primary.default} />}
        />
      )}
    </SafeAreaView>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: Colors.primary.dark, paddingHorizontal: Spacing.md, paddingTop: Spacing.md },
  filters: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    gap: Spacing.sm,
    paddingHorizontal: Spacing.md,
    marginVertical: Spacing.md,
    maxHeight: 88,
    overflow: 'hidden',
  },
  filterChip: {
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: 9999,
    backgroundColor: Colors.surface.card,
  },
  filterActive: { backgroundColor: Colors.primary.dark },
  filterText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.secondary },
  filterTextActive: { color: Colors.text.inverse },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xxl },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center' },
});
