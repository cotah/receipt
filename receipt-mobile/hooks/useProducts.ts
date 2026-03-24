import { useState } from 'react';
import api from '../services/api';

interface ProductHistory {
  product_name: string;
  category: string;
  purchase_count: number;
  avg_days_between_purchases: number | null;
  predicted_next_purchase: string | null;
  price_history: { date: string; store: string; price: number }[];
  avg_price: number;
  cheapest_ever: { price: number; store: string; date: string } | null;
  most_expensive_ever: { price: number; store: string; date: string } | null;
}

interface CategorySummary {
  name: string;
  total_spent: number;
  percentage: number;
  items_count: number;
  trend: string;
  trend_percent: number;
}

interface RunningLowItem {
  product_name: string;
  last_purchased: string;
  avg_days_cycle: number;
  days_since_last: number;
  overdue_by_days: number;
  urgency: 'low' | 'medium' | 'high';
  typical_store: string | null;
  typical_price: number | null;
  best_current_price: { store: string; price: number } | null;
}

export function useProducts() {
  const [history, setHistory] = useState<ProductHistory | null>(null);
  const [categories, setCategories] = useState<CategorySummary[]>([]);
  const [runningLow, setRunningLow] = useState<RunningLowItem[]>([]);
  const [isLoading, setIsLoading] = useState(false);

  const fetchProductHistory = async (name: string, months = 6) => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/products/history', { params: { name, months } });
      setHistory(data);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchCategories = async (period = 'month') => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/products/categories', { params: { period } });
      setCategories(data.categories);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchRunningLow = async () => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/products/running-low');
      setRunningLow(data.items);
    } finally {
      setIsLoading(false);
    }
  };

  return { history, categories, runningLow, isLoading, fetchProductHistory, fetchCategories, fetchRunningLow };
}
