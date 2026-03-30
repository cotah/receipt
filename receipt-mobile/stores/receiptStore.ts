import { LayoutAnimation } from 'react-native';
import { create } from 'zustand';
import api from '../services/api';

export interface Receipt {
  id: string;
  store_name: string;
  store_branch: string | null;
  purchased_at: string;
  total_amount: number;
  discount_total: number;
  items_count: number;
  status: string;
  image_url: string | null;
}

export interface ReceiptDetail extends Receipt {
  subtotal: number | null;
  raw_text: string | null;
  items: ReceiptItem[];
}

export interface ReceiptItem {
  id: string;
  raw_name: string;
  normalized_name: string;
  category: string;
  brand: string | null;
  quantity: number;
  unit: string | null;
  unit_price: number;
  total_price: number;
  discount_amount: number;
  is_on_offer: boolean;
  collective_price: {
    cheapest_store: string;
    cheapest_price: number;
    difference: number;
  } | null;
}

interface ReceiptState {
  receipts: Receipt[];
  currentReceipt: ReceiptDetail | null;
  isLoading: boolean;
  isProcessing: boolean;
  processingStatus: { progress: number; message: string } | null;
  pagination: { page: number; totalPages: number; total: number };
  fetchReceipts: (page?: number, store?: string, month?: string) => Promise<void>;
  fetchReceiptDetail: (id: string) => Promise<void>;
  uploadReceipt: (fileUri: string, source: 'photo' | 'pdf') => Promise<string>;
  pollProcessingStatus: (receiptId: string) => Promise<void>;
  deleteReceipt: (id: string) => Promise<void>;
  clearCurrent: () => void;
}

export const useReceiptStore = create<ReceiptState>((set, get) => ({
  receipts: [],
  currentReceipt: null,
  isLoading: false,
  isProcessing: false,
  processingStatus: null,
  pagination: { page: 1, totalPages: 1, total: 0 },

  fetchReceipts: async (page = 1, store, month) => {
    set({ isLoading: true });
    try {
      const params: Record<string, string | number> = { page, per_page: 20 };
      if (store) params.store = store;
      if (month) params.month = month;
      const { data } = await api.get('/receipts', { params });
      // Filter out failed receipts (duplicates, invalid, etc) — they should never show
      const validReceipts = (data.data || []).filter((r: any) => r.status !== 'failed');
      set({
        receipts: page === 1 ? validReceipts : [...get().receipts, ...validReceipts],
        pagination: {
          page: data.pagination.page,
          totalPages: data.pagination.total_pages,
          total: data.pagination.total,
        },
      });
    } catch {
      // API error — don't crash, just stop loading
    } finally {
      set({ isLoading: false });
    }
  },

  fetchReceiptDetail: async (id: string) => {
    set({ isLoading: true });
    try {
      const { data } = await api.get(`/receipts/${id}`);
      set({ currentReceipt: data });
    } catch {
      // API error — don't crash, just stop loading
    } finally {
      set({ isLoading: false });
    }
  },

  uploadReceipt: async (fileUri: string, source: 'photo' | 'pdf') => {
    set({ isProcessing: true, processingStatus: { progress: 0, message: 'Uploading...' } });
    const formData = new FormData();
    formData.append('file', {
      uri: fileUri,
      name: source === 'pdf' ? 'receipt.pdf' : 'receipt.jpg',
      type: source === 'pdf' ? 'application/pdf' : 'image/jpeg',
    } as any);
    formData.append('source', source);

    const { data } = await api.post('/receipts/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return data.receipt_id;
  },

  pollProcessingStatus: async (receiptId: string) => {
    const startedAt = Date.now();
    const TIMEOUT = 60000;

    const poll = async () => {
      if (Date.now() - startedAt > TIMEOUT) {
        set({
          isProcessing: false,
          processingStatus: { progress: 0, message: 'Processing timed out. Please try again.' },
        });
        return;
      }
      try {
        const { data } = await api.get(`/receipts/${receiptId}/status`);
        set({ processingStatus: { progress: data.progress, message: data.message } });
        if (data.status === 'done' || data.status === 'failed') {
          set({ isProcessing: false });
          return;
        }
        setTimeout(poll, 2000);
      } catch {
        set({ isProcessing: false });
      }
    };
    await poll();
  },

  deleteReceipt: async (id: string) => {
    await api.delete(`/receipts/${id}`);
    LayoutAnimation.configureNext(LayoutAnimation.Presets.easeInEaseOut);
    set({ receipts: get().receipts.filter((r) => r.id !== id) });
  },

  clearCurrent: () => set({ currentReceipt: null }),
}));
