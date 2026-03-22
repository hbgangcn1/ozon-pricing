import { create } from 'zustand'

export const useAuthStore = create((set) => ({
  user: null,
  token: localStorage.getItem('api_token'),
  isAuthenticated: !!localStorage.getItem('api_token'),

  setAuth: (user, token) => {
    localStorage.setItem('api_token', token)
    set({ user, token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('api_token')
    set({ user: null, token: null, isAuthenticated: false })
  },

  setUser: (user) => set({ user }),
}))
