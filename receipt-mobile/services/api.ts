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

// In-memory token that authStore updates directly.
// This avoids depending on SecureStore (which fails with large Google tokens).
let _inMemoryToken: string | null = null;

export function setApiToken(token: string | null) {
  _inMemoryToken = token;
}

api.interceptors.request.use(async (config) => {
  // 1. Try in-memory token first (always works, set by authStore)
  if (_inMemoryToken) {
    config.headers.Authorization = `Bearer ${_inMemoryToken}`;
    return config;
  }
  // 2. Fallback to supabase getSession (works when SecureStore has space)
  try {
    const { data: { session } } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // Continue without auth
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Don't auto-signout on 401 — let the auth state handle it
    return Promise.reject(error);
  }
);

export default api;
