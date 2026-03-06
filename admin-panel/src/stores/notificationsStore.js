import { create } from 'zustand';

export const useNotificationsStore = create((set) => ({
  items: [],
  add: (item) =>
    set((state) => ({
      items: [{ id: crypto.randomUUID(), createdAt: new Date().toISOString(), ...item }, ...state.items].slice(0, 50),
    })),
  clear: () => set({ items: [] }),
}));
