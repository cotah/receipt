import { useState, useRef, useCallback } from 'react';
import api from '../services/api';

// --- Types ---

interface StorePrice {
  store_name: string;
  unit_price: number;
  is_on_offer: boolean;
  last_seen: string;
  confirmations: number;
  is_cheapest: boolean;
  saving_vs_most_expensive: number | null;
}

interface PriceComparison {
  product_name: string;
  unit: string | null;
  last_updated: string;
  stores: StorePrice[];
}

interface BasketResult {
  summary: { store: string; total_estimated: number; items_available: number; items_missing: number; savings_vs_most_expensive: number }[];
  split_recommendation: { message: string; total_with_split: number } | null;
}

interface LeafletOffer {
  store: string;
  product_name: string;
  unit_price: number;
  original_price: number | null;
  discount_percent: number | null;
  category: string;
  valid_from: string;
  valid_until: string;
}

// Smart search types
export interface SearchStoreEntry {
  store_name: string;
  product_name: string;
  unit_price: number;
  is_on_offer: boolean;
  is_cheapest: boolean;
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

export interface SmartSearchResponse {
  query: string;
  results: SearchResult[];
  total: number;
}

// Alternatives types
export interface Alternative {
  product_name: string;
  product_key: string;
  store_name: string;
  unit_price: number;
  is_on_offer: boolean;
  search_term: string;
}

export interface AlternativesResponse {
  product_name: string;
  alternatives: Alternative[];
  total: number;
}

export function usePrices() {
  const [comparison, setComparison] = useState<PriceComparison | null>(null);
  const [basket, setBasket] = useState<BasketResult | null>(null);
  const [offers, setOffers] = useState<LeafletOffer[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  // Smart search state
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearching, setIsSearching] = useState(false);
  const searchTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Alternatives state
  const [alternatives, setAlternatives] = useState<Alternative[]>([]);
  const [altProductName, setAltProductName] = useState('');
  const [isLoadingAlts, setIsLoadingAlts] = useState(false);

  // Selected product for detail view
  const [selectedProduct, setSelectedProduct] = useState<SearchResult | null>(null);

  const compareProduct = async (product: string, area?: string) => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/prices/compare', { params: { product, area } });
      setComparison(data);
    } catch (err) {
      console.error('[Prices] compare error:', err);
      setComparison(null);
    } finally {
      setIsLoading(false);
    }
  };

  const calculateBasket = async (items: string[]) => {
    setIsLoading(true);
    try {
      const { data } = await api.post('/prices/basket', { items });
      setBasket(data);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchLeafletOffers = async (store?: string, category?: string) => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/prices/leaflet-offers', { params: { store, category } });
      setOffers(data.offers);
    } finally {
      setIsLoading(false);
    }
  };

  // Smart search with debounce
  const smartSearch = useCallback((query: string) => {
    setSearchQuery(query);

    if (searchTimer.current) {
      clearTimeout(searchTimer.current);
    }

    if (!query || query.trim().length < 2) {
      setSearchResults([]);
      setIsSearching(false);
      return;
    }

    setIsSearching(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const { data } = await api.get<SmartSearchResponse>('/prices/smart-search', {
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

    setAltProductName(productName);
    setIsLoadingAlts(true);
    setAlternatives([]);

    try {
      const { data } = await api.get<AlternativesResponse>('/prices/alternatives', {
        params: { product_name: productName, limit: 6 },
      });
      setAlternatives(data.alternatives || []);
    } catch (err) {
      console.error('[Prices] alternatives error:', err);
      setAlternatives([]);
    } finally {
      setIsLoadingAlts(false);
    }
  }, []);

  // Select a product (opens detail + triggers alternatives)
  const selectProduct = useCallback((product: SearchResult) => {
    setSelectedProduct(product);
    fetchAlternatives(product.display_name);
  }, [fetchAlternatives]);

  const clearSelection = useCallback(() => {
    setSelectedProduct(null);
    setAlternatives([]);
    setAltProductName('');
  }, []);

  const clearSearch = useCallback(() => {
    setSearchResults([]);
    setSearchQuery('');
    setAlternatives([]);
    setAltProductName('');
    setSelectedProduct(null);
  }, []);

  return {
    // Legacy
    comparison, basket, offers, isLoading,
    compareProduct, calculateBasket, fetchLeafletOffers,
    // Smart search
    searchResults, searchQuery, isSearching, smartSearch, clearSearch,
    // Product detail
    selectedProduct, selectProduct, clearSelection,
    // Alternatives
    alternatives, altProductName, isLoadingAlts, fetchAlternatives,
  };
}
