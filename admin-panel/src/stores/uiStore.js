import { create } from 'zustand';

export const useUiStore = create((set) => ({
  sidebarCollapsed: JSON.parse(localStorage.getItem('admin-sidebar-collapsed') || 'false'),
  lastUpdatedAt: null,
  refreshTick: 0,
  setSidebarCollapsed: (value) => {
    localStorage.setItem('admin-sidebar-collapsed', JSON.stringify(value));
    set({ sidebarCollapsed: value });
  },
  setLastUpdatedAt: (value) => set({ lastUpdatedAt: value }),
  requestRefresh: () => set((state) => ({ refreshTick: state.refreshTick + 1 })),
}));
