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
}

interface AuthState {
  session: Session | null;
  user: User | null;
  profile: UserProfile | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  initialize: () => Promise<void>;
  signInWithMagicLink: (email: string) => Promise<{ error: Error | null }>;
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
    // Supabase appends tokens as a URL fragment:
    //   ...callback#access_token=X&refresh_token=Y&token_type=bearer&...
    const fragment = url.split('#')[1];
    if (!fragment) return;

    const params = new URLSearchParams(fragment);
    const access_token = params.get('access_token');
    const refresh_token = params.get('refresh_token');

    if (!access_token || !refresh_token) return;

    const { data, error } = await supabase.auth.setSession({
      access_token,
      refresh_token,
    });

    if (error) {
      console.error('Failed to set session from deep link:', error.message);
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
  },
}));
