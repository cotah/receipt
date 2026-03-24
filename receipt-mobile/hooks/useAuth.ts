import { useEffect } from 'react';
import { useAuthStore } from '../stores/authStore';
import api from '../services/api';

export function useAuth() {
  const store = useAuthStore();

  useEffect(() => {
    store.initialize();
  }, []);

  const updateProfile = async (data: Record<string, any>) => {
    const { data: updated } = await api.patch('/users/me', data);
    store.setProfile(updated);
  };

  return {
    session: store.session,
    user: store.user,
    profile: store.profile,
    isLoading: store.isLoading,
    isAuthenticated: store.isAuthenticated,
    signIn: store.signInWithMagicLink,
    signOut: store.signOut,
    updateProfile,
  };
}
