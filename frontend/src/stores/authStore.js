import { create } from 'zustand'

const adminPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/settings', '/users', '/plans', '/statistics', '/about']
const userPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/about']

export const useAuthStore = create((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  calcMode: 'fast', // 'fast' | 'detailed'

  setCalcMode: (mode) => set({ calcMode: mode }),

  initAuth: () => {
    const token = localStorage.getItem('api_token')
    const userStr = localStorage.getItem('api_user')
    if (token && userStr) {
      try {
        const user = JSON.parse(userStr)
        set({ user, token, isAuthenticated: true, isLoading: false })
      } catch {
        localStorage.removeItem('api_token')
        localStorage.removeItem('api_user')
        set({ isLoading: false })
      }
    } else {
      localStorage.removeItem('api_token')
      localStorage.removeItem('api_user')
      set({ isLoading: false })
    }
  },

  setAuth: (user, token) => {
    localStorage.setItem('api_token', token)
    localStorage.setItem('api_user', JSON.stringify(user))
    set({ user, token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('api_token')
    localStorage.removeItem('api_user')
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
