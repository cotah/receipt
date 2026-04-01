import React, { useEffect, useState } from 'react';
import { View, Text, Pressable, StyleSheet, RefreshControl, Modal, FlatList, LayoutAnimation, UIManager, Platform } from 'react-native';

if (Platform.OS === 'android' && UIManager.setLayoutAnimationEnabledExperimental) {
  UIManager.setLayoutAnimationEnabledExperimental(true);
}
import { SafeAreaView } from 'react-native-safe-area-context';

import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import { FlashList } from '@shopify/flash-list';
import ReceiptCard from '../../components/receipts/ReceiptCard';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { STORE_NAMES } from '../../constants/stores';
import { useReceipts } from '../../hooks/useReceipts';


const FILTER_OPTIONS = ['All', ...STORE_NAMES];

export default function HistoryScreen() {
  const router = useRouter();
  const { receipts, isLoading, pagination, fetchReceipts } = useReceipts();
  const [selectedStore, setSelectedStore] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [pickerVisible, setPickerVisible] = useState(false);

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

  const handleSelect = (store: string) => {
    setSelectedStore(store === 'All' ? null : store);
    setPickerVisible(false);
  };

  

  return (
    <>
    <SafeAreaView style={styles.container}>
      <View style={styles.headerRow}>
        <Text style={styles.title}>History</Text>
        <Pressable onPress={() => setPickerVisible(true)} style={styles.dropdownBtn}>
          <Text style={styles.dropdownText}>{selectedStore ?? 'All Stores'}</Text>
          <Feather name="chevron-down" size={16} color={Colors.text.secondary} />
        </Pressable>
      </View>

      {/* Store picker modal */}
      <Modal visible={pickerVisible} transparent animationType="fade" onRequestClose={() => setPickerVisible(false)}>
        <Pressable style={styles.overlay} onPress={() => setPickerVisible(false)}>
          <View style={styles.pickerCard}>
            <Text style={styles.pickerTitle}>Filter by store</Text>
            <FlatList
              data={FILTER_OPTIONS}
              keyExtractor={(item) => item}
              renderItem={({ item }) => {
                const isActive = item === 'All' ? !selectedStore : item === selectedStore;
                return (
                  <Pressable onPress={() => handleSelect(item)} style={[styles.pickerItem, isActive && styles.pickerItemActive]}>
                    <Text style={[styles.pickerItemText, isActive && styles.pickerItemTextActive]}>{item}</Text>
                    {isActive && <Feather name="check" size={16} color={'#7DDFAA'} />}
                  </Pressable>
                );
              }}
            />
          </View>
        </Pressable>
      </Modal>

      {receipts.length === 0 && !isLoading ? (
        <View style={styles.empty}>
          <Text style={styles.emptyTitle}>No receipts yet</Text>
          <Text style={styles.emptyText}>Scan your first receipt to get started!</Text>
        </View>
      ) : (
        <FlatList
          data={receipts}
          keyExtractor={(item) => item.id}
          renderItem={({ item }) => (
            <View style={{ paddingHorizontal: Spacing.md }}>
              <ReceiptCard {...item} onPress={() => router.push(`/receipt/${item.id}`)} />
            </View>
          )}
          onEndReached={loadMore}
          onEndReachedThreshold={0.5}
          refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor={'#7DDFAA'} />}
        />
      )}
    </SafeAreaView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  headerRow: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingHorizontal: Spacing.md,
    paddingTop: Spacing.md,
    paddingBottom: Spacing.sm,
  },
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: '#FFFFFF' },
  dropdownBtn: {
    flexDirection: 'row',
    alignItems: 'center',
    gap: 4,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    borderRadius: 9999,
    backgroundColor: Colors.surface.card,
  },
  dropdownText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.secondary },
  overlay: {
    flex: 1,
    backgroundColor: 'rgba(0,0,0,0.4)',
    justifyContent: 'center',
    alignItems: 'center',
    padding: Spacing.xl,
  },
  pickerCard: {
    width: '100%',
    maxWidth: 320,
    backgroundColor: Colors.surface.card,
    borderRadius: 16,
    padding: Spacing.md,
    maxHeight: 400,
  },
  pickerTitle: {
    fontFamily: 'DMSans_700Bold',
    fontSize: 16,
    color: Colors.text.primary,
    marginBottom: Spacing.md,
    textAlign: 'center',
  },
  pickerItem: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    alignItems: 'center',
    paddingVertical: 12,
    paddingHorizontal: Spacing.md,
    borderRadius: 10,
    marginBottom: 2,
  },
  pickerItemActive: {
    backgroundColor: Colors.primary.pale,
  },
  pickerItemText: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 15,
    color: Colors.text.primary,
  },
  pickerItemTextActive: {
    color: '#7DDFAA',
    fontFamily: 'DMSans_700Bold',
  },
  empty: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: Spacing.xxl },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, textAlign: 'center' },
});
