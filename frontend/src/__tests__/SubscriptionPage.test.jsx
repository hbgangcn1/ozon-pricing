import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import SubscriptionPage from '../pages/SubscriptionPage'
import { subscriptionsAPI } from '../services/api'
import { useAuthStore } from '../stores/authStore'

vi.mock('lucide-react', () => ({
  Crown: () => null,
  CheckCircle: () => null,
  ArrowUp: () => null,
  Info: () => null,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}))

vi.mock('../services/api', () => ({
  subscriptionsAPI: {
    getCurrent: vi.fn(),
    getPlans: vi.fn(),
  },
}))

vi.mock('../components/PaymentQRDialog', () => ({
  default: () => null,
}))

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}))

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, _variant, _size, ...rest }) => (
    <button onClick={onClick} disabled={disabled} className={className} {...rest}>{children}</button>
  ),
}))

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className, _variant }) => <span className={className}>{children}</span>,
}))

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ children, open }) => open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children, className }) => <div className={className}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children, className }) => <h3 className={className}>{children}</h3>,
  DialogDescription: ({ children }) => <p>{children}</p>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}))

const mockPlans = [
  { code: 'free', name: '免费版', display_price_month: 0, display_price_year: 0, calc_limit: 5, logistics_limit: 1, features: ['基础功能'] },
  { code: 'efficiency', name: '效率版', display_price_month: 49, display_price_year: 490, actual_price_month: 49, actual_price_year: 490, calc_limit: 50, logistics_limit: 3, features: ['更多计算'] },
  { code: 'professional', name: '专业版', display_price_month: 99, display_price_year: 990, actual_price_month: 99, actual_price_year: 990, calc_limit: -1, logistics_limit: -1, features: ['无限制'] },
  { code: 'enterprise', name: '企业版', display_price_month: 0, display_price_year: 0, calc_limit: -1, logistics_limit: -1, features: ['定制化'], developing: true },
]

describe('SubscriptionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user', user_type: 'free' } })
    subscriptionsAPI.getCurrent.mockResolvedValue({ plan_code: 'free', calc_limit: -1, logistics_limit: 1 })
    subscriptionsAPI.getPlans.mockResolvedValue(mockPlans)
  })

  it('renders "订阅管理" heading', async () => {
    render(<SubscriptionPage />)
    expect(screen.getByText(/订阅管理/)).toBeInTheDocument()
    await waitFor(() => expect(subscriptionsAPI.getPlans).toHaveBeenCalled())
  })

  it('renders current plan section', async () => {
    render(<SubscriptionPage />)
    expect(screen.getAllByText(/当前套餐/).length).toBeGreaterThan(0)
    await waitFor(() => expect(subscriptionsAPI.getPlans).toHaveBeenCalled())
  })

  it('shows plan cards after API response', async () => {
    render(<SubscriptionPage />)
    await waitFor(() => {
      expect(screen.getAllByText('免费版').length).toBeGreaterThan(0)
      expect(screen.getAllByText('效率版').length).toBeGreaterThan(0)
      expect(screen.getAllByText('专业版').length).toBeGreaterThan(0)
      expect(screen.getAllByText('企业版').length).toBeGreaterThan(0)
    })
  })

  it('shows admin label for admin users', async () => {
    useAuthStore.mockReturnValue({ user: { username: 'admin', role: 'admin', user_type: 'free' } })
    render(<SubscriptionPage />)
    await waitFor(() => {
      expect(screen.getByText('管理员')).toBeInTheDocument()
    })
  })

  it('shows free plan name for free user', async () => {
    render(<SubscriptionPage />)
    await waitFor(() => {
      expect(screen.getAllByText('免费版').length).toBeGreaterThan(0)
    })
  })

  it('upgrade button exists for paid plans', async () => {
    render(<SubscriptionPage />)
    await waitFor(() => {
      expect(screen.getByText('升级到效率版')).toBeInTheDocument()
      expect(screen.getByText('升级到专业版')).toBeInTheDocument()
    })
  })

  it('enterprise shows "联系客服升级"', async () => {
    render(<SubscriptionPage />)
    await waitFor(() => {
      expect(screen.getByText('联系客服升级')).toBeInTheDocument()
    })
  })
})
