import { useState } from 'react';
import api from '../services/api';

interface MonthlyReport {
  period: string;
  summary: {
    total_spent: number;
    total_saved: number;
    receipts_count: number;
    items_count: number;
    avg_basket_size: number;
    vs_previous_month: { amount: number; percent: number; trend: string };
  };
  by_store: { store: string; total: number; visits: number; percentage: number }[];
  by_category: { category: string; total: number; percentage: number; top_items: string[] }[];
  insights: string[];
  price_wins: { product: string; store: string; price: number; avg_market_price: number; saved: number }[];
}

interface YearlyOverview {
  year: number;
  months: { month: string; total: number; saved: number; receipts: number }[];
  year_total: number;
  year_saved: number;
}

export function useReport() {
  const [report, setReport] = useState<MonthlyReport | null>(null);
  const [yearlyData, setYearlyData] = useState<YearlyOverview | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const fetchMonthlyReport = async (month?: string) => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/reports/monthly', { params: month ? { month } : {} });
      setReport(data);
    } finally {
      setIsLoading(false);
    }
  };

  const fetchYearlyOverview = async () => {
    setIsLoading(true);
    try {
      const { data } = await api.get('/reports/yearly-overview');
      setYearlyData(data);
    } finally {
      setIsLoading(false);
    }
  };

  return { report, yearlyData, isLoading, fetchMonthlyReport, fetchYearlyOverview };
}
