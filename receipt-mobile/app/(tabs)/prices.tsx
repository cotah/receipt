import React, { useState, useEffect } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet } from 'react-native';
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

export default function PricesScreen() {
  const [tab, setTab] = useState<'compare' | 'offers'>('compare');
  const [search, setSearch] = useState('');
  const { comparison, offers, isLoading, compareProduct, fetchLeafletOffers } = usePrices();

  useEffect(() => {
    if (tab === 'offers') fetchLeafletOffers();
  }, [tab]);

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
            {comparison && (
              <PriceCompare
                product_name={comparison.product_name}
                unit={comparison.unit}
                stores={comparison.stores}
              />
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
});
