import React, { useEffect } from 'react';
import { View, Text, ScrollView, Image, Pressable, StyleSheet, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useLocalSearchParams, useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';
import Card from '../../components/ui/Card';
import StoreTag from '../../components/prices/StoreTag';
import ProductList from '../../components/receipts/ProductList';
import Skeleton from '../../components/ui/Skeleton';
import Button from '../../components/ui/Button';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';
import { formatReceiptDate } from '../../utils/formatDate';
import { useReceipts } from '../../hooks/useReceipts';

export default function ReceiptDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const router = useRouter();
  const { currentReceipt, isLoading, fetchReceiptDetail, deleteReceipt, clearCurrent } = useReceipts();

  useEffect(() => {
    if (id) fetchReceiptDetail(id);
    return () => clearCurrent();
  }, [id]);

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
          <View style={styles.headerRow}>
            <Text style={styles.storeName}>{r.store_name}</Text>
            <StoreTag storeName={r.store_name} size="md" />
          </View>
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
                <Text style={[styles.breakdownLabel, { color: Colors.accent.green }]}>Discount</Text>
                <Text style={[styles.breakdownValue, { color: Colors.accent.green }]}>-{formatCurrency(r.discount_total)}</Text>
              </View>
            </View>
          )}
        </Card>

        {/* Items */}
        <Text style={styles.sectionTitle}>Products ({r.items.length})</Text>
        <ProductList items={r.items} showComparison />

        {/* Receipt image */}
        {r.image_url && (
          <View style={styles.imageSection}>
            <Text style={styles.sectionTitle}>Receipt Image</Text>
            <Image source={{ uri: r.image_url }} style={styles.receiptImage} resizeMode="contain" />
          </View>
        )}

        {/* Delete */}
        <View style={styles.deleteSection}>
          <Button title="Delete Receipt" onPress={handleDelete} variant="ghost" icon="trash-2" />
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
  storeName: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: Colors.primary.dark },
  date: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary, marginTop: 4 },
  totalCard: { alignItems: 'center', marginBottom: Spacing.lg },
  totalLabel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.text.secondary },
  totalAmount: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 36, color: Colors.accent.amber },
  breakdown: { marginTop: Spacing.sm, width: '100%' },
  breakdownRow: { flexDirection: 'row', justifyContent: 'space-between', paddingVertical: 2 },
  breakdownLabel: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.secondary },
  breakdownValue: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 14, color: Colors.text.primary },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm, marginTop: Spacing.md },
  imageSection: { marginTop: Spacing.lg },
  receiptImage: { width: '100%', height: 400, borderRadius: 12, backgroundColor: Colors.surface.alt },
  deleteSection: { marginTop: Spacing.xl, alignItems: 'center' },
});
