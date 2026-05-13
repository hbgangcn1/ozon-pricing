import { create } from 'zustand'
import { useProductStore } from './productStore'
import { useLogisticsStore } from './logisticsStore'
import { authAPI } from '../services/api'

const userPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/about']
const PROFESSIONAL_TIERS = ['professional', 'enterprise', 'gratitude', 'test']
const ENTERPRISE_TIERS = ['enterprise', 'gratitude', 'test']
const initialSessionKicked = { open: false, reason: null }
const REFRESH_THRESHOLD_SECONDS = 300
let refreshPromise = null

const normalizeSubscriptionType = (user) => {
  if (!user) return user
  return {
    ...user,
    subscription_type: user.subscription_type || user.user_type || 'free',
  }
}

const clearPersistedAuth = () => {
  localStorage.removeItem('api_user')
  sessionStorage.removeItem('api_token')
}

const resetLinkedStores = () => {
  useProductStore.getState().reset()
  useLogisticsStore.getState().reset()
}

const buildClearedAuthState = () => ({
  user: null,
  token: null,
  isAuthenticated: false,
  sessionKicked: initialSessionKicked,
  showSecurityDialog: false,
})

const buildPersistedUser = (user) => {
  if (!user) {
    return null
  }

  const {
    id,
    username,
    role,
    subscription_type,
    user_type,
    remaining_calculations,
    has_security_question,
    trial_used,
    trial_started_at,
    trial_expires_at,
    trial_plan_at_start,
  } = user

  return {
    id,
    username,
    role,
    subscription_type,
    user_type,
    remaining_calculations,
    has_security_question,
    trial_used: trial_used ?? 0,
    trial_started_at: trial_started_at ?? 0,
    trial_expires_at: trial_expires_at ?? 0,
    trial_plan_at_start: trial_plan_at_start ?? '',
  }
}

const persistNormalizedUser = (user) => {
  const persistedUser = buildPersistedUser(user)
  if (persistedUser) {
    localStorage.setItem('api_user', JSON.stringify(persistedUser))
  }
}

const buildAuthUserState = (user) => ({
  user,
  showSecurityDialog: !user?.has_security_question,
})

const clearAuthState = (set) => {
  clearPersistedAuth()
  resetLinkedStores()
  set(buildClearedAuthState())
}

export const useAuthStore = create((set, get) => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: true,
  calcMode: 'fast', // 'fast' | 'detailed'
  sessionKicked: initialSessionKicked,
  showSecurityDialog: false,

  setCalcMode: (mode) => set({ calcMode: mode }),
  setShowSecurityDialog: (open) => set({ showSecurityDialog: open }),

  initAuth: () => {
    const userStr = localStorage.getItem('api_user')
    const token = sessionStorage.getItem('api_token')
    if (userStr) {
      try {
        const user = normalizeSubscriptionType(JSON.parse(userStr))
        set({
          ...buildAuthUserState(user),
          token: token || null,
          isAuthenticated: true,
          isLoading: false,
          sessionKicked: initialSessionKicked,
        })
      } catch {
        clearPersistedAuth()
        set({ isLoading: false })
      }
    } else {
      set({ isLoading: false })
    }
  },

  setAuth: (authOrUser, token) => {
    const rawUser = authOrUser?.user ?? authOrUser
    const resolvedToken = authOrUser?.token ?? token
    const normalizedUser = normalizeSubscriptionType(rawUser)
    persistNormalizedUser(normalizedUser)
    if (resolvedToken && import.meta.env.MODE !== 'test') {
      sessionStorage.setItem('api_token', resolvedToken)
    }
    
    const tokenToSet = import.meta.env.MODE === 'test' ? null : (resolvedToken || null)
    set({
      ...buildAuthUserState(normalizedUser),
      token: tokenToSet,
      isAuthenticated: true,
      sessionKicked: initialSessionKicked,
    })
  },

  setToken: (token) => {
    sessionStorage.setItem('api_token', token)
    set({ token, isAuthenticated: true })
  },

  logout: () => {
    clearAuthState(set)
    set({ showSecurityDialog: false })
  },

  setSessionKicked: ({ reason }) => set({
    sessionKicked: { open: true, reason: reason ?? null },
  }),

  clearSessionKicked: () => {
    clearAuthState(set)
  },

  setUser: (user) => {
    const normalizedUser = normalizeSubscriptionType(user)
    persistNormalizedUser(normalizedUser)
    set(buildAuthUserState(normalizedUser))
  },

  getTokenExpiry: () => {
    const { token } = get()
    if (!token) return null
    try {
      const payload = JSON.parse(atob(token.split('.')[1]))
      if (!payload.exp) return null
      const now = Math.floor(Date.now() / 1000)
      return payload.exp - now
    } catch {
      return null
    }
  },

  refreshToken: async () => {
    if (refreshPromise) {
      return refreshPromise
    }
    const { token } = get()
    if (!token) {
      throw new Error('No token to refresh')
    }
    refreshPromise = authAPI.refreshAccess()
      .then((data) => {
        const newToken = data.access_token
        sessionStorage.setItem('api_token', newToken)
        set({ token: newToken })
        return newToken
      })
      .finally(() => {
        refreshPromise = null
      })
    return refreshPromise
  },

  shouldRefreshToken: () => {
    const expiry = get().getTokenExpiry()
    if (expiry === null) return false
    return expiry < REFRESH_THRESHOLD_SECONDS
  },

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

  isInTrial: () => {
    const { user } = get()
    if (!user || typeof user.trial_expires_at !== 'number') return false
    return user.trial_expires_at > Math.floor(Date.now() / 1000)
  },

  hasProfessionalAccess: () => {
    if (get().isAdmin()) return true
    const subscriptionType = get().getSubscriptionType()
    if (PROFESSIONAL_TIERS.includes(subscriptionType)) return true
    return get().isInTrial()
  },

  hasEnterpriseAccess: () => {
    if (get().isAdmin()) return true
    const subscriptionType = get().getSubscriptionType()
    return ENTERPRISE_TIERS.includes(subscriptionType)
  },
}))
