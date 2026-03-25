import { create } from 'zustand';
import { Session, User } from '@supabase/supabase-js';
import * as Linking from 'expo-linking';
import { supabase } from '../services/supabase';

export interface UserProfile {
  id: string;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  locale: string;
  currency: string;
  home_area: string | null;
  notify_alerts: boolean;
  notify_reports: boolean;
  points: number;
  referral_code: string | null;
  plan: 'free' | 'pro';
  plan_expires_at: string | null;
  scans_this_month: number;
  chat_queries_today: number;
  phone: string | null;
}

interface AuthState {
  session: Session | null;
  user: User | null;
  profile: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  initialize: () => Promise<void>;
  signInWithMagicLink: (email: string) => Promise<{ error: Error | null }>;
  signInWithPassword: (email: string, password: string) => Promise<{ error: Error | null }>;
  signUpWithPassword: (email: string, password: string, fullName: string, phone?: string) => Promise<{ error: Error | null }>;
  signInWithOAuth: (provider: 'apple' | 'google') => Promise<{ error: Error | null }>;
  signOut: () => Promise<void>;
  setProfile: (profile: UserProfile) => void;
  fetchProfile: () => Promise<void>;
  handleDeepLink: (url: string) => Promise<void>;
}

/**
 * Build the redirect URL dynamically so it works in every environment:
 *  - Expo Go tunnel → exp://eyrexmk-pasquetto-8081.exp.direct/--/auth/callback
 *  - Expo Go local  → exp://192.168.x.x:8081/--/auth/callback
 *  - Dev build      → receipt://auth/callback
 *  - Production     → receipt://auth/callback
 */
const redirectUrl = Linking.createURL('auth/callback');
const oauthRedirectUrl = 'receipt://auth/callback';

export const useAuthStore = create<AuthState>((set, get) => ({
  session: null,
  user: null,
  profile: null,
  isLoading: true,
  isAuthenticated: false,

  initialize: async () => {
    try {
      const { data: { session } } = await supabase.auth.getSession();
      if (session) {
        set({ session, user: session.user, isAuthenticated: true });
        await get().fetchProfile();
      }
    } finally {
      set({ isLoading: false });
    }

    supabase.auth.onAuthStateChange(async (_event, session) => {
      set({
        session,
        user: session?.user ?? null,
        isAuthenticated: !!session,
      });
      if (session) {
        await get().fetchProfile();
      } else {
        set({ profile: null });
      }
    });
  },

  signInWithMagicLink: async (email: string) => {
    const { error } = await supabase.auth.signInWithOtp({
      email,
      options: { emailRedirectTo: redirectUrl },
    });
    return { error: error ? new Error(error.message) : null };
  },

  signInWithPassword: async (email: string, password: string) => {
    const { error } = await supabase.auth.signInWithPassword({ email, password });
    return { error: error ? new Error(error.message) : null };
  },

  signUpWithPassword: async (email: string, password: string, fullName: string, phone?: string) => {
    const { error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        emailRedirectTo: redirectUrl,
        data: { full_name: fullName, phone: phone || undefined },
      },
    });
    if (!error) {
      // Update profile with phone if provided
      const { data: { user } } = await supabase.auth.getUser();
      if (user && phone) {
        await supabase.from('profiles').update({ phone, full_name: fullName }).eq('id', user.id);
      }
    }
    return { error: error ? new Error(error.message) : null };
  },

  signInWithOAuth: async (provider: 'apple' | 'google') => {
    const { error } = await supabase.auth.signInWithOAuth({
      provider,
      options: { redirectTo: oauthRedirectUrl },
    });
    return { error: error ? new Error(error.message) : null };
  },

  signOut: async () => {
    await supabase.auth.signOut();
    set({ session: null, user: null, profile: null, isAuthenticated: false });
  },

  setProfile: (profile) => set({ profile }),

  fetchProfile: async () => {
    const { data: { user } } = await supabase.auth.getUser();
    if (!user) return;
    const { data } = await supabase
      .from('profiles')
      .select('*')
      .eq('id', user.id)
      .single();
    if (data) set({ profile: data as UserProfile });
  },

  handleDeepLink: async (url: string) => {
    // Only process URLs from known schemes
    if (
      !url.startsWith('exp://') &&
      !url.startsWith('smartdocket://') &&
      !url.startsWith('receipt://')
    ) {
      return;
    }

    // Supabase appends tokens as a URL fragment:
    //   ...callback#access_token=X&refresh_token=Y&token_type=bearer&...
    const fragment = url.split('#')[1];
    if (!fragment) return;

    const params = new URLSearchParams(fragment);
    const access_token = params.get('access_token');
    const refresh_token = params.get('refresh_token');

    if (!access_token || !refresh_token) return;

    const MAX_RETRIES = 3;
    const RETRY_DELAY = 2000;
    const TIMEOUT_MS = 10000;

    for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
      try {
        const sessionPromise = supabase.auth.setSession({
          access_token,
          refresh_token,
        });

        const timeoutPromise = new Promise<never>((_, reject) =>
          setTimeout(() => reject(new Error('Connection timeout. Please try again.')), TIMEOUT_MS),
        );

        const { data, error } = await Promise.race([sessionPromise, timeoutPromise]);

        if (error) {
          console.error(`Deep link setSession error (attempt ${attempt}):`, error.message);
          if (attempt < MAX_RETRIES) {
            await new Promise((r) => setTimeout(r, RETRY_DELAY));
            continue;
          }
          return;
        }

        if (data.session) {
          set({
            session: data.session,
            user: data.session.user,
            isAuthenticated: true,
          });
          await get().fetchProfile();
        }
        return;
      } catch (e: unknown) {
        const msg = e instanceof Error ? e.message : String(e);
        console.error(`Deep link error (attempt ${attempt}/${MAX_RETRIES}):`, msg);
        if (attempt < MAX_RETRIES) {
          await new Promise((r) => setTimeout(r, RETRY_DELAY));
        }
      }
    }
    console.error('Deep link: all retries exhausted');
  },
}));
