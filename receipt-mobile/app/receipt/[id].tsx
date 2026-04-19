import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, Image, Pressable, StyleSheet, Alert, Modal, Dimensions, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import StoreTag from '../../components/prices/StoreTag';
import ProductList from '../../components/receipts/ProductList';
import Skeleton from '../../components/ui/Skeleton';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing, BorderRadius } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';
import { formatReceiptDate } from '../../utils/formatDate';
import { useReceipts } from '../../hooks/useReceipts';
import api from '../../services/api';

interface NeedsWeightItem {
  id: string;
  name: string;
  price: number;
}

const WEIGHT_PRESETS = ['100g', '250g', '500g', '1kg', '1.5kg', '1L', '2L'];

export default function ReceiptDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { currentReceipt, isLoading, fetchReceiptDetail, deleteReceipt, clearCurrent } = useReceipts();
  const [imageModalVisible, setImageModalVisible] = useState(false);
  const [needsWeight, setNeedsWeight] = useState<NeedsWeightItem[]>([]);
  const [weights, setWeights] = useState<Record<string, string>>({});
  const [weightDismissed, setWeightDismissed] = useState(false);
  const [savingWeights, setSavingWeights] = useState(false);

  useEffect(() => {
    if (id) {
      fetchReceiptDetail(id);
      // Check if items need weight confirmation
      api.get(`/receipts/${id}/needs-weight`)
        .then(({ data }) => {
          if (data.items?.length > 0) {
            setNeedsWeight(data.items);
          }
        })
        .catch(() => {});
    }
    return () => clearCurrent();
  }, [id]);

  const handleWeightChange = (itemId: string, value: string) => {
    setWeights(prev => ({ ...prev, [itemId]: value }));
  };

  const handleWeightPreset = (itemId: string, preset: string) => {
    setWeights(prev => ({ ...prev, [itemId]: preset }));
  };

  const handleConfirmSingleWeight = async (itemId: string) => {
    const weight = (weights[itemId] || '').trim();
    if (!weight) return;
    setSavingWeights(true);
    try {
      await api.patch(`/receipts/${id}/confirm-weights`, {
        items: [{ item_id: itemId, weight }],
      });
      // Remove this item from the list
      setNeedsWeight(prev => prev.filter(i => i.id !== itemId));
      setWeights(prev => { const n = { ...prev }; delete n[itemId]; return n; });
      // Refresh receipt to show updated name
      if (id) fetchReceiptDetail(id);
    } catch {
      Alert.alert('Error', 'Could not save weight');
    } finally {
      setSavingWeights(false);
    }
  };

  const handleDelete = () => {
    Alert.alert('Delete Receipt', 'Are you sure you want to delete this receipt?', [
      { text: 'Cancel', style: 'cancel' },
      {
        text: 'Delete',
        style: 'destructive',
        onPress: async () => {
          if (id) {
            await deleteReceipt(id);
            router.back();
          }
        },
      },
    ]);
  };

  if (isLoading || !currentReceipt) {
    return (
      <SafeAreaView style={styles.container}>
        <View style={styles.skeletons}>
          <Skeleton width="60%" height={24} />
          <Skeleton width="40%" height={16} style={{ marginTop: 8 }} />
          <Skeleton width="100%" height={200} style={{ marginTop: 24 }} />
        </View>
      </SafeAreaView>
    );
  }

  const r = currentReceipt;

  return (
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {/* Header */}
        <Pressable onPress={() => router.back()} style={styles.back}>
          <Feather name="arrow-left" size={24} color={Colors.text.primary} />
        </Pressable>

        <View style={styles.header}>
          <StoreTag storeName={r.store_name} size="lg" />
          <Text style={styles.date}>{formatReceiptDate(r.purchased_at)}</Text>
        </View>

        {/* Total */}
        <Card variant="elevated" style={styles.totalCard}>
          <Text style={styles.totalLabel}>Total</Text>
          <Text style={styles.totalAmount}>{formatCurrency(r.total_amount)}</Text>
          {r.subtotal && r.discount_total > 0 && (
            <View style={styles.breakdown}>
              <View style={styles.breakdownRow}>
                <Text style={styles.breakdownLabel}>Subtotal</Text>
                <Text style={styles.breakdownValue}>{formatCurrency(r.subtotal)}</Text>
              </View>
              <View style={styles.breakdownRow}>
                <Text style={[styles.breakdownLabel, { color: '#7DDFAA' }]}>Discount</Text>
                <Text style={[styles.breakdownValue, { color: '#7DDFAA' }]}>-{formatCurrency(r.discount_total)}</Text>
              </View>
            </View>
          )}
        </Card>

        {/* Weight confirmation — each product confirms independently */}
        {needsWeight.length > 0 && !weightDismissed && (
          <Card variant="accent" style={styles.weightCard}>
            <View style={styles.weightHeader}>
              <Feather name="info" size={18} color={'#7DDFAA'} />
              <Text style={styles.weightTitle}>Confirm product sizes</Text>
              <Pressable onPress={() => setWeightDismissed(true)} style={{ marginLeft: 'auto' }}>
                <Feather name="x" size={18} color={Colors.text.tertiary} />
              </Pressable>
            </View>
            <Text style={styles.weightDesc}>
              For better price comparisons, confirm the weight or volume:
            </Text>

            {needsWeight.map((item) => (
              <View key={item.id} style={styles.weightItem}>
                <View style={styles.weightItemHeader}>
                  <Text style={styles.weightItemName} numberOfLines={1}>{item.name}</Text>
                  <Text style={styles.weightItemPrice}>{formatCurrency(item.price)}</Text>
                </View>
                <View style={styles.weightPresets}>
                  {WEIGHT_PRESETS.map((preset) => (
                    <Pressable
                      key={preset}
                      onPress={() => handleWeightPreset(item.id, preset)}
                      style={[
                        styles.presetBtn,
                        weights[item.id] === preset && styles.presetBtnActive,
                      ]}
                    >
                      <Text style={[
                        styles.presetBtnText,
                        weights[item.id] === preset && styles.presetBtnTextActive,
                      ]}>{preset}</Text>
                    </Pressable>
                  ))}
                </View>
                <View style={styles.weightInputRow}>
                  <TextInput
                    style={styles.weightInput}
                    placeholder="Or type: 500g, 1kg, 1L..."
                    placeholderTextColor={Colors.text.tertiary}
                    value={weights[item.id] || ''}
                    onChangeText={(v) => handleWeightChange(item.id, v)}
                    autoCapitalize="none"
                  />
                  <Pressable
                    onPress={() => handleConfirmSingleWeight(item.id)}
                    disabled={!weights[item.id]?.trim() || savingWeights}
                    style={[
                      styles.confirmItemBtn,
                      (!weights[item.id]?.trim()) && { opacity: 0.4 },
                    ]}
                  >
                    <Feather name="check" size={16} color="#FFF" />
                  </Pressable>
                  <Pressable
                    onPress={() => setNeedsWeight(prev => prev.filter(i => i.id !== item.id))}
                    style={styles.skipItemBtn}
                  >
                    <Text style={styles.skipItemBtnText}>Skip</Text>
                  </Pressable>
                </View>
              </View>
            ))}
          </Card>
        )}

        {/* Items */}
        <Text style={styles.sectionTitle}>Products ({r.items.length})</Text>
        <ProductList items={r.items} showComparison />

        {/* Receipt images (swipe for multi-photo) */}
        {(r.image_urls?.length > 0 || r.image_url) && (
          <View style={styles.imageSection}>
            <Text style={styles.sectionTitle}>
              Receipt Image{r.image_urls?.length > 1 ? `s (${r.image_urls.length})` : ''}
            </Text>
            {r.image_urls?.length > 1 ? (
              <ScrollView
                horizontal
                pagingEnabled
                showsHorizontalScrollIndicator={false}
                style={styles.imageScroll}
              >
                {r.image_urls.map((url: string, idx: number) => (
                  <Pressable key={idx} onPress={() => setImageModalVisible(true)}>
                    <Image
                      source={{ uri: url }}
                      style={[styles.receiptImage, { width: Dimensions.get('window').width - 32 }]}
                      resizeMode="contain"
                    />
                    <View style={styles.imageCounter}>
                      <Text style={styles.imageCounterText}>{idx + 1}/{r.image_urls.length}</Text>
                    </View>
                  </Pressable>
                ))}
              </ScrollView>
            ) : (
              <Pressable onPress={() => setImageModalVisible(true)}>
                <Image source={{ uri: r.image_url ?? undefined }} style={styles.receiptImage} resizeMode="contain" />
                <View style={styles.expandHint}>
                  <Feather name="maximize-2" size={14} color="#FFF" />
                  <Text style={styles.expandHintText}>Tap to expand</Text>
                </View>
              </Pressable>
            )}
          </View>
        )}

        {/* Fullscreen image modal */}
        {(r.image_urls?.length > 0 || r.image_url) && (
          <Modal visible={imageModalVisible} transparent animationType="fade" onRequestClose={() => setImageModalVisible(false)}>
            <View style={styles.imageModal}>
              <Pressable style={styles.imageModalClose} onPress={() => setImageModalVisible(false)}>
                <Feather name="x" size={28} color="#FFF" />
              </Pressable>
              <ScrollView horizontal pagingEnabled showsHorizontalScrollIndicator={false}>
                {(r.image_urls?.length > 0 ? r.image_urls : [r.image_url].filter(Boolean) as string[]).map((url: string, idx: number) => (
                  <Image
                    key={idx}
                    source={{ uri: url }}
                    style={styles.imageModalImg}
                    resizeMode="contain"
                  />
                ))}
              </ScrollView>
            </View>
          </Modal>
        )}

        {/* Delete */}
        <View style={styles.deleteSection}>
          <Button title="Delete Receipt" onPress={handleDelete} variant="danger" icon="trash-2" fullWidth />
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  content: { padding: Spacing.md, paddingBottom: Spacing.xxl },
  skeletons: { padding: Spacing.md },
  back: { marginBottom: Spacing.sm },
  header: { marginBottom: Spacing.md },
  headerRow: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  storeName: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: '#FFFFFF' },
  date: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, marginTop: 4 },
  totalCard: { alignItems: 'center', marginBottom: Spacing.lg, backgroundColor: 'rgba(80,200,120,0.12)', borderRadius: 24, paddingVertical: 28 },
  totalLabel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: 'rgba(255,255,255,0.65)' },
  totalAmount: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 40, color: Colors.accent.amber },
  breakdown: { marginTop: Spacing.sm, width: '100%', paddingHorizontal: 20 },
  breakdownRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 3 },
  breakdownLabel: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: 'rgba(255,255,255,0.5)' },
  breakdownValue: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 14, color: 'rgba(255,255,255,0.9)' },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm, marginTop: Spacing.md },
  imageSection: { marginTop: Spacing.lg },
  imageScroll: { marginHorizontal: -Spacing.md },
  receiptImage: { width: '100%', height: 400, borderRadius: 12, backgroundColor: Colors.surface.alt },
  imageCounter: {
    position: 'absolute', top: 12, right: 12,
    backgroundColor: 'rgba(0,0,0,0.5)', paddingHorizontal: 10, paddingVertical: 4, borderRadius: 12,
  },
  imageCounterText: { fontFamily: 'DMSans_600SemiBold', fontSize: 12, color: '#FFF' },
  expandHint: {
    position: 'absolute', bottom: 12, right: 12,
    flexDirection: 'row', alignItems: 'center', gap: 4,
    backgroundColor: 'rgba(0,0,0,0.5)', paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8,
  },
  expandHintText: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: '#FFF' },
  imageModal: {
    flex: 1, backgroundColor: '#000', justifyContent: 'center', alignItems: 'center',
  },
  imageModalClose: {
    position: 'absolute', top: 60, right: 20, zIndex: 10,
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.2)',
    alignItems: 'center', justifyContent: 'center',
  },
  imageModalImg: {
    width: Dimensions.get('window').width,
    height: Dimensions.get('window').height * 0.85,
  },
  deleteSection: { marginTop: Spacing.xl, alignItems: 'center' },

  // Weight confirmation styles
  weightCard: {
    marginTop: Spacing.md, borderRadius: BorderRadius.md,
  },
  weightHeader: { flexDirection: 'row', alignItems: 'center', gap: 8, marginBottom: 4 },
  weightTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: '#FFFFFF' },
  weightDesc: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, marginBottom: 12 },
  weightItem: { marginBottom: 14, paddingBottom: 14, borderBottomWidth: 1, borderBottomColor: 'rgba(0,0,0,0.06)' },
  weightItemHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 },
  weightItemName: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary, flex: 1 },
  weightItemPrice: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 14, color: Colors.accent.amber, marginLeft: 8 },
  weightPresets: { flexDirection: 'row', flexWrap: 'wrap', gap: 6, marginBottom: 8 },
  presetBtn: {
    paddingHorizontal: 12, paddingVertical: 6, borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.08)', borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
  },
  presetBtnActive: { backgroundColor: 'rgba(80,200,120,0.20)', borderColor: 'rgba(80,200,120,0.25)' },
  presetBtnText: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.text.secondary },
  presetBtnTextActive: { color: '#FFF' },
  weightInput: {
    flex: 1, fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.primary,
    borderWidth: 1, borderColor: Colors.surface.border, borderRadius: BorderRadius.sm,
    paddingHorizontal: 12, paddingVertical: 8, backgroundColor: 'rgba(255,255,255,0.08)',
  },
  weightInputRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  confirmItemBtn: {
    width: 36, height: 36, borderRadius: 18,
    backgroundColor: 'rgba(80,200,120,0.20)',
    alignItems: 'center', justifyContent: 'center',
  },
  skipItemBtn: { paddingVertical: 8, paddingHorizontal: 4 },
  skipItemBtnText: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary },
});
