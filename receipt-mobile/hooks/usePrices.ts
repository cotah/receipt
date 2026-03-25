import { useState } from 'react';
import api from '../services/api';

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

export function usePrices() {
  const [comparison, setComparison] = useState<PriceComparison | null>(null);
  const [basket, setBasket] = useState<BasketResult | null>(null);
  const [offers, setOffers] = useState<LeafletOffer[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const compareProduct = async (product: string, area?: string) => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/prices/compare', { params: { product, area } });
      console.log('[Prices] compare result:', JSON.stringify(data));
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

  return { comparison, basket, offers, isLoading, compareProduct, calculateBasket, fetchLeafletOffers };
}
