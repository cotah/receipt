-- Migration: Add barcode_catalog table
-- Stores EAN/GTIN barcodes mapped to products for barcode scanner feature
-- Data sources: Tesco catalog scraper + Cisean open DB (MIT license)

CREATE TABLE IF NOT EXISTS public.barcode_catalog (
    barcode         TEXT PRIMARY KEY,
    product_name    TEXT NOT NULL,
    product_key     TEXT NOT NULL,
    brand           TEXT DEFAULT '',
    category        TEXT DEFAULT 'Other',
    package_size    TEXT DEFAULT '',
    image_url       TEXT DEFAULT '',
    store_name      TEXT,
    last_seen       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_barcode_product_key ON barcode_catalog(product_key);
CREATE INDEX IF NOT EXISTS idx_barcode_category ON barcode_catalog(category);
CREATE INDEX IF NOT EXISTS idx_barcode_brand ON barcode_catalog(brand);

COMMENT ON TABLE barcode_catalog IS 'EAN/GTIN barcode → product mapping for barcode scanner feature';
