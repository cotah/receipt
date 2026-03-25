-- Migration: Add phone column to profiles
-- Run in Supabase SQL Editor

ALTER TABLE public.profiles
    ADD COLUMN IF NOT EXISTS phone TEXT;
