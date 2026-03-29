import { useState, useRef, useCallback } from 'react';
import api from '../services/api';

// --- Smart search types ---
export interface SearchStoreEntry {
  store_name: string;
  product_name: string;
  unit_price: number;
  is_on_offer: boolean;
  is_cheapest: boolean;
  price_per_unit: number | null;
  price_per_unit_label: string | null;
}

export interface SearchResult {
  display_name: string;
  product_key: string;
  stores: SearchStoreEntry[];
  store_count: number;
  cheapest_price: number;
  cheapest_store: string;
  potential_saving: number | null;
}

// --- Alternatives types ---
export interface Alternative {
  product_name: string;
  product_key: string;
  store_name: string;
  unit_price: number;
  is_on_offer: boolean;
  search_term: string;
  price_per_100: number | null;
}

// --- Weekly deals types ---
export interface WeeklyDeal {
  id: string;
  product_key: string;
  product_name: string;
  store_name: string;
  current_price: number;
  avg_price_4w: number | null;
  min_price_ever: number | null;
  discount_pct: number | null;
  promotion_text: string | null;
  category: string;
  deal_type: 'global' | 'personalised' | 'golden';
  rank: number;
  valid_until: string;
}

export interface WeeklyDealsResponse {
  plan: string;
  trending: WeeklyDeal[];
  personalised: WeeklyDeal[];
  golden: WeeklyDeal[];
  total: number;
  refresh_days: number;
}

export function usePrices() {
  const [isLoading, setIsLoading] = useState(false);

  // Smart search state
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Alternatives state
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  const [isLoadingAlts, setIsLoadingAlts] = useState(false);

  // Selected product for detail view
  const [selectedProduct, setSelectedProduct] = useState<SearchResult | null>(null);

  // Weekly deals state
  const [weeklyDeals, setWeeklyDeals] = useState<WeeklyDealsResponse | null>(null);
  const [isLoadingDeals, setIsLoadingDeals] = useState(false);

  // Smart search with debounce
  const smartSearch = useCallback((query: string) => {
    setSearchQuery(query);
    if (searchTimer.current) clearTimeout(searchTimer.current);

    if (!query || query.trim().length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const { data } = await api.get('/prices/smart-search', {
          params: { q: query.trim(), limit: 20 },
        });
        setSearchResults(data.results || []);
      } catch (err) {
        console.error('[Prices] smart search error:', err);
        setSearchResults([]);
      } finally {
        setIsSearching(false);
      }
    }, 400);
  }, []);

  // AI alternatives
  const fetchAlternatives = useCallback(async (productName: string) => {
    if (!productName || productName.length < 2) return;
    setIsLoadingAlts(true);
    setAlternatives([]);
    try {
      const { data } = await api.get('/prices/alternatives', {
        params: { product_name: productName, limit: 6 },
      });
      setAlternatives(data.alternatives || []);
    } catch (err) {
      console.error('[Prices] alternatives error:', err);
    } finally {
      setIsLoadingAlts(false);
    }
  }, []);

  // Select product → detail + alternatives
  const selectProduct = useCallback((product: SearchResult) => {
    setSelectedProduct(product);
    fetchAlternatives(product.display_name);
  }, [fetchAlternatives]);

  const clearSelection = useCallback(() => {
    setSelectedProduct(null);
    setAlternatives([]);
  }, []);

  const clearSearch = useCallback(() => {
    setSearchResults([]);
    setSearchQuery('');
    setAlternatives([]);
    setSelectedProduct(null);
  }, []);

  // Weekly deals
  const fetchWeeklyDeals = useCallback(async () => {
    setIsLoadingDeals(true);
    try {
      const { data } = await api.get<WeeklyDealsResponse>('/deals/weekly');
      setWeeklyDeals(data);
    } catch (err) {
      console.error('[Deals] fetch error:', err);
      setWeeklyDeals(null);
    } finally {
      setIsLoadingDeals(false);
    }
  }, []);

  return {
    isLoading,
    // Smart search
    searchResults, searchQuery, isSearching, smartSearch, clearSearch,
    // Product detail
    selectedProduct, selectProduct, clearSelection,
    // Alternatives
    alternatives, isLoadingAlts,
    // Weekly deals
    weeklyDeals, isLoadingDeals, fetchWeeklyDeals,
  };
}
