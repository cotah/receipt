-- Short error reason for failed receipts
ALTER TABLE public.receipts
    ADD COLUMN IF NOT EXISTS error_reason TEXT;
