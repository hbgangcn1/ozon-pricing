import { describe, it, expect, beforeEach, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { usePricingCalculation } from '../pages/pricing/usePricingCalculation'
import { commissionCategoriesAPI, productsAPI, logisticsAPI } from '../services/api'
import { useAuthStore } from '../stores/authStore'

vi.mock('../services/api', () => ({
  pricingAPI: { calculate: vi.fn(), calculateGrouped: vi.fn() },
  productsAPI: { getAll: vi.fn(), create: vi.fn(), update: vi.fn(), delete: vi.fn() },
  commissionCategoriesAPI: { getAll: vi.fn() },
  logisticsAPI: { getAll: vi.fn() },
  authAPI: { getMe: vi.fn(), refreshAccess: vi.fn() },
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), warning: vi.fn(), dismiss: vi.fn() },
}))

describe('usePricingCalculation commission gating', () => {
  const initialAuthState = useAuthStore.getState()

  beforeEach(() => {
    useAuthStore.setState(initialAuthState, true)
    vi.clearAllMocks()
    productsAPI.getAll.mockResolvedValue([])
    logisticsAPI.getAll.mockResolvedValue([])
    commissionCategoriesAPI.getAll.mockResolvedValue([
      { id: 1, name: '服装', rfbs_tier1_rate: 0.08, rfbs_tier2_rate: 0.07, rfbs_tier3_rate: 0.06 },
    ])
  })

  it('skips commission fetch on mount when hasProfessionalAccess is false', async () => {
    useAuthStore.setState({
      user: { id: 1, role: 'user', subscription_type: 'free' },
    })

    const { result } = renderHook(() => usePricingCalculation({ user_type: 'free' }))

    await waitFor(() => {
      expect(productsAPI.getAll).toHaveBeenCalled()
    })

    expect(commissionCategoriesAPI.getAll).not.toHaveBeenCalled()
    expect(result.current.commissionCategories).toEqual([])
  })

  it('fetches commission categories on mount when hasProfessionalAccess is true (paid tier)', async () => {
    useAuthStore.setState({
      user: { id: 2, role: 'user', subscription_type: 'professional' },
    })

    const { result } = renderHook(() => usePricingCalculation({ user_type: 'professional' }))

    await waitFor(() => {
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(1)
      expect(result.current.commissionCategories.length).toBe(1)
    })
    expect(result.current.commissionCategories[0].name).toBe('服装')
  })

  it('fetches commission categories on mount when free tier user is in active trial', async () => {
    const future = Math.floor(Date.now() / 1000) + 3600
    useAuthStore.setState({
      user: { id: 3, role: 'user', subscription_type: 'free', trial_expires_at: future },
    })

    renderHook(() => usePricingCalculation({ user_type: 'free' }))

    await waitFor(() => {
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(1)
    })
  })

  it('skips all data fetches when no user is committed yet (auth gate)', async () => {
    useAuthStore.setState({ user: null })

    const { result } = renderHook(() => usePricingCalculation(null))

    await new Promise((resolve) => setTimeout(resolve, 50))

    expect(productsAPI.getAll).not.toHaveBeenCalled()
    expect(commissionCategoriesAPI.getAll).not.toHaveBeenCalled()
    expect(logisticsAPI.getAll).not.toHaveBeenCalled()
    expect(result.current.commissionCategories).toEqual([])
  })

  it('refetches commission categories when user transitions from null to professional (post-login race fix)', async () => {
    useAuthStore.setState({ user: null })

    const { result, rerender } = renderHook(
      ({ user }) => usePricingCalculation(user),
      { initialProps: { user: null } },
    )

    await new Promise((resolve) => setTimeout(resolve, 30))
    expect(commissionCategoriesAPI.getAll).not.toHaveBeenCalled()

    const adminUser = { id: 159043, role: 'admin', subscription_type: 'enterprise' }
    useAuthStore.setState({ user: adminUser })
    rerender({ user: adminUser })

    await waitFor(() => {
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(1)
      expect(result.current.commissionCategories.length).toBe(1)
    })
  })

  it('admin user with enterprise subscription receives commission categories on mount (original bug repro)', async () => {
    useAuthStore.setState({
      user: { id: 159043, role: 'admin', subscription_type: 'enterprise' },
    })
    commissionCategoriesAPI.getAll.mockResolvedValue([
      { id: 3562, name: '日化用品', rfbs_tier1_rate: 0.05, rfbs_tier2_rate: 0.04, rfbs_tier3_rate: 0.03 },
    ])

    const adminUser = { id: 159043, role: 'admin', subscription_type: 'enterprise', user_type: 'enterprise' }
    const { result } = renderHook(() => usePricingCalculation(adminUser))

    await waitFor(() => {
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(1)
      expect(result.current.commissionCategories.length).toBe(1)
    })
    expect(result.current.commissionCategories[0].name).toBe('日化用品')
  })
})
