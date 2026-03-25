-- Add hash columns for duplicate detection
ALTER TABLE public.receipts
    ADD COLUMN IF NOT EXISTS image_hash TEXT,
    ADD COLUMN IF NOT EXISTS data_hash TEXT;

-- Indexes for fast duplicate lookups
CREATE INDEX IF NOT EXISTS idx_receipts_image_hash
    ON public.receipts(user_id, image_hash)
    WHERE image_hash IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_receipts_data_hash
    ON public.receipts(user_id, data_hash)
    WHERE data_hash IS NOT NULL;
