import React from 'react'
import { beforeEach, describe, expect, test, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Outlet, useLocation } from 'react-router-dom'
import App from '../App'
import { useAuthStore } from '../stores/authStore'

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}))

vi.mock('../hooks/useTokenRefresh', () => ({
  useTokenRefresh: () => {},
}))

vi.mock('../components/AppLayout', () => ({
  default: () => <div data-testid="layout"><Outlet /></div>,
}))

vi.mock('../components/SessionKickedDialog', () => ({
  default: () => null,
}))

vi.mock('../components/ErrorBoundary', () => ({
  default: ({ children }) => children,
}))

vi.mock('../pages/LoginPage', () => ({ default: () => <div data-testid="page-login">login</div> }))
vi.mock('../pages/PricingPage', () => ({ default: () => <div data-testid="page-pricing">pricing</div> }))
vi.mock('../pages/RegisterPage', () => ({ default: () => <div data-testid="page-register">register</div> }))
vi.mock('../pages/ForgotPasswordPage', () => ({ default: () => <div data-testid="page-forgot-password">forgot password</div> }))
vi.mock('../pages/LogisticsPage', () => ({ default: () => <div data-testid="page-logistics">logistics</div> }))
vi.mock('../pages/AccountPage', () => ({ default: () => <div data-testid="page-account">account</div> }))
vi.mock('../pages/SubscriptionPage', () => ({ default: () => <div data-testid="page-subscription">subscription</div> }))
vi.mock('../pages/PaymentPage', () => ({ default: () => <div data-testid="page-payment">payment</div> }))
vi.mock('../pages/SettingsPage', () => ({ default: () => <div data-testid="page-settings">settings</div> }))
vi.mock('../pages/UserManagementPage', () => ({ default: () => <div data-testid="page-users">users</div> }))
vi.mock('../pages/PlanManagementPage', () => ({ default: () => <div data-testid="page-plans">plans</div> }))
vi.mock('../pages/StatisticsPage', () => ({ default: () => <div data-testid="page-statistics">statistics</div> }))
vi.mock('../pages/CommissionCategoriesPage', () => ({ default: () => <div data-testid="page-commission-categories">commission categories</div> }))
vi.mock('../pages/LogisticsPoolPage', () => ({ default: () => <div data-testid="page-logistics-pool">logistics pool</div> }))
vi.mock('../pages/ProductImportPage', () => ({ default: () => <div data-testid="page-product-import">product import</div> }))
vi.mock('../pages/NotFoundPage', () => ({ default: () => <div data-testid="page-not-found">not found</div> }))

const unauthState = () => ({
  user: null,
  token: null,
  isAuthenticated: false,
  isLoading: false,
  initAuth: vi.fn(),
  sessionKicked: { open: false, reason: null },
  clearSessionKicked: vi.fn(),
  isAdmin: () => false,
})

const authNonAdminState = () => ({
  ...unauthState(),
  user: { id: 1, username: 'alice', role: 'user' },
  isAuthenticated: true,
})

function mockAuthState(state) {
  vi.mocked(useAuthStore).mockImplementation((selector) => (
    selector ? selector(state) : state
  ))
}

function LocationProbe({ onLocation }) {
  const loc = useLocation()
  React.useEffect(() => {
    onLocation(loc)
  }, [loc, onLocation])
  return null
}

function renderAt(path, { onLocation } = {}) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <App />
      {onLocation && <LocationProbe onLocation={onLocation} />}
    </MemoryRouter>
  )
}

describe('App routing', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  test('Case A: / renders login page when not authenticated', async () => {
    mockAuthState(unauthState())

    renderAt('/')

    await waitFor(() => {
      expect(screen.getByTestId('page-login')).toBeInTheDocument()
    })
  })

  test('Case B: / renders login page when authenticated', async () => {
    mockAuthState(authNonAdminState())

    renderAt('/')

    await waitFor(() => {
      expect(screen.getByTestId('page-login')).toBeInTheDocument()
    })
  })

  test('Case C: /pricing redirects unauthenticated users to login with returnTo', async () => {
    mockAuthState(unauthState())
    let captured = null

    renderAt('/pricing', { onLocation: (loc) => { captured = loc } })

    await waitFor(() => {
      expect(captured?.pathname).toBe('/login')
      expect(captured?.search).toBe('?returnTo=%2Fpricing')
    })
  })

  test('Case D: /settings redirects unauthenticated users to login with returnTo', async () => {
    mockAuthState(unauthState())
    let captured = null

    renderAt('/settings', { onLocation: (loc) => { captured = loc } })

    await waitFor(() => {
      expect(captured?.pathname).toBe('/login')
      expect(captured?.search).toBe('?returnTo=%2Fsettings')
    })
  })

  test('Case E: /pricing renders pricing page when authenticated as non-admin', async () => {
    mockAuthState(authNonAdminState())

    renderAt('/pricing')

    await waitFor(() => {
      expect(screen.getByTestId('page-pricing')).toBeInTheDocument()
    })
  })

  test('Case F: /settings redirects authenticated non-admin users to pricing page', async () => {
    mockAuthState(authNonAdminState())
    let captured = null

    renderAt('/settings', { onLocation: (loc) => { captured = loc } })

    await waitFor(() => {
      expect(captured?.pathname).toBe('/pricing')
      expect(screen.getByTestId('page-pricing')).toBeInTheDocument()
    })
  })
})
