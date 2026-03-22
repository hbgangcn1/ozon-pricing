import { create } from 'zustand'

const adminPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/settings', '/users', '/plans', '/statistics', '/about']
const userPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/about']

export const useAuthStore = create((set, get) => ({
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

  hasPermission: (page) => {
    const { user } = get()
    if (!user) return false
    if (user.role === 'admin') return true
    return userPages.includes(page)
  },

  isAdmin: () => {
    const { user } = get()
    return user?.role === 'admin'
  },
}))
