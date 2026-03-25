import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { GestureDetector } from 'react-native-gesture-handler';
import { useTabSwipe } from '../../hooks/useTabSwipe';
import Input from '../../components/ui/Input';
import PriceCompare from '../../components/prices/PriceCompare';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import StoreTag from '../../components/prices/StoreTag';
import { Colors } from '../../constants/colors';
import { Spacing } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';
import { usePrices } from '../../hooks/usePrices';
import api from '../../services/api';

interface EligibleAlert {
  id: string;
  store: string;
  product: string;
}

export default function PricesScreen() {
  const [tab, setTab] = useState<'compare' | 'offers'>('compare');
  const [search, setSearch] = useState('');
  const [eligibleAlerts, setEligibleAlerts] = useState<EligibleAlert[]>([]);
  const [confirmedIds, setConfirmedIds] = useState<Set<string>>(new Set());
  const { comparison, offers, isLoading, compareProduct, fetchLeafletOffers } = usePrices();

  useEffect(() => {
    if (tab === 'offers') fetchLeafletOffers();
  }, [tab]);

  // Fetch alerts eligible for savings confirmation (5-8h old)
  useEffect(() => {
    (async () => {
      try {
        const resp = await api.get('/alerts?unread_only=false&per_page=10');
        const alerts = resp.data?.data || [];
        const now = Date.now();
        const eligible: EligibleAlert[] = [];
        for (const a of alerts) {
          const created = new Date(a.created_at).getTime();
          const hoursAgo = (now - created) / (1000 * 60 * 60);
          if (hoursAgo >= 5 && hoursAgo <= 8 && a.metadata) {
            eligible.push({
              id: a.id,
              store: a.metadata.store_name || a.metadata.store || 'the store',
              product: a.metadata.product_name || a.metadata.product || '',
            });
          }
        }
        setEligibleAlerts(eligible);
      } catch {
        // Silently ignore
      }
    })();
  }, []);

  const handleConfirmSaving = useCallback(async (alertId: string) => {
    try {
      const resp = await api.post(`/alerts/${alertId}/confirm-saving`);
      setConfirmedIds((prev) => new Set([...prev, alertId]));
      Alert.alert(
        'Thanks! +10 points added',
        `You saved ${formatCurrency(resp.data?.saving || 0)} on ${resp.data?.product || 'this item'}`,
      );
    } catch {
      Alert.alert('Oops', 'Could not confirm this saving. It may have expired.');
    }
  }, []);

  const handleSearch = () => {
    if (search.trim()) compareProduct(search.trim());
  };

  const swipe = useTabSwipe(2);

  return (
    <GestureDetector gesture={swipe}>
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Prices</Text>

      {/* Tabs */}
      <View style={styles.tabs}>
        <Pressable onPress={() => setTab('compare')} style={[styles.tab, tab === 'compare' && styles.tabActive]}>
          <Text style={[styles.tabText, tab === 'compare' && styles.tabTextActive]}>Compare</Text>
        </Pressable>
        <Pressable onPress={() => setTab('offers')} style={[styles.tab, tab === 'offers' && styles.tabActive]}>
          <Text style={[styles.tabText, tab === 'offers' && styles.tabTextActive]}>Offers This Week</Text>
        </Pressable>
      </View>

      {/* Savings confirmation banners */}
      {eligibleAlerts
        .filter((a) => !confirmedIds.has(a.id))
        .map((alert) => (
          <View key={alert.id} style={styles.savingsBanner}>
            <Text style={styles.savingsText}>
              Did you go to {alert.store} because of our alert?
            </Text>
            <Pressable
              style={styles.savingsBtn}
              onPress={() => handleConfirmSaving(alert.id)}
            >
              <Text style={styles.savingsBtnText}>Yes, I went! (+10pts)</Text>
            </Pressable>
          </View>
        ))}

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {tab === 'compare' && (
          <>
            <Input
              placeholder="Search a product..."
              value={search}
              onChangeText={setSearch}
              leftIcon="search"
              onSubmitEditing={handleSearch}
              returnKeyType="search"
            />
            {comparison && comparison.stores && comparison.stores.length > 0 && (
              <PriceCompare
                product_name={comparison.product_name}
                unit={comparison.unit}
                stores={comparison.stores}
              />
            )}
            {comparison && (!comparison.stores || comparison.stores.length === 0) && (
              <Text style={styles.hint}>No price data yet for "{search}". Scan more receipts to build the price database!</Text>
            )}
            {!comparison && !isLoading && (
              <Text style={styles.hint}>Search for a product to compare prices across stores</Text>
            )}
          </>
        )}

        {tab === 'offers' && (
          <>
            {offers.map((offer, i) => (
              <Card key={i} style={styles.offerCard}>
                <View style={styles.offerRow}>
                  <View style={styles.offerLeft}>
                    <StoreTag storeName={offer.store} />
                    <Text style={styles.offerName}>{offer.product_name}</Text>
                    <Badge text={offer.category} variant="neutral" size="sm" />
                  </View>
                  <View style={styles.offerRight}>
                    <Text style={styles.offerPrice}>{formatCurrency(offer.unit_price)}</Text>
                    {offer.discount_percent && (
                      <Badge text={`-${offer.discount_percent}%`} variant="success" size="sm" />
                    )}
                  </View>
                </View>
              </Card>
            ))}
            {offers.length === 0 && !isLoading && (
              <Text style={styles.hint}>No leaflet offers available right now</Text>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
    </GestureDetector>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Colors.surface.background },
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: Colors.primary.dark, paddingHorizontal: Spacing.md, paddingTop: Spacing.md },
  tabs: { flexDirection: 'row', paddingHorizontal: Spacing.md, marginTop: Spacing.md, gap: Spacing.sm },
  tab: { flex: 1, paddingVertical: Spacing.sm, alignItems: 'center', borderRadius: 9999, backgroundColor: Colors.surface.card },
  tabActive: { backgroundColor: Colors.primary.dark },
  tabText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.secondary },
  tabTextActive: { color: Colors.text.inverse },
  content: { padding: Spacing.md },
  hint: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.tertiary, textAlign: 'center', marginTop: Spacing.xl },
  offerCard: { marginBottom: Spacing.sm },
  offerRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  offerLeft: { flex: 1, gap: 4 },
  offerName: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  offerRight: { alignItems: 'flex-end', gap: 4 },
  offerPrice: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 18, color: Colors.accent.amber },
  savingsBanner: {
    marginHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    backgroundColor: '#F0F9F4',
    borderWidth: 1,
    borderColor: '#A8D5B8',
    borderRadius: 12,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  savingsText: {
    fontFamily: 'DMSans_500Medium',
    fontSize: 13,
    color: Colors.text.primary,
    flex: 1,
  },
  savingsBtn: {
    backgroundColor: Colors.primary.default,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderRadius: 8,
  },
  savingsBtnText: {
    fontFamily: 'DMSans_700Bold',
    fontSize: 12,
    color: '#FFF',
  },
});
