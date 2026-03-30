import { create } from 'zustand';
import { Session, User } from '@supabase/supabase-js';
import * as Linking from 'expo-linking';
import { supabase } from '../services/supabase';
import api, { setApiToken } from '../services/api';

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
  fetchProfile: (accessToken?: string) => Promise<void>;
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
        setApiToken(session.access_token);
        set({ session, user: session.user, isAuthenticated: true });
        await get().fetchProfile(session.access_token);
      }
    } finally {
      set({ isLoading: false });
    }

    supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('[Auth] onAuthStateChange:', event, session?.user?.email);
      // CRITICAL: Set the in-memory token BEFORE anything else
      // This is needed because SecureStore can't store large Google OAuth tokens
      setApiToken(session?.access_token ?? null);
      set({
        session,
        user: session?.user ?? null,
        isAuthenticated: !!session,
      });
      if (session) {
        await get().fetchProfile(session.access_token);
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
    try {
      await supabase.auth.signOut();
    } catch {
      // Sign out from Supabase failed — still clear local state
    }
    set({ session: null, user: null, profile: null, isAuthenticated: false });
  },

  setProfile: (profile) => set({ profile }),

  fetchProfile: async (accessToken?: string) => {
    try {
      // Get token: use passed token first, fallback to session in state, then getSession
      let token = accessToken;
      if (!token) {
        token = get().session?.access_token;
      }
      if (!token) {
        try {
          const { data: { session } } = await supabase.auth.getSession();
          token = session?.access_token;
        } catch {}
      }
      if (!token) {
        console.warn('[Auth] fetchProfile: no token available');
        return;
      }

      console.log('[Auth] fetchProfile with token:', token.substring(0, 20) + '...');

      // Call API directly with the token — bypass the axios interceptor
      // which might fail if getSession() returns null (SecureStore issue)
      const baseURL = process.env.EXPO_PUBLIC_API_URL;
      const response = await fetch(`${baseURL}/users/me`, {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
      });

      if (!response.ok) {
        console.warn('[Auth] fetchProfile HTTP error:', response.status);
        return;
      }

      const data = await response.json();
      if (data) {
        console.log('[Auth] Profile loaded:', data.email, 'plan:', data.plan);
        set({ profile: data as UserProfile });
      }
    } catch (err: any) {
      console.warn('[Auth] fetchProfile failed:', err?.message || err);
    }
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

    try {
      // OAuth PKCE flow returns ?code= in query params
      const urlObj = new URL(url.replace('receipt://', 'https://placeholder/').replace('exp://', 'https://placeholder/'));
      const code = urlObj.searchParams.get('code');

      if (code) {
        console.log('[DeepLink] Exchanging code for session...');
        const { data, error } = await supabase.auth.exchangeCodeForSession(code);
        if (error) {
          console.error('[DeepLink] exchangeCodeForSession failed:', error.message);
          return;
        }
        if (data.session) {
          set({ session: data.session, user: data.session.user, isAuthenticated: true });
          await get().fetchProfile(data.session.access_token);
        }
        return;
      }

      // Magic link flow returns #access_token=X&refresh_token=Y
      const fragment = url.split('#')[1];
      if (!fragment) return;

      const params = new URLSearchParams(fragment);
      const access_token = params.get('access_token');
      const refresh_token = params.get('refresh_token');
      if (!access_token || !refresh_token) return;

      console.log('[DeepLink] Setting session from tokens...');
      const { data, error } = await supabase.auth.setSession({ access_token, refresh_token });
      if (error) {
        console.error('[DeepLink] setSession failed:', error.message);
        return;
      }
      if (data.session) {
        set({ session: data.session, user: data.session.user, isAuthenticated: true });
        await get().fetchProfile(data.session.access_token);
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error('[DeepLink] Error:', msg);
    }
  },
}));
