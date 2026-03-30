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

// Track if we're already signing out to prevent loops
let isSigningOut = false;

api.interceptors.request.use(async (config) => {
  try {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    if (session?.access_token) {
      config.headers.Authorization = `Bearer ${session.access_token}`;
    }
  } catch {
    // If getSession fails, continue without auth — the API will return 401
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    // Only sign out on 401 ONCE to prevent loops
    if (error.response?.status === 401 && !isSigningOut) {
      isSigningOut = true;
      try {
        await supabase.auth.signOut();
      } catch {
        // Sign out failed — ignore
      } finally {
        // Reset after 5 seconds to allow future sign-outs
        setTimeout(() => { isSigningOut = false; }, 5000);
      }
    }
    return Promise.reject(error);
  }
);

export default api;
