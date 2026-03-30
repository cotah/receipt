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
        // Sync Google name + avatar to profile if missing
        const profile = get().profile;
        const user = session.user;
        if (profile && user?.user_metadata) {
          const updates: Record<string, string> = {};
          const googleName = user.user_metadata.full_name || user.user_metadata.name;
          const googleAvatar = user.user_metadata.avatar_url || user.user_metadata.picture;
          if (!profile.full_name && googleName) updates.full_name = googleName;
          if ((!profile.avatar_url || profile.avatar_url.startsWith('data:')) && googleAvatar) {
            updates.avatar_url = googleAvatar;
          }
          if (Object.keys(updates).length > 0) {
            await supabase.from('profiles').update(updates).eq('id', user.id);
            set({ profile: { ...profile, ...updates } });
          }
        }
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

  fetchProfile: async () => {
    try {
      const { data: { user } } = await supabase.auth.getUser();
      if (!user) return;
      const { data } = await supabase
        .from('profiles')
        .select('*')
        .eq('id', user.id)
        .single();
      if (data) set({ profile: data as UserProfile });
    } catch {
      // Profile fetch failed — user will see empty profile but app won't crash
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
          await get().fetchProfile();
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
        await get().fetchProfile();
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      console.error('[DeepLink] Error:', msg);
    }
  },
}));
