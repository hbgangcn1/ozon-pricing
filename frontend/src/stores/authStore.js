import { create } from 'zustand'

const adminPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/settings', '/users', '/plans', '/statistics', '/about']
const userPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/about']
const PROFESSIONAL_TIERS = ['professional', 'enterprise', 'gratitude', 'test']
const ENTERPRISE_TIERS = ['enterprise', 'gratitude', 'test']

const normalizeSubscriptionType = (user) => {
  if (!user) return user
  return {
    ...user,
    subscription_type: user.subscription_type || user.user_type || 'free',
  }
}

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
        const user = normalizeSubscriptionType(JSON.parse(userStr))
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
    const normalizedUser = normalizeSubscriptionType(user)
    localStorage.setItem('api_token', token)
    localStorage.setItem('api_user', JSON.stringify(normalizedUser))
    set({ user: normalizedUser, token, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('api_token')
    localStorage.removeItem('api_user')
    set({ user: null, token: null, isAuthenticated: false })
  },

  setUser: (user) => set({ user: normalizeSubscriptionType(user) }),

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

  getSubscriptionType: () => {
    const { user } = get()
    return user?.subscription_type || user?.user_type || 'free'
  },

  hasProfessionalAccess: () => {
    if (get().isAdmin()) return true
    const subscriptionType = get().getSubscriptionType()
    return PROFESSIONAL_TIERS.includes(subscriptionType)
  },

  hasEnterpriseAccess: () => {
    if (get().isAdmin()) return true
    const subscriptionType = get().getSubscriptionType()
    return ENTERPRISE_TIERS.includes(subscriptionType)
  },
}))
