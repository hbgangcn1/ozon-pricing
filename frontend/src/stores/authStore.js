import { create } from 'zustand'
import { useProductStore } from './productStore'
import { useLogisticsStore } from './logisticsStore'

const userPages = ['/pricing', '/logistics', '/account', '/subscription', '/payment', '/about']
const PROFESSIONAL_TIERS = ['professional', 'enterprise', 'gratitude', 'test']
const ENTERPRISE_TIERS = ['enterprise', 'gratitude', 'test']
const initialSessionKicked = { open: false, reason: null }

const normalizeSubscriptionType = (user) => {
  if (!user) return user
  return {
    ...user,
    subscription_type: user.subscription_type || user.user_type || 'free',
  }
}

const clearPersistedAuth = () => {
  localStorage.removeItem('api_user')
  localStorage.removeItem('api_token')
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
  } = user

  return {
    id,
    username,
    role,
    subscription_type,
    user_type,
    remaining_calculations,
    has_security_question,
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
    const token = localStorage.getItem('api_token')
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
      localStorage.setItem('api_token', resolvedToken)
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
    localStorage.setItem('api_token', token)
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
