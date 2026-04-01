import React, { useState, useEffect, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, StyleSheet, ActivityIndicator, Alert, TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter } from 'expo-router';
import { Feather } from '@expo/vector-icons';


import Input from '../../components/ui/Input';
import Card from '../../components/ui/Card';
import Badge from '../../components/ui/Badge';
import StoreTag from '../../components/prices/StoreTag';
import ExpiryBadge from '../../components/prices/ExpiryBadge';
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
  const [autoSelectFirst, setAutoSelectFirst] = useState(false);
  const [eligibleAlerts, setEligibleAlerts] = useState<EligibleAlert[]>([]);
  const [confirmedIds, setConfirmedIds] = useState<Set<string>>(new Set());
  const [addedToList, setAddedToList] = useState<Map<string, string>>(new Map());
  const [timing, setTiming] = useState<any>(null);
  const router = useRouter();

  const toggleShoppingList = useCallback(async (name: string, store: string, price: number, category?: string) => {
    const key = `${name}-${store}`;
    const existingId = addedToList.get(key);
    if (existingId) {
      // Remove from list
      try {
        if (existingId !== 'exists') {
          await api.delete(`/shopping-list/${existingId}`);
        }
        setAddedToList(prev => { const n = new Map(prev); n.delete(key); return n; });
      } catch {
        // If delete fails, still remove from UI state so button isn't stuck
        setAddedToList(prev => { const n = new Map(prev); n.delete(key); return n; });
      }
    } else {
      // Add to list
      try {
        const { data } = await api.post('/shopping-list/add', {
          product_name: name, store_name: store, unit_price: price,
          category: category || 'Other', source: 'deal',
        });
        if (data.status === 'exists') {
          // Already in list — show brief confirmation, don't add to map
          Alert.alert('Already in list', `${name} is already in your shopping list`);
          return;
        }
        const itemId = data.item?.id;
        if (itemId) {
          setAddedToList(prev => new Map(prev).set(key, itemId));
        }
      } catch {
        Alert.alert('Error', 'Could not add to list');
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

  // Auto-select first result when clicking from "Also available"
  useEffect(() => {
    if (autoSelectFirst && searchResults.length > 0 && !isSearching) {
      setAutoSelectFirst(false);
      selectProduct(searchResults[0]);
    }
  }, [searchResults, isSearching, autoSelectFirst]);

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
            {/* Search bar with clear X */}
            <View style={styles.searchBar}>
              <Feather name="search" size={16} color="rgba(255,255,255,0.35)" />
              <TextInput
                placeholder="Search products... (e.g. brioche, milk, nutella)"
                placeholderTextColor="rgba(255,255,255,0.3)"
                value={searchText}
                onChangeText={handleSearchChange}
                returnKeyType="search"
                style={styles.searchInput}
              />
              {searchText.length > 0 && (
                <Pressable onPress={() => { setSearchText(''); clearSearch(); }} hitSlop={12}>
                  <Feather name="x" size={18} color="rgba(255,255,255,0.5)" />
                </Pressable>
              )}
            </View>

            {/* Loading */}
            {isSearching && (
              <View style={styles.loadingRow}>
                <ActivityIndicator size="small" color={'#7DDFAA'} />
                <Text style={styles.loadingText}>Searching...</Text>
              </View>
            )}

            {/* Product Detail View */}
            {selectedProduct && !isSearching && (
              <View style={styles.detailSection}>
                {/* Back + Title */}
                <View style={styles.detailHeader}>
                  <Pressable onPress={handleBack} style={styles.detailBackBtn}>
                    <Feather name="arrow-left" size={18} color="rgba(255,255,255,0.5)" />
                  </Pressable>
                  <Text style={styles.detailTitle}>{selectedProduct.display_name}</Text>
                </View>

                {/* Comparison card with bars */}
                <View style={styles.barsCard}>
                  <View style={styles.barsHeader}>
                    <Text style={styles.barsCount}>{selectedProduct.stores.length} stores compared</Text>
                    {selectedProduct.potential_saving && selectedProduct.potential_saving > 0 && (
                      <View style={styles.savePill}>
                        <Text style={styles.savePillText}>Save {formatCurrency(selectedProduct.potential_saving ?? 0)}</Text>
                      </View>
                    )}
                  </View>

                  {/* Price bars */}
                  {selectedProduct.stores
                    .sort((a, b) => a.unit_price - b.unit_price)
                    .map((store, i) => {
                      const maxPrice = selectedProduct.stores[selectedProduct.stores.length - 1]?.unit_price || store.unit_price;
                      const barWidth = Math.max(15, (store.unit_price / maxPrice) * 100);
                      const storeKey = store.store_name.toLowerCase().replace(/\s/g, '');
                      const barColor = (Colors.stores as any)[storeKey] || 'rgba(255,255,255,0.15)';
                      return (
                        <View key={store.store_name} style={styles.barRow}>
                          <Text style={styles.barStoreName}>{store.store_name.length > 6 ? store.store_name.substring(0, 6) : store.store_name}</Text>
                          <View style={styles.barTrack}>
                            <View style={[styles.barFill, { width: `${barWidth}%` as any, backgroundColor: barColor }]} />
                          </View>
                          <Text style={[styles.barPrice, i === 0 && styles.barPriceCheapest]}>{formatCurrency(store.unit_price)}</Text>
                          {i === 0 && (
                            <View style={styles.barCheck}>
                              <Feather name="check" size={10} color="#7DDFAA" />
                            </View>
                          )}
                        </View>
                      );
                    })}
                </View>

                {/* Value tip */}
                {selectedProduct.value_tip && (
                  <View style={styles.valueTipDetail}>
                    <Feather name="trending-down" size={14} color="#7DDFAA" />
                    <Text style={styles.valueTipDetailText}>
                      {selectedProduct.value_tip.message}
                    </Text>
                  </View>
                )}

                {/* AI Alternatives — "Also available" */}
                <View style={styles.altSection}>
                  <Text style={styles.altTitle}>Also available</Text>

                  {isLoadingAlts && (
                    <View style={styles.loadingRow}>
                      <ActivityIndicator size="small" color="#7DDFAA" />
                      <Text style={styles.loadingText}>Finding alternatives...</Text>
                    </View>
                  )}

                  {!isLoadingAlts && alternatives.length === 0 && (
                    <Text style={styles.altEmpty}>No alternatives found</Text>
                  )}

                  {alternatives.length > 0 && (
                    <View style={styles.altCard}>
                      {alternatives.map((alt, i) => (
                        <Pressable
                          key={`${alt.product_key}-${i}`}
                          onPress={() => {
                            setSearchText(alt.product_name);
                            clearSelection();
                            setAutoSelectFirst(true);
                            smartSearch(alt.product_name);
                          }}
                          style={[styles.altRow, i === alternatives.length - 1 && { borderBottomWidth: 0 }]}
                        >
                          <View style={[styles.altDot, { backgroundColor: (Colors.stores as any)[alt.store_name.toLowerCase().replace(/\s/g, '')] || 'rgba(255,255,255,0.2)' }]} />
                          <View style={{ flex: 1 }}>
                            <Text style={styles.altName} numberOfLines={1}>{alt.product_name}</Text>
                            <Text style={styles.altStore}>{alt.store_name}</Text>
                          </View>
                          <View style={styles.altRight}>
                            <Text style={styles.altPrice}>{formatCurrency(alt.unit_price)}</Text>
                            {alt.price_per_100 && (
                              <Text style={styles.altPerUnit}>{`€${(alt.price_per_100 / 100).toFixed(2)}/100g`}</Text>
                            )}
                          </View>
                          <Feather name="chevron-right" size={14} color="rgba(255,255,255,0.2)" />
                        </Pressable>
                      ))}
                    </View>
                  )}
                </View>

                {/* Add to shopping list button */}
                {selectedProduct.stores.length > 0 && (
                  <Pressable
                    onPress={() => {
                      const cheapest = selectedProduct.stores[0];
                      if (cheapest) toggleShoppingList(cheapest.product_name, cheapest.store_name, cheapest.unit_price, '');
                    }}
                    style={styles.addToListBtn}
                  >
                    <Text style={styles.addToListText}>
                      {addedToList.has(`${selectedProduct.stores[0]?.product_name}-${selectedProduct.stores[0]?.store_name}`) 
                        ? '✓ Added to shopping list' 
                        : 'Add to shopping list'}
                    </Text>
                  </Pressable>
                )}
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
                      {result.value_tip && (
                        <View style={styles.valueTip}>
                          <Text style={styles.valueTipText}>
                            💡 {result.value_tip.quantity}x {result.value_tip.product_name} at {result.value_tip.store_name} = €{result.value_tip.total_price.toFixed(2)} (save €{result.value_tip.saving.toFixed(2)})
                          </Text>
                        </View>
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
                <ActivityIndicator size="small" color={'#7DDFAA'} />
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
                            <ExpiryBadge validUntil={deal.valid_until} />
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
                            <ExpiryBadge validUntil={deal.valid_until} />
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
                            <ExpiryBadge validUntil={deal.valid_until} />
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
  title: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 28, color: '#FFFFFF', paddingHorizontal: Spacing.md, paddingTop: Spacing.md },

  // Search bar
  searchBar: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.12)',
    borderRadius: 14, paddingHorizontal: 14, marginBottom: 12,
  },
  searchInput: {
    flex: 1, fontFamily: 'DMSans_400Regular', fontSize: 15,
    color: '#FFFFFF', paddingVertical: 12,
  },
  tabs: { flexDirection: 'row', paddingHorizontal: Spacing.md, marginTop: Spacing.md, gap: Spacing.sm },
  tab: { flex: 1, paddingVertical: Spacing.sm, alignItems: 'center', borderRadius: 9999, backgroundColor: 'rgba(255,255,255,0.06)', borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.10)' },
  tabActive: { backgroundColor: 'rgba(80,200,120,0.20)', borderColor: 'rgba(80,200,120,0.3)' },
  tabText: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: 'rgba(255,255,255,0.4)' },
  tabTextActive: { color: '#7DDFAA' },
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
  resultPrice: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 18, color: '#7DDFAA' },
  resultBottom: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: Spacing.sm },
  resultStores: { flexDirection: 'row', gap: 6, flexWrap: 'wrap', flex: 1 },
  resultHint: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, marginTop: 6 },
  valueTip: {
    marginTop: 6, backgroundColor: 'rgba(80,200,120,0.12)',
    borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6,
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
  },
  valueTipText: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: '#7DDFAA', lineHeight: 16 },
  valueTipDetail: {
    backgroundColor: 'rgba(80,200,120,0.12)', borderRadius: 12,
    padding: Spacing.sm, marginBottom: Spacing.sm,
    borderLeftWidth: 3, borderLeftColor: 'rgba(80,200,120,0.4)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
  },
  valueTipDetailTitle: { fontFamily: 'DMSans_700Bold', fontSize: 13, color: '#7DDFAA', marginBottom: 4 },
  valueTipDetailText: { fontFamily: 'DMSans_400Regular', fontSize: 13, color: 'rgba(125,223,170,0.8)', lineHeight: 18 },

  // Product detail — bar chart layout
  detailSection: { marginTop: Spacing.sm },
  detailHeader: { flexDirection: 'row', alignItems: 'center', gap: 10, marginBottom: 12 },
  detailBackBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    alignItems: 'center', justifyContent: 'center',
  },
  detailTitle: { fontFamily: 'DMSerifDisplay_400Regular', fontSize: 20, color: '#FFFFFF', flex: 1 },

  // Bars card
  barsCard: {
    backgroundColor: 'rgba(255,255,255,0.10)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.18)',
    borderRadius: 18, padding: 16, marginBottom: 12,
  },
  barsHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 14 },
  barsCount: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: 'rgba(255,255,255,0.45)' },
  savePill: {
    backgroundColor: 'rgba(80,200,120,0.15)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: 20, paddingHorizontal: 12, paddingVertical: 4,
  },
  savePillText: { fontFamily: 'DMSans_600SemiBold', fontSize: 12, color: '#7DDFAA' },

  barRow: { flexDirection: 'row', alignItems: 'center', gap: 6, marginBottom: 10 },
  barStoreName: { fontFamily: 'DMSans_600SemiBold', fontSize: 11, width: 46, color: 'rgba(255,255,255,0.55)', textAlign: 'right' },
  barTrack: {
    flex: 1, height: 18, borderRadius: 10,
    backgroundColor: 'rgba(255,255,255,0.04)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.06)',
    overflow: 'hidden',
  },
  barFill: { height: '100%', borderRadius: 10 },
  barPrice: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 13, color: 'rgba(255,255,255,0.6)', width: 44 },
  barPriceCheapest: { color: '#7DDFAA' },
  barCheck: {
    width: 18, height: 18, borderRadius: 9,
    backgroundColor: 'rgba(80,200,120,0.25)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.35)',
    alignItems: 'center', justifyContent: 'center',
  },

  // Add to shopping list button
  addToListBtn: {
    backgroundColor: 'rgba(80,200,120,0.15)',
    borderWidth: 0.5, borderColor: 'rgba(80,200,120,0.25)',
    borderRadius: 14, paddingVertical: 14, alignItems: 'center',
    marginBottom: 16,
  },
  addToListText: { fontFamily: 'DMSans_700Bold', fontSize: 15, color: '#FFFFFF' },

  // Alternatives — "Also available"
  altSection: { marginTop: 8, marginBottom: 12 },
  altTitle: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: 'rgba(255,255,255,0.7)', marginBottom: 8 },
  altEmpty: { fontFamily: 'DMSans_400Regular', fontSize: 14, color: 'rgba(255,255,255,0.35)', textAlign: 'center', paddingVertical: Spacing.md },
  altCard: {
    backgroundColor: 'rgba(255,255,255,0.08)',
    borderWidth: 0.5, borderColor: 'rgba(255,255,255,0.15)',
    borderRadius: 16, paddingHorizontal: 14, overflow: 'hidden',
  },
  altRow: {
    flexDirection: 'row', alignItems: 'center', gap: 10,
    paddingVertical: 10,
    borderBottomWidth: 0.5, borderBottomColor: 'rgba(255,255,255,0.06)',
  },
  altDot: { width: 8, height: 8, borderRadius: 4 },
  altName: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: 'rgba(255,255,255,0.85)' },
  altStore: { fontFamily: 'DMSans_400Regular', fontSize: 11, color: 'rgba(255,255,255,0.35)' },
  altRight: { alignItems: 'flex-end' },
  altPrice: { fontFamily: 'JetBrainsMono_600SemiBold', fontSize: 14, color: '#FFFFFF' },
  altPerUnit: { fontFamily: 'DMSans_400Regular', fontSize: 10, color: 'rgba(255,255,255,0.35)', marginTop: 1 },

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

  goldenCard: { marginBottom: Spacing.sm, borderWidth: 2, borderColor: '#F0D68A', borderRadius: BorderRadius.md },
  goldenName: { fontFamily: 'DMSans_700Bold', fontSize: 16, color: Colors.text.primary },
  goldenPromo: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: '#7DDFAA' },
  goldenPrice: { fontFamily: 'JetBrainsMono_700Bold', fontSize: 20, color: Colors.accent.amber },
  goldenWas: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, textDecorationLine: 'line-through' },

  refreshInfo: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.tertiary, textAlign: 'center', marginTop: Spacing.md, marginBottom: Spacing.lg },

  // Add to list button
  addBtn: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: 'rgba(80,200,120,0.20)',
    alignItems: 'center', justifyContent: 'center',
    marginTop: 4,
  },
  addBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 18, color: '#fff', lineHeight: 20 },

  // Smart Timing
  timingCard: { marginBottom: Spacing.xs, padding: Spacing.sm },

  // Shopping list button
  shoppingListBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8,
    backgroundColor: 'rgba(80,200,120,0.20)', borderRadius: 12,
    paddingVertical: 12, marginBottom: Spacing.md,
  },
  shoppingListBtnText: { fontFamily: 'DMSans_600SemiBold', fontSize: 15, color: '#fff' },
  timingRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  timingLeft: { flex: 1, gap: 4 },
  timingRight: { alignItems: 'flex-end', marginLeft: Spacing.sm },
  timingDetail: { fontFamily: 'DMSans_400Regular', fontSize: 12, color: Colors.text.secondary },
  timingValid: { fontFamily: 'DMSans_500Medium', fontSize: 12, color: Colors.text.tertiary },
  timingUrgent: { fontFamily: 'DMSans_600SemiBold', fontSize: 12, color: '#F0997B' },
  timingProduct: { fontFamily: 'DMSans_600SemiBold', fontSize: 14, color: Colors.text.primary, marginBottom: 2 },

  // Savings banner
  savingsBanner: {
    marginHorizontal: Spacing.md,
    marginTop: Spacing.sm,
    backgroundColor: 'rgba(80,200,120,0.08)',
    borderWidth: 0.5,
    borderColor: 'rgba(80,200,120,0.20)',
    borderRadius: 12,
    padding: Spacing.md,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: Spacing.sm,
  },
  savingsText: { fontFamily: 'DMSans_500Medium', fontSize: 13, color: Colors.text.primary, flex: 1 },
  savingsBtn: { backgroundColor: 'rgba(80,200,120,0.20)', paddingHorizontal: 14, paddingVertical: 8, borderRadius: 8 },
  savingsBtnText: { fontFamily: 'DMSans_700Bold', fontSize: 12, color: '#FFF' },
});
