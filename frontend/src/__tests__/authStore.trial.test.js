import { describe, it, expect, beforeEach, vi } from 'vitest'
import { useAuthStore } from '../stores/authStore'

vi.mock('../services/api', () => ({
  authAPI: { refreshAccess: vi.fn() },
}))

const nowSec = () => Math.floor(Date.now() / 1000)

describe('authStore trial-aware gating', () => {
  const initialState = useAuthStore.getState()

  beforeEach(() => {
    useAuthStore.setState(initialState, true)
    localStorage.clear()
    vi.clearAllMocks()
  })

  describe('isInTrial()', () => {
    it('returns true when trial_expires_at is in the future', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'free', trial_expires_at: nowSec() + 3600 },
      })
      expect(useAuthStore.getState().isInTrial()).toBe(true)
    })

    it('returns false when trial_expires_at is in the past', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'free', trial_expires_at: nowSec() - 60 },
      })
      expect(useAuthStore.getState().isInTrial()).toBe(false)
    })

    it('returns false when user is null', () => {
      useAuthStore.setState({ user: null })
      expect(useAuthStore.getState().isInTrial()).toBe(false)
    })

    it('returns false when trial_expires_at is missing or non-numeric', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'free' },
      })
      expect(useAuthStore.getState().isInTrial()).toBe(false)

      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'free', trial_expires_at: 'abc' },
      })
      expect(useAuthStore.getState().isInTrial()).toBe(false)
    })
  })

  describe('hasProfessionalAccess()', () => {
    it('returns true for admin regardless of subscription/trial', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'admin', subscription_type: 'free', trial_expires_at: 0 },
      })
      expect(useAuthStore.getState().hasProfessionalAccess()).toBe(true)
    })

    it('returns true for professional/enterprise/gratitude/test tiers', () => {
      for (const tier of ['professional', 'enterprise', 'gratitude', 'test']) {
        useAuthStore.setState({
          user: { id: 1, role: 'user', subscription_type: tier, trial_expires_at: 0 },
        })
        expect(useAuthStore.getState().hasProfessionalAccess()).toBe(true)
      }
    })

    it('returns true for free tier when trial is active', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'free', trial_expires_at: nowSec() + 3600 },
      })
      expect(useAuthStore.getState().hasProfessionalAccess()).toBe(true)
    })

    it('returns true for efficiency tier when trial is active', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'efficiency', trial_expires_at: nowSec() + 3600 },
      })
      expect(useAuthStore.getState().hasProfessionalAccess()).toBe(true)
    })

    it('returns false for free tier with expired trial and non-admin', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'free', trial_expires_at: nowSec() - 60 },
      })
      expect(useAuthStore.getState().hasProfessionalAccess()).toBe(false)
    })

    it('returns false for free tier with no trial fields', () => {
      useAuthStore.setState({
        user: { id: 1, role: 'user', subscription_type: 'free' },
      })
      expect(useAuthStore.getState().hasProfessionalAccess()).toBe(false)
    })
  })

  describe('persistence of trial_* fields', () => {
    it('persists all 4 trial_* fields and reload via initAuth restores them', () => {
      const trialExpires = nowSec() + 86400
      useAuthStore.getState().setUser({
        id: 7,
        username: 'trial-user',
        role: 'user',
        subscription_type: 'free',
        trial_used: 1,
        trial_started_at: trialExpires - 86400,
        trial_expires_at: trialExpires,
        trial_plan_at_start: 'free',
      })

      const stored = JSON.parse(localStorage.getItem('api_user'))
      expect(stored.trial_used).toBe(1)
      expect(stored.trial_started_at).toBe(trialExpires - 86400)
      expect(stored.trial_expires_at).toBe(trialExpires)
      expect(stored.trial_plan_at_start).toBe('free')

      useAuthStore.setState(initialState, true)
      useAuthStore.getState().initAuth()
      const restored = useAuthStore.getState().user
      expect(restored.trial_used).toBe(1)
      expect(restored.trial_expires_at).toBe(trialExpires)
      expect(restored.trial_plan_at_start).toBe('free')
      expect(useAuthStore.getState().isInTrial()).toBe(true)
      expect(useAuthStore.getState().hasProfessionalAccess()).toBe(true)
    })

    it('defaults trial_* fields to safe zeros when missing from input', () => {
      useAuthStore.getState().setUser({
        id: 8,
        username: 'no-trial-user',
        role: 'user',
        subscription_type: 'free',
      })
      const stored = JSON.parse(localStorage.getItem('api_user'))
      expect(stored.trial_used).toBe(0)
      expect(stored.trial_started_at).toBe(0)
      expect(stored.trial_expires_at).toBe(0)
      expect(stored.trial_plan_at_start).toBe('')
    })
  })
})
