import { create } from 'zustand'

export const useLogisticsStore = create((set) => ({
  logistics: [],
  loading: false,
  error: null,

  setLogistics: (logistics) => set({ logistics }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),

  addLogistics: (item) =>
    set((state) => ({ logistics: [...state.logistics, item] })),

  updateLogistics: (id, updatedItem) =>
    set((state) => ({
      logistics: state.logistics.map((l) =>
        l.id === id ? { ...l, ...updatedItem } : l
      ),
    })),

  removeLogistics: (id) =>
    set((state) => ({
      logistics: state.logistics.filter((l) => l.id !== id),
    })),
}))
