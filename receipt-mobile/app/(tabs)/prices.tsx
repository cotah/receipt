import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator, Alert } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';


import Input from '../../components/ui/Input';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import StoreTag from '../../components/prices/StoreTag';
import { Colors, Shadows } from '../../constants/colors';
import { Spacing, BorderRadius, Fonts } from '../../constants/typography';
import { formatCurrency } from '../../utils/formatCurrency';
import { usePrices, SearchResult, Alternative } from '../../hooks/usePrices';
import api from '../../services/api';

interface EligibleAlert {
  id: string;
  store: string;
  product: string;
}

export default function PricesScreen() {
  const [tab, setTab] = useState<'compare' | 'offers'>('compare');
  const [searchText, setSearchText] = useState('');
  const [eligibleAlerts, setEligibleAlerts] = useState<EligibleAlert[]>([]);
  const [confirmedIds, setConfirmedIds] = useState<Set<string>>(new Set());
  const [addedToList, setAddedToList] = useState<Map<string, string>>(new Map());
  const [timing, setTiming] = useState<any>(null);
  const router = useRouter();

  const toggleShoppingList = useCallback(async (name: string, store: string, price: number, category?: string) => {
    const key = `${name}-${store}`;
    const existingId = addedToList.get(key);
    if (existingId) {
      try {
        await api.delete(`/shopping-list/${existingId}`);
        setAddedToList(prev => { const n = new Map(prev); n.delete(key); return n; });
      } catch {}
    } else {
      try {
        const { data } = await api.post('/shopping-list/add', {
          product_name: name, store_name: store, unit_price: price,
          category: category || 'Other', source: 'deal',
        });
        const itemId = data.item?.id || 'exists';
        setAddedToList(prev => new Map(prev).set(key, itemId));
      } catch {
        Alert.alert('Error', 'Could not update list');
      }
    }
  }, [addedToList]);

  const {
    isLoading,
    searchResults, isSearching, smartSearch, clearSearch,
    selectedProduct, selectProduct, clearSelection,
    alternatives, isLoadingAlts,
    weeklyDeals, isLoadingDeals, fetchWeeklyDeals,
  } = usePrices();

  useEffect(() => {
    if (tab === 'offers') {
      fetchWeeklyDeals();
      api.get('/prices/smart-timing').then(({ data }) => setTiming(data)).catch(() => {});
    }
  }, [tab]);

  // Fetch savings confirmation alerts
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

  const handleSearchChange = (text: string) => {
    setSearchText(text);
    if (selectedProduct) clearSelection();
    smartSearch(text);
  };

  const handleProductTap = (result: SearchResult) => {
    selectProduct(result);
  };

  const handleBack = () => {
    clearSelection();
  };

  

  return (
    <>
    <SafeAreaView style={styles.container}>
      <Text style={styles.title}>Prices</Text>

      {/* Tabs */}
      <View style={styles.tabs}>
        <Pressable onPress={() => { setTab('compare'); clearSearch(); setSearchText(''); }} style={[styles.tab, tab === 'compare' && styles.tabActive]}>
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
            <Pressable style={styles.savingsBtn} onPress={() => handleConfirmSaving(alert.id)}>
              <Text style={styles.savingsBtnText}>Yes, I went! (+10pts)</Text>
            </Pressable>
          </View>
        ))}

      <ScrollView showsVerticalScrollIndicator={false} contentContainerStyle={styles.content}>
        {tab === 'compare' && (
          <>
            {/* Search bar */}
            <Input
              placeholder="Search products... (e.g. brioche, milk, nutella)"
              value={searchText}
              onChangeText={handleSearchChange}
              leftIcon="search"
              returnKeyType="search"
            />

            {/* Loading */}
            {isSearching && (
              <View style={styles.loadingRow}>
                <ActivityIndicator size="small" color={Colors.primary.default} />
                <Text style={styles.loadingText}>Searching...</Text>
              </View>
            )}

            {/* Product Detail View */}
            {selectedProduct && !isSearching && (
              <View style={styles.detailSection}>
                {/* Back button */}
                <Pressable onPress={handleBack} style={styles.backBtn}>
                  <Text style={styles.backText}>← Back to results</Text>
                </Pressable>

                {/* Product card with all store prices */}
                <Text style={styles.detailTitle}>{selectedProduct.display_name}</Text>

                {selectedProduct.stores.length > 1 && selectedProduct.potential_saving && (
                  <View style={styles.savingChip}>
                    <Text style={styles.savingChipText}>
                      Save {formatCurrency(selectedProduct.potential_saving)} by choosing {selectedProduct.cheapest_store}
                    </Text>
                  </View>
                )}

                {selectedProduct.stores.map((store, i) => (
                  <Card key={store.store_name} style={[styles.storeRow, i === 0 && styles.storeRowCheapest] as any}>
                    <View style={styles.storeRowInner}>
                      <View style={styles.storeRowLeft}>
                        <StoreTag storeName={store.store_name} size="md" />
                        <Text style={styles.storeProductName} numberOfLines={2}>
                          {store.product_name}
                        </Text>
                      </View>
                      <View style={styles.storeRowRight}>
                        <Text style={[styles.storePrice, i === 0 && styles.storePriceCheapest]}>
                          {formatCurrency(store.unit_price)}
                        </Text>
                        {store.is_cheapest && <Badge text="CHEAPEST" variant="success" size="sm" />}
                        {store.is_on_offer && <Badge text="OFFER" variant="warning" size="sm" />}
                      </View>
                    </View>
                  </Card>
                ))}

                {/* AI Alternatives Section */}
                <View style={styles.altSection}>
                  <View style={styles.altHeader}>
                    <Text style={styles.altTitle}>💡 Cheaper Alternatives</Text>
                    <Text style={styles.altSubtitle}>AI-powered suggestions based on similar products</Text>
                  </View>

                  {isLoadingAlts && (
                    <View style={styles.loadingRow}>
                      <ActivityIndicator size="small" color={Colors.accent.blue} />
                      <Text style={styles.loadingText}>Finding alternatives...</Text>
                    </View>
                  )}

                  {!isLoadingAlts && alternatives.length === 0 && (
                    <Text style={styles.altEmpty}>No alternatives found in current promotions</Text>
                  )}

                  {alternatives.map((alt, i) => (
                    <Card key={`${alt.product_key}-${i}`} style={styles.altCard}>
                      <View style={styles.altRow}>
                        <View style={styles.altLeft}>
                          <StoreTag storeName={alt.store_name} size="sm" />
                          <Text style={styles.altName} numberOfLines={2}>{alt.product_name}</Text>
                        </View>
                        <View style={styles.altRight}>
                          <Text style={styles.altPrice}>{formatCurrency(alt.unit_price)}</Text>
                          {alt.is_on_offer && <Badge text="OFFER" variant="warning" size="sm" />}
                        </View>
                      </View>
                    </Card>
                  ))}
                </View>
              </View>
            )}

            {/* Search Results List */}
            {!selectedProduct && !isSearching && searchResults.length > 0 && (
              <View style={styles.resultsSection}>
                <Text style={styles.resultsCount}>
                  {searchResults.length} product{searchResults.length !== 1 ? 's' : ''} found
                </Text>
                {searchResults.map((result, i) => (
                  <Pressable key={`${result.product_key}-${i}`} onPress={() => handleProductTap(result)}>
                    <Card style={styles.resultCard}>
                      <View style={styles.resultTop}>
                        <Text style={styles.resultName} numberOfLines={2}>
                          {result.display_name}
                        </Text>
                        <Text style={styles.resultPrice}>{formatCurrency(result.cheapest_price)}</Text>
                      </View>
                      <View style={styles.resultBottom}>
                        <View style={styles.resultStores}>
                          {result.stores.map((s) => (
                            <StoreTag key={s.store_name} storeName={s.store_name} size="sm" />
                          ))}
                        </View>
                        {result.potential_saving && result.potential_saving > 0 && (
                          <Badge
                            text={`Save ${formatCurrency(result.potential_saving)}`}
                            variant="success"
                            size="sm"
                          />
                        )}
                      </View>
                      {result.store_count > 1 && (
                        <Text style={styles.resultHint}>
                          Available in {result.store_count} stores · Tap to compare
                        </Text>
                      )}
                    </Card>
                  </Pressable>
                ))}
              </View>
            )}

            {/* Empty states */}
            {!selectedProduct && !isSearching && searchResults.length === 0 && searchText.length >= 2 && (
              <View style={styles.emptyState}>
                <Text style={styles.emptyEmoji}>🔍</Text>
                <Text style={styles.emptyTitle}>No products found</Text>
                <Text style={styles.emptyText}>
                  Try a different search term, like "milk", "bread", or a brand name
                </Text>
              </View>
            )}

            {!selectedProduct && !isSearching && searchText.length < 2 && (
              <View style={styles.emptyState}>
                <Text style={styles.emptyEmoji}>🛒</Text>
                <Text style={styles.emptyTitle}>Compare prices across stores</Text>
                <Text style={styles.emptyText}>
                  Search for any product to see prices at SuperValu, Tesco, and Lidl. We'll show you the cheapest option and suggest alternatives.
                </Text>
              </View>
            )}
          </>
        )}

        {tab === 'offers' && (
          <>
            {isLoadingDeals && (
              <View style={styles.loadingRow}>
                <ActivityIndicator size="small" color={Colors.primary.default} />
                <Text style={styles.loadingText}>Loading your deals...</Text>
              </View>
            )}

            {!isLoadingDeals && weeklyDeals && (
              <>
                {/* Golden Deals — PRO only */}
                {weeklyDeals.golden.length > 0 && (
                  <View style={styles.dealSection}>
                    <Text style={styles.dealSectionTitle}>🥇 Golden Offers</Text>
                    <Text style={styles.dealSectionSub}>Exceptional deals matched to your profile</Text>
                    {weeklyDeals.golden.map((deal) => (
                      <Card key={deal.id} style={styles.goldenCard}>
                        <View style={styles.dealRow}>
                          <View style={styles.dealLeft}>
                            <StoreTag storeName={deal.store_name} size="md" />
                            <Text style={styles.goldenName} numberOfLines={2}>{deal.product_name}</Text>
                            {deal.promotion_text && (
                              <Text style={styles.goldenPromo}>{deal.promotion_text}</Text>
                            )}
                          </View>
                          <View style={styles.dealRight}>
                            <Text style={styles.goldenPrice}>{formatCurrency(deal.current_price)}</Text>
                            {deal.avg_price_4w && (
                              <Text style={styles.goldenWas}>avg €{Number(deal.avg_price_4w).toFixed(2)}</Text>
                            )}
                            {deal.discount_pct && (
                              <Badge text={`-${deal.discount_pct}%`} variant="success" size="sm" />
                            )}
                            <Pressable
                              onPress={() => toggleShoppingList(deal.product_name, deal.store_name, deal.current_price, deal.category)}
                              style={styles.addBtn}
                            >
                              <Text style={styles.addBtnText}>
                                {addedToList.has(`${deal.product_name}-${deal.store_name}`) ? '✓' : '+'}
                              </Text>
                            </Pressable>
                          </View>
                        </View>
                      </Card>
                    ))}
                  </View>
                )}

                {/* Trending Deals */}
                {weeklyDeals.trending.length > 0 && (
                  <View style={styles.dealSection}>
                    <Text style={styles.dealSectionTitle}>🔥 Trending This Week</Text>
                    <Text style={styles.dealSectionSub}>Best savings across all stores</Text>
                    {weeklyDeals.trending.map((deal) => (
                      <Card key={deal.id} style={styles.dealCard}>
                        <View style={styles.dealRow}>
                          <View style={styles.dealLeft}>
                            <StoreTag storeName={deal.store_name} />
                            <Text style={styles.dealName} numberOfLines={2}>{deal.product_name}</Text>
                            {deal.promotion_text && (
                              <Text style={styles.dealPromo} numberOfLines={2}>{deal.promotion_text}</Text>
                            )}
                          </View>
                          <View style={styles.dealRight}>
                            <Text style={styles.dealPrice}>{formatCurrency(deal.current_price)}</Text>
                            {deal.discount_pct && (
                              <Badge text={`-${deal.discount_pct}%`} variant="success" size="sm" />
                            )}
                            <Pressable
                              onPress={() => toggleShoppingList(deal.product_name, deal.store_name, deal.current_price, deal.category)}
                              style={styles.addBtn}
                            >
                              <Text style={styles.addBtnText}>
                                {addedToList.has(`${deal.product_name}-${deal.store_name}`) ? '✓' : '+'}
                              </Text>
                            </Pressable>
                          </View>
                        </View>
                      </Card>
                    ))}
                  </View>
                )}

                {/* Personal Deals */}
                {weeklyDeals.personalised.length > 0 && (
                  <View style={styles.dealSection}>
                    <Text style={styles.dealSectionTitle}>✨ Picked For You</Text>
                    <Text style={styles.dealSectionSub}>Based on your shopping habits</Text>
                    {weeklyDeals.personalised.map((deal) => (
                      <Card key={deal.id} style={styles.dealCard}>
                        <View style={styles.dealRow}>
                          <View style={styles.dealLeft}>
                            <StoreTag storeName={deal.store_name} />
                            <Text style={styles.dealName} numberOfLines={2}>{deal.product_name}</Text>
                            {deal.promotion_text && (
                              <Text style={styles.dealPromo} numberOfLines={2}>{deal.promotion_text}</Text>
                            )}
                          </View>
                          <View style={styles.dealRight}>
                            <Text style={styles.dealPrice}>{formatCurrency(deal.current_price)}</Text>
                            {deal.discount_pct && (
                              <Badge text={`-${deal.discount_pct}%`} variant="success" size="sm" />
                            )}
                            <Pressable
                              onPress={() => toggleShoppingList(deal.product_name, deal.store_name, deal.current_price, deal.category)}
                              style={styles.addBtn}
                            >
                              <Text style={styles.addBtnText}>
                                {addedToList.has(`${deal.product_name}-${deal.store_name}`) ? '✓' : '+'}
                              </Text>
                            </Pressable>
                          </View>
                        </View>
                      </Card>
                    ))}
                  </View>
                )}

                {/* Refresh info */}
                <Text style={styles.refreshInfo}>
                  Refreshes every {weeklyDeals.refresh_days} days
                  {weeklyDeals.plan === 'free' ? ' · Upgrade to Pro for more deals and Golden Offers' : ''}
                </Text>

                {/* Shopping List shortcut */}
                {addedToList.size > 0 && (
                  <Pressable style={styles.shoppingListBtn} onPress={() => router.push('/shopping-list')}>
                    <Feather name="shopping-cart" size={16} color="#fff" />
                    <Text style={styles.shoppingListBtnText}>
                      View Shopping List ({addedToList.size})
                    </Text>
                  </Pressable>
                )}

                {/* Smart Timing — store schedules */}
                {timing?.store_schedules && (
                  <View style={styles.dealSection}>
                    <Text style={styles.dealSectionTitle}>⏰ Store Schedules</Text>
                    <Text style={styles.dealSectionSub}>When new offers drop at each store</Text>
                    {timing.store_schedules.map((s: any) => (
                      <Card key={s.store} style={styles.timingCard}>
                        <View style={styles.timingRow}>
                          <View style={styles.timingLeft}>
                            <StoreTag storeName={s.store} />
                            <Text style={styles.timingDetail}>{s.refresh_detail}</Text>
                          </View>
                          <View style={styles.timingRight}>
                            {s.days_until_expiry != null && s.days_until_expiry <= 2 ? (
                              <Text style={styles.timingUrgent}>Expires {s.days_until_expiry === 0 ? 'today' : `in ${s.days_until_expiry}d`}</Text>
                            ) : s.offers_valid_until ? (
                              <Text style={styles.timingValid}>Valid until {s.offers_valid_until}</Text>
                            ) : null}
                          </View>
                        </View>
                      </Card>
                    ))}
                  </View>
                )}

                {/* Restock insights */}
                {timing?.user_restock_insights?.length > 0 && (
                  <View style={styles.dealSection}>
                    <Text style={styles.dealSectionTitle}>🔄 Restock Reminders</Text>
                    <Text style={styles.dealSectionSub}>Based on your purchase patterns</Text>
                    {timing.user_restock_insights.filter((i: any) => i.status === 'due' || i.status === 'soon').map((item: any, idx: number) => (
                      <Card key={idx} style={styles.timingCard}>
                        <Text style={styles.timingProduct}>{item.product}</Text>
                        <Text style={item.status === 'due' ? styles.timingUrgent : styles.timingDetail}>
                          {item.status === 'due'
                            ? `Overdue — you usually buy every ${item.avg_days_between} days`
                            : `Due in ${item.days_until_restock} days`}
                        </Text>
                      </Card>
                    ))}
                  </View>
                )}

                {/* Empty state */}
                {weeklyDeals.total === 0 && (
                  <View style={styles.emptyState}>
                    <Text style={styles.emptyEmoji}>📦</Text>
                    <Text style={styles.emptyTitle}>Deals are being prepared</Text>
                    <Text style={styles.emptyText}>
                      Your personalised offers are being generated. Check back soon!
                    </Text>
                  </View>
                )}
              </>
            )}

            {!isLoadingDeals && !weeklyDeals && (
              <View style={styles.emptyState}>
                <Text style={styles.emptyEmoji}>📦</Text>
                <Text style={styles.emptyTitle}>No offers right now</Text>
                <Text style={styles.emptyText}>
                  We're preparing smart deals for you. Check back soon!
                </Text>
              </View>
            )}
          </>
        )}
      </ScrollView>
    </SafeAreaView>
    </>
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
  content: { padding: Spacing.md, paddingBottom: 100 },

  // Loading
  loadingRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', paddingVertical: Spacing.lg, gap: Spacing.sm },
  loadingText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.tertiary },

  // Search results list
  resultsSection: { marginTop: Spacing.sm },
  resultsCount: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.tertiary, marginBottom: Spacing.sm },
  resultCard: { marginBottom: Spacing.sm, padding: Spacing.md },
  resultTop: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: Spacing.sm },
  resultName: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary, flex: 1 },
  resultPrice: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 18, color: Colors.primary.default },
  resultBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm },
  resultStores: { flexDirection: 'row', gap: 6, flexWrap: 'wrap', flex: 1 },
  resultHint: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, marginTop: 6 },

  // Product detail
  detailSection: { marginTop: Spacing.sm },
  backBtn: { paddingVertical: Spacing.xs, marginBottom: Spacing.sm },
  backText: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.accent.blue },
  detailTitle: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 22, color: Colors.text.primary, marginBottom: Spacing.sm },

  savingChip: {
    backgroundColor: '#E8F5EE',
    borderRadius: BorderRadius.sm,
    paddingHorizontal: Spacing.md,
    paddingVertical: Spacing.sm,
    marginBottom: Spacing.md,
    borderWidth: 1,
    borderColor: '#A8D5B8',
  },
  savingChipText: { fontFamily: 'DMSans_600SemiBold', fontSize: 13, color: Colors.primary.default },

  storeRow: { marginBottom: Spacing.sm },
  storeRowCheapest: { borderWidth: 2, borderColor: Colors.accent.green, borderRadius: BorderRadius.md },
  storeRowInner: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  storeRowLeft: { flex: 1, gap: 6 },
  storeProductName: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.secondary },
  storeRowRight: { alignItems: 'flex-end', gap: 4 },
  storePrice: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 20, color: Colors.accent.amber },
  storePriceCheapest: { color: Colors.accent.green },

  // Alternatives
  altSection: { marginTop: Spacing.lg, paddingTop: Spacing.lg, borderTopWidth: 1, borderTopColor: Colors.surface.alt },
  altHeader: { marginBottom: Spacing.md },
  altTitle: { fontFamily: 'DMSans_700Bold', fontSize: 17, color: Colors.text.primary },
  altSubtitle: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.tertiary, marginTop: 2 },
  altEmpty: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.tertiary, textAlign: 'center', paddingVertical: Spacing.md },
  altCard: { marginBottom: Spacing.xs },
  altRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  altLeft: { flex: 1, gap: 4 },
  altName: { fontFamily: 'DMSans_500Medium', fontSize: 14, color: Colors.text.primary },
  altRight: { alignItems: 'flex-end', gap: 4 },
  altPrice: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 16, color: Colors.accent.amber },

  // Empty states
  emptyState: { alignItems: 'center', paddingVertical: Spacing.xxl, paddingHorizontal: Spacing.lg },
  emptyEmoji: { fontSize: 48, marginBottom: Spacing.md },
  emptyTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, textAlign: 'center', marginBottom: Spacing.xs },
  emptyText: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: Colors.text.tertiary, textAlign: 'center', lineHeight: 20 },

  // Deals sections
  dealSection: { marginBottom: Spacing.lg },
  dealSectionTitle: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: Colors.text.primary, marginBottom: 2 },
  dealSectionSub: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: Colors.text.tertiary, marginBottom: Spacing.md },

  dealCard: { marginBottom: Spacing.sm },
  dealRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start' },
  dealLeft: { flex: 1, gap: 4 },
  dealName: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: Colors.text.primary },
  dealPromo: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary },
  dealRight: { alignItems: 'flex-end', gap: 4, marginLeft: Spacing.sm },
  dealPrice: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 18, color: Colors.accent.amber },

  goldenCard: { marginBottom: Spacing.sm, borderWidth: 2, borderColor: '#E8A020', borderRadius: BorderRadius.md },
  goldenName: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: Colors.text.primary },
  goldenPromo: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.primary.default },
  goldenPrice: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 20, color: Colors.accent.amber },
  goldenWas: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, textDecorationLine: 'line-through' },

  refreshInfo: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, textAlign: 'center', marginTop: Spacing.md, marginBottom: Spacing.lg },

  // Add to list button
  addBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: Colors.primary.default,
    alignItems: 'center', justifyContent: 'center',
    marginTop: 4,
  },
  addBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: '#fff', lineHeight: 20 },

  // Smart Timing
  timingCard: { marginBottom: Spacing.xs, padding: Spacing.sm },

  // Shopping list button
  shoppingListBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: Colors.primary.default, borderRadius: 12,
    paddingVertical: 12, marginBottom: Spacing.md,
  },
  shoppingListBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#fff' },
  timingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  timingLeft: { flex: 1, gap: 4 },
  timingRight: { alignItems: 'flex-end', marginLeft: Spacing.sm },
  timingDetail: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary },
  timingValid: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.text.tertiary },
  timingUrgent: { fontFamily: 'DMSans_600SemiBold', fontSize: 12, color: '#E85D3A' },
  timingProduct: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary, marginBottom: 2 },

  // Savings banner
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
  savingsText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.primary, flex: 1 },
  savingsBtn: { backgroundColor: Colors.primary.default, paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  savingsBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 12, color: '#FFF' },
});
