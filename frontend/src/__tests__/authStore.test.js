import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '../stores/authStore'

describe('authStore.js', () => {
  const initialState = useAuthStore.getState()
  
  beforeEach(() => {
    useAuthStore.setState(initialState, true)
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('Initial state', () => {
    it('has correct initial state', () => {
      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.token).toBeNull()
      expect(state.isAuthenticated).toBe(false)
      expect(state.isLoading).toBe(true)
      expect(state.calcMode).toBe('fast')
    })
  })

  describe('initAuth()', () => {
    it('sets state when valid user exists in localStorage', () => {
      const mockUser = { id: 1, role: 'user' }
      localStorage.setItem('api_user', JSON.stringify(mockUser))

      useAuthStore.getState().initAuth()

      const state = useAuthStore.getState()
      expect(state.user).toEqual({ ...mockUser, subscription_type: 'free' })
      expect(state.token).toBeNull()
      expect(state.isAuthenticated).toBe(true)
      expect(state.isLoading).toBe(false)
    })

    it('clears storage and sets isLoading false when user is invalid JSON', () => {
      localStorage.setItem('api_user', 'invalid-json')

      useAuthStore.getState().initAuth()

      const state = useAuthStore.getState()
      expect(state.isLoading).toBe(false)
      expect(state.user).toBeNull()
      expect(localStorage.getItem('api_user')).toBeNull()
    })

    it('sets isLoading false when user is missing', () => {
      useAuthStore.getState().initAuth()

      expect(useAuthStore.getState().isLoading).toBe(false)
      expect(useAuthStore.getState().isAuthenticated).toBe(false)
    })
  })

  describe('setAuth()', () => {
    it('saves user to localStorage and updates state (token not stored)', () => {
      const mockUser = { id: 2 }
      const mockToken = 'new-token'

      useAuthStore.getState().setAuth(mockUser, mockToken)

      const state = useAuthStore.getState()
      expect(state.user).toEqual({ ...mockUser, subscription_type: 'free' })
      expect(state.token).toBeNull()
      expect(state.isAuthenticated).toBe(true)

      expect(localStorage.getItem('api_token')).toBeNull()
      expect(localStorage.getItem('api_user')).toBe(
        JSON.stringify({ ...mockUser, subscription_type: 'free' })
      )
    })

    it('normalizes subscription_type from user_type during login', () => {
      const mockUser = { id: 3, user_type: 'professional' }

      useAuthStore.getState().setAuth(mockUser, 'tier-token')

      const state = useAuthStore.getState()
      expect(state.user).toEqual({
        id: 3,
        user_type: 'professional',
        subscription_type: 'professional',
      })
      expect(JSON.parse(localStorage.getItem('api_user'))).toEqual({
        id: 3,
        user_type: 'professional',
        subscription_type: 'professional',
      })
    })
  })

  describe('setToken()', () => {
    it('syncs state and localStorage', () => {
      useAuthStore.getState().setToken('refreshed-token')

      expect(useAuthStore.getState().token).toBe('refreshed-token')
      expect(useAuthStore.getState().isAuthenticated).toBe(true)
      expect(localStorage.getItem('api_token')).toBe('refreshed-token')
    })
  })

  describe('logout()', () => {
    it('removes keys from localStorage and resets state', () => {
      useAuthStore.setState({
        user: { id: 1 },
        token: 'token',
        isAuthenticated: true,
      })
      localStorage.setItem('api_user', 'user')

      useAuthStore.getState().logout()

      const state = useAuthStore.getState()
      expect(state.user).toBeNull()
      expect(state.token).toBeNull()
      expect(state.isAuthenticated).toBe(false)

      expect(localStorage.getItem('api_user')).toBeNull()
    })
  })

  describe('setCalcMode()', () => {
    it('updates calcMode', () => {
      useAuthStore.getState().setCalcMode('detailed')
      expect(useAuthStore.getState().calcMode).toBe('detailed')
    })
  })

  describe('setUser()', () => {
    it('updates user', () => {
      const mockUser = { name: 'Test' }
      useAuthStore.getState().setUser(mockUser)
      expect(useAuthStore.getState().user).toEqual({
        ...mockUser,
        subscription_type: 'free',
      })
    })
  })

  describe('hasPermission()', () => {
    it('returns false if user is null', () => {
      useAuthStore.setState({ user: null })
      expect(useAuthStore.getState().hasPermission('/pricing')).toBe(false)
    })

    it('returns true for all pages if user is admin', () => {
      useAuthStore.setState({ user: { role: 'admin' } })
      expect(useAuthStore.getState().hasPermission('/users')).toBe(true)
      expect(useAuthStore.getState().hasPermission('/pricing')).toBe(true)
    })

    it('returns true for subset pages if user is regular user', () => {
      useAuthStore.setState({ user: { role: 'user' } })
      expect(useAuthStore.getState().hasPermission('/pricing')).toBe(true)
      expect(useAuthStore.getState().hasPermission('/logistics')).toBe(true)
    })

    it('returns false for admin pages if user is regular user', () => {
      useAuthStore.setState({ user: { role: 'user' } })
      expect(useAuthStore.getState().hasPermission('/users')).toBe(false)
      expect(useAuthStore.getState().hasPermission('/settings')).toBe(false)
    })
  })

  describe('isAdmin()', () => {
    it('returns true if role is admin', () => {
      useAuthStore.setState({ user: { role: 'admin' } })
      expect(useAuthStore.getState().isAdmin()).toBe(true)
    })

    it('returns false if role is not admin', () => {
      useAuthStore.setState({ user: { role: 'user' } })
      expect(useAuthStore.getState().isAdmin()).toBe(false)
    })

    it('returns false if user is null', () => {
      useAuthStore.setState({ user: null })
      expect(useAuthStore.getState().isAdmin()).toBe(false)
    })
  })

  describe('subscription helpers', () => {
    it('getSubscriptionType returns normalized subscription tier', () => {
      useAuthStore.getState().setUser({ id: 8, user_type: 'enterprise' })

      expect(useAuthStore.getState().getSubscriptionType()).toBe('enterprise')
    })

    it('getSubscriptionType falls back to free when user is missing', () => {
      useAuthStore.setState({ user: null })

      expect(useAuthStore.getState().getSubscriptionType()).toBe('free')
    })
  })
})
