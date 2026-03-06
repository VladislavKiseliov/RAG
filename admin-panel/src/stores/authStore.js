import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { loginAdminMock, logoutAdminMock } from '../api/adminApi';

export const useAuthStore = create(
  persist(
    (set) => ({
      isAuthenticated: false,
      role: null,
      user: null,
      isLoading: false,
      login: async (username, password) => {
        set({ isLoading: true });
        const data = await loginAdminMock(username, password);
        set({
          isAuthenticated: true,
          role: data.role,
          user: data.user,
          isLoading: false,
        });
      },
      logout: async () => {
        await logoutAdminMock();
        set({ isAuthenticated: false, role: null, user: null, isLoading: false });
      },
    }),
    { name: 'admin-auth-mock' },
  ),
);
