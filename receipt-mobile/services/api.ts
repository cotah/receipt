import axios from 'axios';
import { supabase } from './supabase';

const api = axios.create({
  baseURL: process.env.EXPO_PUBLIC_API_URL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
    'ngrok-skip-browser-warning': 'true',
  },
});

// Track auth state to prevent loops
let isSigningOut = false;
let authFailCount = 0;

api.interceptors.request.use(async (config) => {
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
      authFailCount = 0; // Reset on successful token
    }
  } catch {
    // Continue without auth
  }
  return config;
});

api.interceptors.response.use(
  (response) => {
    authFailCount = 0;
    return response;
  },
  async (error) => {
    if (error.response?.status === 401) {
      authFailCount++;
      // Only sign out after 3 consecutive 401s AND not already signing out
      // This prevents sign-out loops from a single bad request
      if (authFailCount >= 3 && !isSigningOut) {
        isSigningOut = true;
        try {
          await supabase.auth.signOut();
        } catch {
          // Force clear local state even if signOut fails
        } finally {
          isSigningOut = false;
          authFailCount = 0;
        }
      }
    }
    return Promise.reject(error);
  }
);

export default api;
