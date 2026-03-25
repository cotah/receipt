-- Savings attribution: tracks when SmartDocket alerts led to real savings
CREATE TABLE IF NOT EXISTS public.savings_attributions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES profiles(id),
    alert_id UUID,
    receipt_id UUID REFERENCES receipts(id),
    product_name TEXT,
    store TEXT,
    price_paid FLOAT,
    price_elsewhere FLOAT,
    saving FLOAT,
    attribution TEXT CHECK (attribution IN ('automatic', 'confirmed', 'none')),
    alerted_at TIMESTAMPTZ,
    scanned_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_savings_user_id ON public.savings_attributions(user_id);
CREATE INDEX IF NOT EXISTS idx_savings_receipt_id ON public.savings_attributions(receipt_id);
CREATE INDEX IF NOT EXISTS idx_savings_alert_id ON public.savings_attributions(alert_id);

-- RLS
ALTER TABLE public.savings_attributions ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own savings"
    ON public.savings_attributions FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Service can insert savings"
    ON public.savings_attributions FOR INSERT
    WITH CHECK (true);
