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
    <SafeAreaView style={s.safe}>
      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={s.scroll}>
        {/* Header — glass style */}
        <View style={s.header}>
          <View>
            <Text style={s.greeting}>Good morning</Text>
            <Text style={s.headerName}>{name}</Text>
          </View>
          <View style={s.headerRight}>
            <Pressable onPress={() => router.push('/alerts')} style={s.bellWrap}>
              <Feather name="bell" size={20} color="#FFFFFF" />
              {unreadCount > 0 && (
                <View style={s.bellBadge}>
                  <Text style={s.bellBadgeText}>{unreadCount > 9 ? '9+' : unreadCount}</Text>
                </View>
              )}
            </Pressable>
            <ProfileAvatar size={40} />
          </View>
        </View>

        {/* Main card — Spent this month */}
        <View style={s.mainCard}>
          <Text style={s.mainLabel}>Spent this month</Text>
          <Text style={s.mainAmount}>{formatCurrency(monthTotal)}</Text>
          <Text style={s.mainSub}>{monthReceipts.length} shops</Text>
        </View>

        {/* Stats row */}
        <View style={s.statsRow}>
          <View style={s.statCard}>
            <Text style={s.statValue}>{monthReceipts.length}</Text>
            <Text style={s.statLabel}>Shops</Text>
          </View>
          <View style={s.statCard}>
            <Text style={s.statValue}>{formatCurrency(monthDiscounts)}</Text>
            <Text style={s.statLabel}>Discounts</Text>
          </View>
          <View style={s.statCard}>
            <Text style={[s.statValue, savings?.attributed_savings > 0 && { color: '#7DDFAA' }]}>
              {formatCurrency(savings?.attributed_savings ?? 0)}
            </Text>
            <Text style={s.statLabel}>Saved</Text>
            {savings?.attributed_savings > 0 && (
              <Text style={s.comingSoon}>with SmartDocket</Text>
            )}
          </View>
        </View>

        {/* My Usual Shop shortcut */}
        <Pressable onPress={() => router.push('/usual-shop')} style={s.usualShopBtn}>
          <View style={s.usualShopLeft}>
            <Feather name="shopping-bag" size={18} color="#7DDFAA" />
            <View>
              <Text style={s.usualShopTitle}>My usual shop</Text>
              <Text style={s.usualShopSub}>See where your regulars are cheapest</Text>
            </View>
          </View>
          <Feather name="chevron-right" size={18} color="rgba(255,255,255,0.35)" />
        </Pressable>

        {/* Running Low */}
        {runningLow.length > 0 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Running Low</Text>
            <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }}>
              {runningLow.slice(0, 5).map((item) => (
                <View key={item.product_name} style={s.lowCard}>
                  <Text style={s.lowName}>{item.product_name}</Text>
                  <Badge text={`${item.overdue_by_days}d overdue`} variant={item.urgency === 'high' ? 'danger' : 'warning'} size="sm" />
                  {item.best_current_price && (
                    <Text style={s.lowPrice}>{formatCurrency(item.best_current_price.price)} at {item.best_current_price.store}</Text>
                  )}
                </View>
              ))}
            </ScrollView>
          </View>
        )}

        {/* Price Memory */}
        {priceMemories.length > 0 && (
          <View style={s.section}>
            <Text style={s.sectionTitle}>Price Memory</Text>
            {priceMemories.map((m, i) => (
              <View key={i} style={s.memoryCard}>
                <Text style={s.memoryProduct} numberOfLines={1}>{m.product_name}</Text>
                <Text style={s.memoryDetail}>
                  You paid {formatCurrency(m.paid_price)} at {m.paid_store}
                </Text>
                <View style={s.memoryRow}>
                  <Text style={s.memoryNow}>
                    Now {formatCurrency(m.current_price)} at {m.current_store}
                  </Text>
                  <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                    <View style={s.savingBadge}>
                      <Text style={s.savingBadgeText}>Save {formatCurrency(m.saving)}</Text>
                    </View>
                    <Pressable
                      onPress={() => toggleShoppingList(m.product_name, m.current_store, m.current_price)}
                      style={s.memoryAddBtn}
                    >
                      <Text style={s.memoryAddBtnText}>
                        {addedToList.has(`${m.product_name}-${m.current_store}`) ? '✓' : '+'}
                      </Text>
                    </Pressable>
                  </View>
                </View>
              </View>
            ))}
            <Pressable onPress={() => router.push('/(tabs)/prices')}>
              <Text style={s.seeAll}>See all price comparisons →</Text>
            </Pressable>
          </View>
        )}

        {/* Best saving highlight */}
        {savings?.best_saving && priceMemories.length === 0 && 
         savings.best_saving.paid > 0 && savings.best_saving.now > 0 &&
         (savings.best_saving.paid / savings.best_saving.now) < 2.0 &&
         savings.best_saving.saving > 0.20 && (
          <View style={s.bestSavingCard}>
            <Text style={s.bestSavingTitle}>Best saving right now</Text>
            <Text style={s.bestSavingText}>
              {savings.best_saving.product} — you paid {formatCurrency(savings.best_saving.paid)} at {savings.best_saving.paid_store}, 
              now {formatCurrency(savings.best_saving.now)} at {savings.best_saving.now_store}
            </Text>
          </View>
        )}

        {/* Shopping List shortcut */}
        <Pressable style={s.shoppingListBar} onPress={() => router.push('/shopping-list')}>
          <View style={s.shoppingListLeft}>
            <Feather name="shopping-cart" size={18} color="#7DDFAA" />
            <Text style={s.shoppingListText}>Shopping List</Text>
          </View>
          <Feather name="chevron-right" size={18} color="rgba(255,255,255,0.35)" />
        </Pressable>

        {/* This Month's Receipts */}
        <View style={s.section}>
          <Text style={s.sectionTitle}>This Month</Text>
          {monthReceipts.length > 0 ? (
            monthReceipts.slice(0, 3).map((r) => (
              <ReceiptCard key={r.id} {...r} onPress={() => router.push(`/receipt/${r.id}`)} />
            ))
          ) : (
            <View style={s.emptyMonth}>
              <Text style={s.emptyMonthText}>No receipts yet this month</Text>
              <Text style={s.emptyMonthSub}>Scan your first receipt to start tracking</Text>
            </View>
          )}
        </View>
      </ScrollView>
    </SafeAreaView>
    </>
  );
}

