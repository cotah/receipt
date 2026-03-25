-- Migration: Add referral_code and referred_by to profiles
-- Run in Supabase SQL Editor

-- Referral code (unique per user, e.g. SMART-ABC123)
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS referral_code TEXT UNIQUE;

-- Who referred this user
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS referred_by TEXT;

-- Plan and usage columns (if not already added)
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS plan TEXT DEFAULT 'free' CHECK (plan IN ('free','pro'));
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS plan_expires_at TIMESTAMPTZ;
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS scans_this_month INTEGER DEFAULT 0;
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS scans_month_reset DATE;
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS chat_queries_today INTEGER DEFAULT 0;
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS chat_queries_reset DATE;
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS points INTEGER DEFAULT 0;
ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS is_admin BOOLEAN DEFAULT FALSE;
