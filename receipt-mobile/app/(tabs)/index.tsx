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

        {/* Header — "Good morning" + name + avatar */}
        <View style={s.header}>
          <View>
            <Text style={s.greeting}>Good morning</Text>
            <Text style={s.name}>{name}</Text>
          </View>
          <Pressable onPress={() => router.push('/(tabs)/profile')} style={s.avatar}>
            <Text style={s.avatarText}>{name.charAt(0).toUpperCase()}{profile?.full_name?.split(' ')?.[1]?.charAt(0)?.toUpperCase() ?? ''}</Text>
          </Pressable>
        </View>

        {/* Search bar */}
        <Pressable onPress={() => router.push('/(tabs)/prices')} style={s.searchBar}>
          <Feather name="search" size={14} color="rgba(255,255,255,0.3)" />
          <Text style={s.searchText}>Search any product...</Text>
        </Pressable>

        {/* Savings card — green accent */}
        <View style={s.savingsCard}>
          <View>
            <Text style={s.savingsLabel}>Your potential savings</Text>
            <Text style={s.savingsAmount}>{formatCurrency(savings?.attributed_savings ?? 12.40)}</Text>
            <Text style={s.savingsSub}>per week across 5 stores</Text>
          </View>
          <Text style={s.savingsStar}>★</Text>
        </View>

        {/* Two shortcuts side by side */}
        <View style={s.shortcutsRow}>
          <Pressable onPress={() => router.push('/usual-shop')} style={s.shortcutCard}>
            <Feather name="shopping-bag" size={20} color="rgba(255,255,255,0.6)" />
            <Text style={s.shortcutLabel}>My usual shop</Text>
          </Pressable>
          <Pressable onPress={() => router.push('/rewards')} style={s.shortcutCard}>
            <Feather name="award" size={20} color="#F0D68A" />
            <Text style={[s.shortcutLabel, { color: '#7DDFAA' }]}>460 pts</Text>
          </Pressable>
        </View>

        {/* Best deals today */}
        <Text style={s.sectionTitle}>Best deals today</Text>
        <View style={s.dealsCard}>
          {[
            { name: 'Chicken Breast 1kg', store: 'Aldi', price: '5.99', dot: '#7C8CF0' },
            { name: 'Avonmore Milk 2L', store: 'Lidl', price: '2.19', dot: '#F0997B' },
            { name: 'Kerrygold Butter 227g', store: 'Tesco', price: '2.79', dot: '#85B7EB' },
          ].map((item, i) => (
            <View key={i} style={[s.dealRow, i < 2 && s.dealRowBorder]}>
              <View style={[s.dealDot, { backgroundColor: item.dot }]} />
              <View style={{ flex: 1 }}>
                <Text style={s.dealName}>{item.name}</Text>
                <Text style={s.dealStore}>{item.store}</Text>
              </View>
              <View style={s.dealPricePill}>
                <Text style={s.dealPriceText}>{item.price}</Text>
              </View>
            </View>
          ))}
        </View>

        {/* Raffle card — gold */}
        <Text style={s.sectionTitle}>Raffle</Text>
        <View style={s.raffleCard}>
          <View>
            <Text style={s.raffleLabel}>Monthly draw</Text>
            <Text style={s.raffleTickets}>3 tickets earned</Text>
            <Text style={s.raffleNext}>Next draw: May 3rd</Text>
          </View>
          <Text style={s.raffleTrophy}>🏆</Text>
        </View>

        {/* This Month's Receipts (if any) */}
        {monthReceipts.length > 0 && (
          <>
            <Text style={s.sectionTitle}>This month</Text>
            {monthReceipts.slice(0, 3).map((r) => (
              <ReceiptCard key={r.id} {...r} onPress={() => router.push(`/receipt/${r.id}`)} />
            ))}
          </>
        )}

      </ScrollView>
    </SafeAreaView>
    </>
  );
}

const s = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#0d2818' },
  scroll: { paddingHorizontal: 16, paddingBottom: 100, paddingTop: 8 },

  // Header
  header: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  greeting: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(255,255,255,0.4)' },
  name: { fontFamily: 'DMSans_700Bold', fontSize: 24, color: '#FFFFFF' },
  avatar: {
    width: 40, height: 40, borderRadius: 20,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center', justifyContent: 'center',
  },
  avatarText: { fontFamily: 'DMSans_700Bold', fontSize: 14, color: '#7DDFAA' },

  // Search
  searchBar: {
    flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.10)',
    borderRadius: 14, paddingHorizontal: 14, paddingVertical: 10,
    marginBottom: 14,
  },
  searchText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: 'rgba(255,255,255,0.3)' },

  // Savings card
  savingsCard: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: 'rgba(80,200,120,0.12)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: 18, padding: 16, marginBottom: 12,
  },
  savingsLabel: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: 'rgba(255,255,255,0.5)' },
  savingsAmount: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 32, color: '#FFFFFF', marginVertical: 2 },
  savingsSub: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: 'rgba(255,255,255,0.4)' },
  savingsStar: { fontSize: 28, color: 'rgba(255,255,255,0.08)' },

  // Shortcuts
  shortcutsRow: { flexDirection: 'row', gap: 10, marginBottom: 18 },
  shortcutCard: {
    flex: 1, alignItems: 'center', justifyContent: 'center', gap: 6,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 16, paddingVertical: 14,
  },
  shortcutLabel: { fontFamily: 'DMSans_600SemiBold', fontSize: 12, color: 'rgba(255,255,255,0.6)' },

  // Section
  sectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: 'rgba(255,255,255,0.7)', marginBottom: 8 },

  // Deals card
  dealsCard: {
    backgroundColor: 'rgba(255,255,255,0.12)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.20)',
    borderRadius: 18, padding: 14, marginBottom: 18,
  },
  dealRow: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10 },
  dealRowBorder: { borderBottomWidth: 0.5, borderBottomColor: 'rgba(255,255,255,0.06)' },
  dealDot: { width: 8, height: 8, borderRadius: 4 },
  dealName: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: 'rgba(255,255,255,0.85)' },
  dealStore: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: 'rgba(255,255,255,0.35)' },
  dealPricePill: {
    backgroundColor: 'rgba(80,200,120,0.15)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: 20, paddingHorizontal: 12, paddingVertical: 4,
  },
  dealPriceText: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 13, color: '#7DDFAA' },

  // Raffle card
  raffleCard: {
    flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center',
    backgroundColor: 'rgba(212,168,67,0.10)',
    borderWidth: 0.5, borderColor: 'rgba(212,168,67,0.20)',
    borderRadius: 18, padding: 16, marginBottom: 18,
  },
  raffleLabel: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: 'rgba(255,255,255,0.45)' },
  raffleTickets: { fontFamily: 'DMSans_700Bold', fontSize: 17, color: '#F0D68A', marginVertical: 2 },
  raffleNext: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: 'rgba(255,255,255,0.35)' },
  raffleTrophy: { fontSize: 28 },
});
