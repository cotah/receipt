import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Alert, ActivityIndicator, TextInput, Share } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../components/ui/Card';
import StoreTag from '../components/prices/StoreTag';
import { Colors } from '../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../constants/typography';
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
  const [sharedWith, setSharedWith] = useState<string | null>(null);

  // Sharing state
  const [showShare, setShowShare] = useState(false);
  const [shareCode, setShareCode] = useState<string | null>(null);
  const [joinCode, setJoinCode] = useState('');
  const [isSharing, setIsSharing] = useState(false);

  const fetchList = useCallback(async () => {
    try {
      const { data } = await api.get('/shopping-list');
      setStores(data.stores || []);
      setTotalItems(data.total_items || 0);
      setEstimatedTotal(data.estimated_total || 0);
      setCheckedCount(data.checked_count || 0);
      setSharedWith(data.shared_with || null);
    } catch {
    } finally {
      setIsLoading(false);
    }
  }, []);

  const fetchShareStatus = useCallback(async () => {
    try {
      const { data } = await api.get('/shopping-list/share-status');
      setShareCode(data.share_code || null);
      setSharedWith(data.partner_name || null);
    } catch {}
  }, []);

  const generateShareCode = async () => {
    try {
      const { data } = await api.post('/shopping-list/share');
      setShareCode(data.share_code);
      Share.share({ message: `Join my SmartDocket shopping list! Use code: ${data.share_code}` });
    } catch {
      Alert.alert('Error', 'Could not generate share code');
    }
  };

  const joinList = async () => {
    if (!joinCode.trim()) return;
    setIsSharing(true);
    try {
      const { data } = await api.post('/shopping-list/join', null, { params: { code: joinCode.trim() } });
      setSharedWith(data.shared_with);
      setShowShare(false);
      setJoinCode('');
      fetchList();
      Alert.alert('Linked!', `Now sharing with ${data.shared_with}`);
    } catch (e: any) {
      Alert.alert('Error', e?.response?.data?.detail || 'Invalid code');
    } finally {
      setIsSharing(false);
    }
  };

  const unlinkList = async () => {
    Alert.alert('Stop sharing?', 'You will no longer see each other\'s items.', [
      { text: 'Cancel', style: 'cancel' },
      { text: 'Unlink', style: 'destructive', onPress: async () => {
        try {
          await api.delete('/shopping-list/unlink');
          setSharedWith(null);
          fetchList();
        } catch {}
      }},
    ]);
  };

  useEffect(() => {
    fetchList();
    fetchShareStatus();
    // Safety: never stay loading forever
    const timeout = setTimeout(() => setIsLoading(false), 8000);
    return () => clearTimeout(timeout);
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
        <Pressable onPress={() => setShowShare(!showShare)} hitSlop={12}>
          <Feather name="users" size={22} color={sharedWith ? Colors.primary.default : Colors.text.secondary} />
        </Pressable>
      </View>

      {/* Sharing panel */}
      {showShare && (
        <Card style={styles.sharePanel}>
          {sharedWith ? (
            <View>
              <View style={styles.shareRow}>
                <Feather name="link" size={16} color={Colors.primary.default} />
                <Text style={styles.shareLinked}>Sharing with {sharedWith}</Text>
              </View>
              <Pressable onPress={unlinkList} style={styles.unlinkBtn}>
                <Text style={styles.unlinkText}>Stop sharing</Text>
              </Pressable>
            </View>
          ) : (
            <View style={styles.shareOptions}>
              <Pressable onPress={generateShareCode} style={styles.shareCodeBtn}>
                <Feather name="share-2" size={16} color="#FFF" />
                <Text style={styles.shareCodeBtnText}>
                  {shareCode ? `Code: ${shareCode}` : 'Share my list'}
                </Text>
              </Pressable>
              <Text style={styles.shareOr}>or join someone:</Text>
              <View style={styles.joinRow}>
                <TextInput
                  style={styles.joinInput}
                  placeholder="Enter code"
                  placeholderTextColor={Colors.text.tertiary}
                  value={joinCode}
                  onChangeText={setJoinCode}
                  autoCapitalize="characters"
                  maxLength={8}
                />
                <Pressable
                  onPress={joinList}
                  style={[styles.joinBtn, isSharing && { opacity: 0.5 }]}
                  disabled={isSharing}
                >
                  <Text style={styles.joinBtnText}>Join</Text>
                </Pressable>
              </View>
            </View>
          )}
        </Card>
      )}

      {/* Shared indicator */}
      {sharedWith && !showShare && (
        <View style={styles.sharedBanner}>
          <Feather name="users" size={13} color={Colors.primary.default} />
          <Text style={styles.sharedBannerText}>Shared with {sharedWith}</Text>
        </View>
      )}

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

  // Sharing
  sharePanel: { marginHorizontal: Spacing.md, marginBottom: Spacing.sm, padding: Spacing.md },
  shareRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  shareLinked: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary, flex: 1 },
  unlinkBtn: { marginTop: 8, alignSelf: 'flex-start' },
  unlinkText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: '#C74343' },
  shareOptions: { gap: 8 },
  shareCodeBtn: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: Colors.primary.default, borderRadius: 10,
    paddingHorizontal: 16, paddingVertical: 10, alignSelf: 'flex-start',
  },
  shareCodeBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: '#FFF' },
  shareOr: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary },
  joinRow: { flexDirection: 'row', gap: 8 },
  joinInput: {
    flex: 1, borderWidth: 1, borderColor: Colors.surface.border,
    borderRadius: 10, paddingHorizontal: 12, paddingVertical: 8,
    fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary,
    letterSpacing: 2,
  },
  joinBtn: {
    backgroundColor: Colors.primary.default, borderRadius: 10,
    paddingHorizontal: 20, justifyContent: 'center',
  },
  joinBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: '#FFF' },
  sharedBanner: {
    flexDirection: 'row', alignItems: 'center', gap: 6,
    paddingHorizontal: Spacing.md, paddingVertical: 4,
  },
  sharedBannerText: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.primary.default },
});
