-- Receipt App — Supabase Database Schema
-- Run this in the Supabase SQL Editor

-- Extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- ============================================================
-- PROFILES (extends auth.users)
-- ============================================================
CREATE TABLE public.profiles (
    id              UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email           TEXT NOT NULL,
    full_name       TEXT,
    avatar_url      TEXT,
    locale          TEXT DEFAULT 'en-IE',
    currency        TEXT DEFAULT 'EUR',
    home_area       TEXT,
    phone           TEXT,
    notify_alerts   BOOLEAN DEFAULT TRUE,
    notify_reports  BOOLEAN DEFAULT TRUE,
    push_token      TEXT,
    plan            TEXT DEFAULT 'free' CHECK (plan IN ('free','pro')),
    plan_expires_at TIMESTAMPTZ,
    scans_this_month    INTEGER DEFAULT 0,
    scans_month_reset   DATE,
    chat_queries_today  INTEGER DEFAULT 0,
    chat_queries_reset  DATE,
    points          INTEGER DEFAULT 0,
    referral_code   TEXT UNIQUE,
    referred_by     TEXT,
    is_admin        BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

ALTER TABLE profiles ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_profile" ON profiles
    FOR ALL USING (auth.uid() = id);

-- Auto-create profile on signup
CREATE OR REPLACE FUNCTION public.handle_new_user()
RETURNS TRIGGER AS $$
BEGIN
    INSERT INTO public.profiles (id, email, full_name)
    VALUES (NEW.id, NEW.email, NEW.raw_user_meta_data->>'full_name');
    RETURN NEW;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

CREATE TRIGGER on_auth_user_created
    AFTER INSERT ON auth.users
    FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();

-- ============================================================
-- RECEIPTS
-- ============================================================
CREATE TABLE public.receipts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    store_name      TEXT NOT NULL,
    store_branch    TEXT,
    store_address   TEXT,
    purchased_at    TIMESTAMPTZ NOT NULL,
    total_amount    DECIMAL(10,2) NOT NULL,
    subtotal        DECIMAL(10,2),
    discount_total  DECIMAL(10,2) DEFAULT 0,
    image_url       TEXT,
    raw_text        TEXT,
    status          TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','done','failed')),
    source          TEXT DEFAULT 'photo'
                    CHECK (source IN ('photo','pdf','manual')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_receipts_user_id ON receipts(user_id);
CREATE INDEX idx_receipts_purchased_at ON receipts(purchased_at DESC);
CREATE INDEX idx_receipts_store_name ON receipts(store_name);

ALTER TABLE receipts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_receipts" ON receipts
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================
-- RECEIPT ITEMS
-- ============================================================
CREATE TABLE public.receipt_items (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    receipt_id          UUID NOT NULL REFERENCES receipts(id) ON DELETE CASCADE,
    user_id             UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    raw_name            TEXT NOT NULL,
    normalized_name     TEXT NOT NULL,
    category            TEXT NOT NULL,
    brand               TEXT,
    quantity            DECIMAL(10,3) DEFAULT 1,
    unit                TEXT,
    unit_price          DECIMAL(10,2) NOT NULL,
    total_price         DECIMAL(10,2) NOT NULL,
    discount_amount     DECIMAL(10,2) DEFAULT 0,
    is_on_offer         BOOLEAN DEFAULT FALSE,
    barcode             TEXT,
    embedding           vector(1536),
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_items_receipt_id ON receipt_items(receipt_id);
CREATE INDEX idx_items_user_id ON receipt_items(user_id);
CREATE INDEX idx_items_normalized_name ON receipt_items(normalized_name);
CREATE INDEX idx_items_category ON receipt_items(category);
CREATE INDEX idx_items_embedding ON receipt_items
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

ALTER TABLE receipt_items ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_items" ON receipt_items
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================
-- COLLECTIVE PRICES (anonymous)
-- ============================================================
CREATE TABLE public.collective_prices (
    id                  UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_key         TEXT NOT NULL,
    product_name        TEXT NOT NULL,
    category            TEXT NOT NULL,
    store_name          TEXT NOT NULL,
    store_branch        TEXT,
    home_area           TEXT,
    unit_price          DECIMAL(10,2) NOT NULL,
    unit                TEXT,
    is_on_offer         BOOLEAN DEFAULT FALSE,
    source              TEXT DEFAULT 'receipt'
                        CHECK (source IN ('receipt','leaflet','manual')),
    observed_at         TIMESTAMPTZ NOT NULL,
    expires_at          TIMESTAMPTZ NOT NULL,
    confirmation_count  INTEGER DEFAULT 1,
    created_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_prices_product_key ON collective_prices(product_key);
CREATE INDEX idx_prices_store ON collective_prices(store_name);
CREATE INDEX idx_prices_observed ON collective_prices(observed_at DESC);
CREATE INDEX idx_prices_expires ON collective_prices(expires_at);
CREATE INDEX idx_prices_area ON collective_prices(home_area);

-- ============================================================
-- ALERTS
-- ============================================================
CREATE TABLE public.alerts (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    type            TEXT NOT NULL
                    CHECK (type IN ('restock','price_drop','price_spike','weekly_report')),
    product_name    TEXT,
    store_name      TEXT,
    message         TEXT NOT NULL,
    data            JSONB,
    is_read         BOOLEAN DEFAULT FALSE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_alerts_user_id ON alerts(user_id);
CREATE INDEX idx_alerts_is_read ON alerts(user_id, is_read);

ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_alerts" ON alerts
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================
-- CHAT MESSAGES
-- ============================================================
CREATE TABLE public.chat_messages (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    session_id      UUID NOT NULL,
    role            TEXT NOT NULL CHECK (role IN ('user','assistant')),
    content         TEXT NOT NULL,
    context_used    JSONB,
    tokens_used     INTEGER,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_chat_user_session ON chat_messages(user_id, session_id);
CREATE INDEX idx_chat_created ON chat_messages(user_id, created_at DESC);

ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
CREATE POLICY "users_own_chat" ON chat_messages
    FOR ALL USING (auth.uid() = user_id);

-- ============================================================
-- LEAFLETS
-- ============================================================
CREATE TABLE public.leaflets (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    store_name      TEXT NOT NULL,
    valid_from      DATE NOT NULL,
    valid_until     DATE NOT NULL,
    pdf_url         TEXT,
    page_count      INTEGER,
    items_extracted INTEGER DEFAULT 0,
    status          TEXT DEFAULT 'pending'
                    CHECK (status IN ('pending','processing','done','failed')),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_leaflets_store ON leaflets(store_name);
CREATE INDEX idx_leaflets_valid ON leaflets(valid_from, valid_until);

-- ============================================================
-- USER PRODUCT PATTERNS (materialized view)
-- ============================================================
CREATE MATERIALIZED VIEW user_product_patterns AS
SELECT
    ri.user_id,
    ri.normalized_name,
    ri.category,
    COUNT(*)                                    AS purchase_count,
    AVG(ri.unit_price)                          AS avg_price,
    MIN(ri.unit_price)                          AS min_price_ever,
    MAX(ri.unit_price)                          AS max_price_ever,
    MAX(r.purchased_at)                         AS last_purchased_at,
    AVG(
        EXTRACT(EPOCH FROM (
            r.purchased_at - LAG(r.purchased_at) OVER (
                PARTITION BY ri.user_id, ri.normalized_name
                ORDER BY r.purchased_at
            )
        )) / 86400
    )                                           AS avg_days_between_purchases
FROM receipt_items ri
JOIN receipts r ON r.id = ri.receipt_id
GROUP BY ri.user_id, ri.normalized_name, ri.category;

CREATE INDEX idx_patterns_user ON user_product_patterns(user_id);
CREATE INDEX idx_patterns_last ON user_product_patterns(user_id, last_purchased_at DESC);

-- Function to refresh materialized view (called by worker via RPC)
CREATE OR REPLACE FUNCTION refresh_product_patterns()
RETURNS void AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY user_product_patterns;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- ============================================================
-- STORAGE BUCKET
-- ============================================================
INSERT INTO storage.buckets (id, name, public)
VALUES ('receipt-images', 'receipt-images', true)
ON CONFLICT (id) DO NOTHING;

CREATE POLICY "users_upload_own_receipts" ON storage.objects
    FOR INSERT WITH CHECK (
        bucket_id = 'receipt-images'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

CREATE POLICY "users_read_own_receipts" ON storage.objects
    FOR SELECT USING (
        bucket_id = 'receipt-images'
        AND auth.uid()::text = (storage.foldername(name))[1]
    );

-- ============================================================
-- REALTIME (enable for alerts)
-- ============================================================
ALTER PUBLICATION supabase_realtime ADD TABLE alerts;