// ── Liquid Glass styles ──
const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0d2818' },
  scroll: { paddingHorizontal: 16, paddingBottom: 100, paddingTop: 8 },

  // Header
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  greeting: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.4)' },
  headerName: { fontFamily: 'DMSans_700Bold', fontSize: 24, color: '#FFFFFF' },
  headerRight: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  bellWrap: {
    position: 'relative', padding: 6,
    backgroundColor: 'rgba(255,255,255,0.08)', borderRadius: 14,
  },
  bellBadge: {
    position: 'absolute', top: 0, right: -2,
    minWidth: 16, height: 16, borderRadius: 8,
    backgroundColor: '#F09595', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 3,
  },
  bellBadgeText: { fontFamily: 'DMSans_700Bold', fontSize: 9, color: '#FFF' },
  avatar: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: '#7DDFAA' },

  // Main card — Spent this month (green accent glass)
  mainCard: {
    backgroundColor: 'rgba(80,200,120,0.12)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: 18, padding: 20, alignItems: 'center', marginBottom: 12,
  },
  mainLabel: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: 'rgba(255,255,255,0.5)' },
  mainAmount: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 36, color: '#FFFFFF', marginVertical: 4 },
  mainSub: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.4)' },

  // Stats row
  statsRow: { flexDirection: 'row', gap: 8, marginBottom: 14 },
  statCard: {
    flex: 1, alignItems: 'center', paddingVertical: 14,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 16,
  },
  statValue: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 18, color: '#FFFFFF' },
  statLabel: { fontFamily: 'DMSans_500Medium', fontSize: 10, color: 'rgba(255,255,255,0.4)', marginTop: 3, textTransform: 'uppercase', letterSpacing: 0.5 },
  comingSoon: { fontFamily: 'DMSans_400Regular', fontSize: 9, color: 'rgba(255,255,255,0.3)', marginTop: 1 },

  // My Usual Shop
  usualShopBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 16, padding: 14, marginBottom: 18,
  },
  usualShopLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  usualShopTitle: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: '#FFFFFF' },
  usualShopSub: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: 'rgba(255,255,255,0.4)' },

  // Sections
  section: { marginBottom: 18 },
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: 'rgba(255,255,255,0.7)', marginBottom: 8 },

  // Running Low
  lowCard: {
    width: 140, padding: 10, gap: 4,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 14,
  },
  lowName: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: '#FFFFFF' },
  lowPrice: { fontFamily: 'JetBrainsMono_500Medium', fontSize: 11, color: '#7DDFAA' },

  // Price Memory
  memoryCard: {
    marginBottom: 6, padding: 12,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 14,
  },
  memoryProduct: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#FFFFFF' },
  memoryDetail: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.45)', marginTop: 2 },
  memoryRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 6 },
  memoryNow: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: '#FFFFFF' },
  savingBadge: {
    backgroundColor: 'rgba(80,200,120,0.15)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: 10, paddingHorizontal: 10, paddingVertical: 4,
  },
  savingBadgeText: { fontFamily: 'DMSans_700Bold', fontSize: 12, color: '#7DDFAA' },
  memoryAddBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(80,200,120,0.2)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.3)',
    alignItems: 'center', justifyContent: 'center',
  },
  memoryAddBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: '#7DDFAA', lineHeight: 18 },
  seeAll: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: '#7DDFAA', marginTop: 8, textAlign: 'center' },

  // Best saving
  bestSavingCard: {
    marginBottom: 18, padding: 14,
    backgroundColor: 'rgba(80,200,120,0.12)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: 16,
  },
  bestSavingTitle: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: '#7DDFAA', marginBottom: 4 },
  bestSavingText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.55)', lineHeight: 18 },

  // Shopping list shortcut
  shoppingListBar: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 16, padding: 14, marginBottom: 18,
  },
  shoppingListLeft: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  shoppingListText: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: '#FFFFFF' },

  // Empty month
  emptyMonth: {
    padding: 16, alignItems: 'center' as const,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.10)',
    borderRadius: 14,
  },
  emptyMonthText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: 'rgba(255,255,255,0.55)' },
  emptyMonthSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: 'rgba(255,255,255,0.35)', marginTop: 4 },
});
