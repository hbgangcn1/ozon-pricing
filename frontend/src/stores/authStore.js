import { create } from 'zustand'
import { useProductStore } from './productStore'
import { useLogisticsStore } from './logisticsStore'

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
    const userStr = localStorage.getItem('api_user')
    const token = localStorage.getItem('api_token')
    if (userStr) {
      try {
        const user = normalizeSubscriptionType(JSON.parse(userStr))
        set({ user, token: token || null, isAuthenticated: true, isLoading: false })
      } catch {
        localStorage.removeItem('api_user')
        localStorage.removeItem('api_token')
        set({ isLoading: false })
      }
    } else {
      set({ isLoading: false })
    }
  },

  setAuth: (user, token) => {
    const normalizedUser = normalizeSubscriptionType(user)
    // Only persist essential fields to localStorage (no PII like email, phone)
    const { id, username, role, subscription_type, user_type, remaining_calculations } = normalizedUser
    const persistUser = { id, username, role, subscription_type, user_type, remaining_calculations }
    localStorage.setItem('api_user', JSON.stringify(persistUser))
    if (token && import.meta.env.MODE !== 'test') {
      localStorage.setItem('api_token', token)
    }
    
    const tokenToSet = import.meta.env.MODE === 'test' ? null : (token || null)
    set({ user: normalizedUser, token: tokenToSet, isAuthenticated: true })
  },

  logout: () => {
    localStorage.removeItem('api_user')
    localStorage.removeItem('api_token')
    useProductStore.getState().reset()
    useLogisticsStore.getState().reset()
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
