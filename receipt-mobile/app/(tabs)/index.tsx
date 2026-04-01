import React, { useEffect, useState, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Alert, ActivityIndicator } from 'react-native';
import * as Location from 'expo-location';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useFocusEffect } from 'expo-router';

import { useRouter } from 'expo-router';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import { Feather } from '@expo/vector-icons';
import ProfileAvatar from '../../components/ui/ProfileAvatar';
import ReceiptCard from '../../components/receipts/ReceiptCard';
import { Colors, Shadows } from '../../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../../constants/typography';

import { formatCurrency, formatCurrencyChange } from '../../utils/formatCurrency';
import { useAuthStore } from '../../stores/authStore';
import { useReceipts } from '../../hooks/useReceipts';
import { useProducts } from '../../hooks/useProducts';
import { useAlertStore } from '../../stores/alertStore';
import api from '../../services/api';

export default function HomeScreen() {
  const router = useRouter();
  const profile = useAuthStore((s) => s.profile);
  const setProfile = useAuthStore((s) => s.setProfile);
  const { receipts, fetchReceipts } = useReceipts();
  const { runningLow, fetchRunningLow } = useProducts();
  const { unreadCount, fetchAlerts } = useAlertStore();
  const [locationChecked, setLocationChecked] = useState(false);
  const [savings, setSavings] = useState<any>(null);
  const [priceMemories, setPriceMemories] = useState<any[]>([]);
  const [addedToList, setAddedToList] = useState<Map<string, string>>(new Map());

  const toggleShoppingList = async (name: string, store: string, price: number) => {
    const key = `${name}-${store}`;
    const existingId = addedToList.get(key);
    if (existingId) {
      try {
        if (existingId !== 'exists') {
          await api.delete(`/shopping-list/${existingId}`);
        }
        setAddedToList(prev => { const n = new Map(prev); n.delete(key); return n; });
      } catch {
        setAddedToList(prev => { const n = new Map(prev); n.delete(key); return n; });
      }
    } else {
      try {
        const { data } = await api.post('/shopping-list/add', {
          product_name: name, store_name: store, unit_price: price, source: 'memory',
        });
        if (data.status === 'exists') return;
        const itemId = data.item?.id;
        if (itemId) {
          setAddedToList(prev => new Map(prev).set(key, itemId));
        }
      } catch {}
    }
  };

  useEffect(() => {
    fetchReceipts(1);
    fetchRunningLow();
    fetchAlerts();
    // Fetch savings + price memory
    api.get('/prices/savings-summary').then(({ data }) => setSavings(data)).catch(() => {});
    api.get('/prices/price-memory?limit=3').then(({ data }) => setPriceMemories(data.memories || [])).catch(() => {});
  }, []);

  // Refetch receipts every time Home gets focus (catches status changes like failed duplicates)
  useFocusEffect(
    useCallback(() => {
      fetchReceipts(1);
      fetchAlerts();
    }, [])
  );

  // Auto-detect location on first login if home_area is empty
  // Delay 1s to let profile fully load (especially for new Google accounts)
  useEffect(() => {
    if (!profile?.id || profile.home_area || locationChecked) return;
    setLocationChecked(true);

    const timer = setTimeout(async () => {
      const { status } = await Location.requestForegroundPermissionsAsync();
      if (status !== 'granted') return;

      try {
        const loc = await Location.getCurrentPositionAsync({ accuracy: Location.Accuracy.Balanced });
        const [geo] = await Location.reverseGeocodeAsync(loc.coords);
        const area = geo?.city || geo?.subregion || geo?.region || '';
        if (!area) return;

        Alert.alert(
          'Location detected',
          `We detected you're in ${area} — is that correct?`,
          [
            { text: 'Change', style: 'cancel' },
            {
              text: 'Yes',
              onPress: async () => {
                const { supabase } = require('../../services/supabase');
                await supabase.from('profiles').update({ home_area: area }).eq('id', profile.id);
                setProfile({ ...profile, home_area: area });
              },
            },
          ]
        );
      } catch {
        // Location failed silently
      }
    }, 1000);

    return () => clearTimeout(timer);
  }, [profile?.id, profile?.home_area]);

  const name = profile?.full_name?.split(' ')[0] ?? '';

  // Calculate month total from receipts
  const now = new Date();
  const monthReceipts = receipts.filter((r) => {
    const d = new Date(r.purchased_at);
    return d.getMonth() === now.getMonth() && d.getFullYear() === now.getFullYear();
  });
  const monthTotal = monthReceipts.reduce((s, r) => s + r.total_amount, 0);
  const monthDiscounts = monthReceipts.reduce((s, r) => s + (r.discount_total ?? 0), 0);

  

  return (
    <>
    <SafeAreaView style={styles.container}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.scroll}>
        {/* Header */}
        <View style={styles.headerRow}>
          <Text style={styles.greeting}>Hi, {name}</Text>
          <View style={styles.headerRight}>
            <Pressable onPress={() => router.push('/alerts')} style={styles.bellWrap}>
              <Feather name="bell" size={22} color={Colors.text.primary} />
              {unreadCount > 0 && (
                <View style={styles.bellBadge}>
                  <Text style={styles.bellBadgeText}>{unreadCount > 9 ? '9+' : unreadCount}</Text>
                </View>
              )}
            </Pressable>
            <ProfileAvatar size={32} />
          </View>
        </View>

        {/* Main card */}
        <Card variant="elevated" style={styles.mainCard}>
          <Text style={styles.mainLabel}>Spent this month</Text>
          <Text style={styles.mainAmount}>{formatCurrency(monthTotal)}</Text>
          <Text style={styles.mainSub}>{monthReceipts.length} shops</Text>
        </Card>

        {/* Stats row */}
        <View style={styles.statsRow}>
          <Card style={styles.statCard}>
            <Text style={styles.statValue}>{monthReceipts.length}</Text>
            <Text style={styles.statLabel}>Shops</Text>
          </Card>
          <Card style={styles.statCard}>
            <Text style={styles.statValue}>{formatCurrency(monthDiscounts)}</Text>
            <Text style={styles.statLabel}>Discounts</Text>
          </Card>
          <Card style={styles.statCard}>
            <Text style={[styles.statValue, { color: savings?.attributed_savings > 0 ? Colors.accent.green : Colors.text.tertiary }]}>
              {formatCurrency(savings?.attributed_savings ?? 0)}
            </Text>
            <Text style={styles.statLabel}>Saved</Text>
            {savings?.attributed_savings > 0 && (
              <Text style={styles.comingSoon}>with SmartDocket</Text>
            )}
          </Card>
        </View>

        {/* My Usual Shop shortcut */}
        <Pressable onPress={() => router.push('/usual-shop')} style={styles.usualShopBtn}>
          <View style={styles.usualShopLeft}>
            <Feather name="shopping-bag" size={18} color={Colors.primary.default} />
            <View>
              <Text style={styles.usualShopTitle}>My usual shop</Text>
              <Text style={styles.usualShopSub}>See where your regulars are cheapest</Text>
            </View>
          </View>
          <Feather name="chevron-right" size={18} color={Colors.text.tertiary} />
        </Pressable>

        {/* Running Low */}
        {runningLow.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>Running Low</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: Spacing.sm }}>
              {runningLow.slice(0, 5).map((item) => (
                <Card key={item.product_name} style={styles.lowCard}>
                  <Text style={styles.lowName}>{item.product_name}</Text>
                  <Badge text={`${item.overdue_by_days}d overdue`} variant={item.urgency === 'high' ? 'danger' : 'warning'} size="sm" />
                  {item.best_current_price && (
                    <Text style={styles.lowPrice}>{formatCurrency(item.best_current_price.price)} at {item.best_current_price.store}</Text>
                  )}
                </Card>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Price Memory — products you bought that are cheaper elsewhere */}
        {priceMemories.length > 0 && (
          <View style={styles.section}>
            <Text style={styles.sectionTitle}>💰 Price Memory</Text>
            {priceMemories.map((m, i) => (
              <Card key={i} style={styles.memoryCard}>
                <Text style={styles.memoryProduct} numberOfLines={1}>{m.product_name}</Text>
                <Text style={styles.memoryDetail}>
                  You paid {formatCurrency(m.paid_price)} at {m.paid_store}
                </Text>
                <View style={styles.memoryRow}>
                  <Text style={styles.memoryNow}>
                    Now {formatCurrency(m.current_price)} at {m.current_store}
                  </Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <View style={styles.savingBadge}>
                      <Text style={styles.savingBadgeText}>Save {formatCurrency(m.saving)}</Text>
                    </View>
                    <Pressable
                      onPress={() => toggleShoppingList(m.product_name, m.current_store, m.current_price)}
                      style={styles.memoryAddBtn}
                    >
                      <Text style={styles.memoryAddBtnText}>
                        {addedToList.has(`${m.product_name}-${m.current_store}`) ? '✓' : '+'}
                      </Text>
                    </Pressable>
                  </View>
                </View>
              </Card>
            ))}
            <Pressable onPress={() => router.push('/(tabs)/prices')}>
              <Text style={styles.seeAll}>See all price comparisons →</Text>
            </Pressable>
          </View>
        )}

        {/* Best saving highlight — only if ratio is < 2x (avoids false matches) */}
        {savings?.best_saving && priceMemories.length === 0 && 
         savings.best_saving.paid > 0 && savings.best_saving.now > 0 &&
         (savings.best_saving.paid / savings.best_saving.now) < 2.0 &&
         savings.best_saving.saving > 0.20 && (
          <Card style={styles.bestSavingCard}>
            <Text style={styles.bestSavingTitle}>💡 Best saving right now</Text>
            <Text style={styles.bestSavingText}>
              {savings.best_saving.product} — you paid {formatCurrency(savings.best_saving.paid)} at {savings.best_saving.paid_store}, 
              now {formatCurrency(savings.best_saving.now)} at {savings.best_saving.now_store}
            </Text>
          </Card>
        )}

        {/* Shopping List shortcut */}
        <Pressable style={styles.shoppingListBar} onPress={() => router.push('/shopping-list')}>
          <View style={styles.shoppingListLeft}>
            <Feather name="shopping-cart" size={18} color={Colors.primary.default} />
            <Text style={styles.shoppingListText}>Shopping List</Text>
          </View>
          <Feather name="chevron-right" size={18} color={Colors.text.tertiary} />
        </Pressable>

        {/* This Month's Receipts */}
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>This Month</Text>
          {monthReceipts.length > 0 ? (
            monthReceipts.slice(0, 3).map((r) => (
              <ReceiptCard
                key={r.id}
                {...r}
                onPress={() => router.push(`/receipt/${r.id}`)}
              />
            ))
          ) : (
            <Card style={styles.emptyMonth}>
              <Text style={styles.emptyMonthText}>No receipts yet this month</Text>
              <Text style={styles.emptyMonthSub}>Scan your first receipt to start tracking</Text>
            </Card>
          )}
        </View>
      </ScrollView>

    </SafeAreaView>
    </>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  scroll: { padding: Spacing.md, paddingBottom: 100 },
  headerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: Spacing.lg },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 16 },
  bellWrap: { position: 'relative', padding: 6, backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 14 },
  bellBadge: {
    position: 'absolute', top: 0, right: -2,
    minWidth: 18, height: 18, borderRadius: 9,
    backgroundColor: '#E53E3E',
    alignItems: 'center', justifyContent: 'center',
    paddingHorizontal: 4,
    borderWidth: 2, borderColor: Colors.surface.background,
  },
  bellBadgeText: { fontFamily: 'DMSans_700Bold', fontSize: 9, color: '#FFF' },
  greeting: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: Colors.primary.dark },
  mainCard: {
    marginBottom: Spacing.md, alignItems: 'center', paddingVertical: 28,
    backgroundColor: Colors.primary.dark, borderRadius: 24,
  },
  mainLabel: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: 'rgba(255,255,255,0.65)' },
  mainAmount: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 42, color: Colors.accent.amber, marginVertical: 6 },
  mainSub: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.5)' },
  statsRow: { flexDirection: 'row', gap: Spacing.sm, marginBottom: Spacing.md },
  statCard: { flex: 1, alignItems: 'center', paddingVertical: Spacing.md, borderRadius: 20 },
  usualShopBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: Colors.surface.card, borderRadius: BorderRadius.lg,
    padding: Spacing.md, marginBottom: Spacing.lg,
    borderWidth: 1, borderColor: Colors.surface.border,
  },
  usualShopLeft: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  usualShopTitle: { fontFamily: Fonts.bodyBold, fontSize: 14, color: Colors.text.primary },
  usualShopSub: { fontFamily: Fonts.body, fontSize: 12, color: Colors.text.secondary },
  statValue: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 20, color: Colors.text.primary },
  statLabel: { fontFamily: 'DMSans_500Medium', fontSize: 11, color: Colors.text.secondary, marginTop: 4, textTransform: 'uppercase', letterSpacing: 0.5 },
  comingSoon: { fontFamily: 'DMSans_400Regular', fontSize: 9, color: Colors.text.tertiary, marginTop: 1 },
  section: { marginBottom: Spacing.lg },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: Spacing.sm },
  emptyMonth: { padding: Spacing.md, alignItems: 'center' as const },
  emptyMonthText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.secondary },
  emptyMonthSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, marginTop: 4 },
  lowCard: { width: 140, padding: Spacing.sm, gap: 4 },
  lowName: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary },
  lowPrice: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 11, color: Colors.accent.green },

  // Price Memory
  memoryCard: { marginBottom: Spacing.xs, padding: Spacing.sm },
  memoryProduct: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  memoryDetail: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, marginTop: 2 },
  memoryRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 4 },
  memoryNow: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.primary },
  savingBadge: { backgroundColor: Colors.accent.greenSoft, borderRadius: 10, paddingHorizontal: 10, paddingVertical: 4 },
  savingBadgeText: { fontFamily: 'DMSans_700Bold', fontSize: 12, color: Colors.accent.green },
  memoryAddBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: Colors.primary.default, alignItems: 'center', justifyContent: 'center',
    ...Shadows.card,
  },
  memoryAddBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: '#fff', lineHeight: 18 },
  seeAll: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: Colors.primary.default, marginTop: Spacing.sm, textAlign: 'center' },
  bestSavingCard: {
    marginBottom: Spacing.lg, padding: Spacing.md,
    borderWidth: 1.5, borderColor: Colors.accent.green, borderRadius: 20,
    backgroundColor: Colors.accent.greenSoft,
  },
  bestSavingTitle: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: Colors.text.primary, marginBottom: 4 },
  bestSavingText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary, lineHeight: 18 },

  // Shopping list shortcut
  shoppingListBar: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: Colors.surface.card, borderRadius: 20, padding: Spacing.md,
    marginBottom: Spacing.lg,
    ...Shadows.card,
  },
  shoppingListLeft: { flexDirection: 'row', alignItems: 'center', gap: Spacing.sm },
  shoppingListText: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: Colors.text.primary },
});
