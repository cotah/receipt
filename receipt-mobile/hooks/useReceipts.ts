import { useReceiptStore } from '../stores/receiptStore';

export function useReceipts() {
  const store = useReceiptStore();
  return {
    receipts: store.receipts,
    currentReceipt: store.currentReceipt,
    isLoading: store.isLoading,
    isProcessing: store.isProcessing,
    processingStatus: store.processingStatus,
    pagination: store.pagination,
    fetchReceipts: store.fetchReceipts,
    fetchReceiptDetail: store.fetchReceiptDetail,
    uploadReceipt: store.uploadReceipt,
    pollProcessingStatus: store.pollProcessingStatus,
    deleteReceipt: store.deleteReceipt,
    clearCurrent: store.clearCurrent,
  };
}
