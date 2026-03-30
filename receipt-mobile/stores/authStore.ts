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

    supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('[Auth] onAuthStateChange:', event, session?.user?.email);
      set({
        session,
        user: session?.user ?? null,
        isAuthenticated: !!session,
      });
      if (session) {
        // Small delay to ensure session is fully saved before fetching profile
        await new Promise(resolve => setTimeout(resolve, 500));
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
      if (!user) {
        console.warn('[Auth] fetchProfile: no user');
        return;
      }

      console.log('[Auth] fetchProfile for user:', user.id, user.email);

      // Fetch profile - use explicit columns to avoid any serialization issues
      const { data, error } = await supabase
        .from('profiles')
        .select('id, email, full_name, avatar_url, locale, currency, home_area, notify_alerts, notify_reports, push_token, referral_code, referred_by, plan, plan_expires_at, scans_this_month, scans_month_reset, chat_queries_today, chat_queries_reset, points, is_admin, phone')
        .eq('id', user.id)
        .single();

      if (error) {
        console.warn('[Auth] Profile fetch error:', error.code, error.message);
        // Profile doesn't exist — create it (new user from Google/Apple)
        if (error.code === 'PGRST116') {
          console.log('[Auth] Creating new profile for', user.email);
          const newProfile = {
            id: user.id,
            email: user.email,
            full_name: user.user_metadata?.full_name || user.user_metadata?.name || null,
            avatar_url: user.user_metadata?.avatar_url || user.user_metadata?.picture || null,
            plan: 'free',
          };
          const { data: created, error: createErr } = await supabase
            .from('profiles')
            .insert(newProfile)
            .select()
            .single();
          if (createErr) {
            console.error('[Auth] Profile create failed:', createErr.message);
          } else if (created) {
            console.log('[Auth] Profile created successfully');
            set({ profile: created as UserProfile });
          }
        }
        return;
      }

      if (data) {
        console.log('[Auth] Profile loaded:', data.email, 'plan:', data.plan);
        // Sync Google metadata if profile exists but missing data
        const updates: Record<string, string> = {};
        const googleName = user.user_metadata?.full_name || user.user_metadata?.name;
        const googleAvatar = user.user_metadata?.avatar_url || user.user_metadata?.picture;
        if (!data.full_name && googleName) updates.full_name = googleName;
        if ((!data.avatar_url || data.avatar_url.startsWith('data:')) && googleAvatar) {
          updates.avatar_url = googleAvatar;
        }
        if (!data.email && user.email) updates.email = user.email;

        if (Object.keys(updates).length > 0) {
          console.log('[Auth] Syncing Google metadata:', Object.keys(updates));
          await supabase.from('profiles').update(updates).eq('id', user.id);
          Object.assign(data, updates);
        }

        set({ profile: data as UserProfile });
      }
    } catch (err) {
      console.error('[Auth] fetchProfile failed:', err);
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
