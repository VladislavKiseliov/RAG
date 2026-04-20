import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { loginAdmin, logoutAdmin } from '../api/adminApi';

export const useAuthStore = create(
  persist(
    (set) => ({
      isAuthenticated: false,
      role: null,
      user: null,
      accessToken: null,
      refreshToken: null,
      isLoading: false,
      login: async (username, password) => {
        set({ isLoading: true });
        try {
          const data = await loginAdmin(username, password);
          localStorage.setItem('admin-access-token', data.access_token);
          localStorage.setItem('admin-refresh-token', data.refresh_token);
          set({
            isAuthenticated: true,
            role: data.role,
            user: data.user,
            accessToken: data.access_token,
            refreshToken: data.refresh_token,
          });
        } finally {
          set({ isLoading: false });
        }
      },
      logout: async () => {
        const refreshToken = localStorage.getItem('admin-refresh-token');
        await logoutAdmin(refreshToken);
        localStorage.removeItem('admin-access-token');
        localStorage.removeItem('admin-refresh-token');
        set({
          isAuthenticated: false,
          role: null,
          user: null,
          accessToken: null,
          refreshToken: null,
          isLoading: false,
        });
      },
    }),
    { name: 'admin-auth' },
  ),
);
