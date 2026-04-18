import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import PaymentPage from '../pages/PaymentPage'
import { toast } from 'sonner'
import { ordersAPI } from '../services/api'

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}))

vi.mock('../services/api', () => ({
  ordersAPI: {
    getAll: vi.fn(),
  },
}))

vi.mock('lucide-react', () => ({
  Download: () => null,
  Search: () => null,
  Maximize2: () => null,
  Minimize2: () => null,
  RefreshCw: () => null,
  Info: () => null,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
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

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}))

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className, _variant }) => <span className={className}>{children}</span>,
}))

vi.mock('../components/ui/select', () => ({
  Select: ({ children, _value, _onValueChange }) => <div>{children}</div>,
  SelectTrigger: ({ children, className }) => <div className={className}>{children}</div>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <div data-value={value}>{children}</div>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
}))

vi.mock('../components/ui/skeleton', () => ({
  Skeleton: ({ className }) => <div className={className} data-testid="skeleton" />,
}))

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableCell: ({ children, className }) => <td className={className}>{children}</td>,
  TableHead: ({ children, className }) => <th className={className}>{children}</th>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableRow: ({ children }) => <tr>{children}</tr>,
}))

const mockOrders = {
  orders: [
    { order_id: 'TEST001', order_type: 'professional', amount: 9900, status: 'SUCCESS', created_at: '1710000000' },
    { order_id: 'TEST002', order_type: 'efficiency', amount: 4900, status: 'PENDING', created_at: '1710100000' },
  ],
  total: 2,
}

describe('PaymentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    global.URL.createObjectURL = vi.fn(() => 'blob:mock')
    global.URL.revokeObjectURL = vi.fn()
    ordersAPI.getAll.mockResolvedValue(mockOrders)
  })

  it('renders "支付与订单管理" heading', async () => {
    render(<PaymentPage />)
    expect(screen.getByText(/支付与订单管理/)).toBeInTheDocument()
    await waitFor(() => expect(ordersAPI.getAll).toHaveBeenCalled())
  })

  it('shows loading skeletons while fetching', () => {
    ordersAPI.getAll.mockReturnValue(new Promise(() => {}))
    render(<PaymentPage />)
    expect(screen.getAllByTestId('skeleton').length).toBeGreaterThan(0)
  })

  it('shows orders after API response resolves', async () => {
    render(<PaymentPage />)
    await waitFor(() => {
      expect(screen.getByText('TEST001')).toBeInTheDocument()
      expect(screen.getByText('TEST002')).toBeInTheDocument()
    })
  })

  it('shows empty state with "暂无订单记录" when API returns empty', async () => {
    ordersAPI.getAll.mockResolvedValue({ orders: [], total: 0 })
    render(<PaymentPage />)
    await waitFor(() => {
      expect(screen.getByText('暂无订单记录')).toBeInTheDocument()
      expect(screen.getByText('前往订阅管理')).toBeInTheDocument()
    })
  })

  it('CSV export with real data triggers download and toast', async () => {
    render(<PaymentPage />)
    await waitFor(() => {
      expect(screen.getByText('TEST001')).toBeInTheDocument()
    })
    const mockAnchor = { href: '', download: '', click: vi.fn() }
    vi.spyOn(document, 'createElement').mockReturnValueOnce(mockAnchor)
    fireEvent.click(screen.getByText('导出CSV'))
    expect(toast.success).toHaveBeenCalledWith('导出成功')
  })

  it('info notice renders navigation hint text', async () => {
    render(<PaymentPage />)
    expect(screen.getByText(/如需订阅或升级套餐/)).toBeInTheDocument()
    await waitFor(() => expect(ordersAPI.getAll).toHaveBeenCalled())
  })

  it('refresh button calls fetchOrders again', async () => {
    render(<PaymentPage />)
    await waitFor(() => {
      expect(screen.getByText('TEST001')).toBeInTheDocument()
    })
    expect(ordersAPI.getAll).toHaveBeenCalledTimes(1)
    fireEvent.click(screen.getByLabelText('刷新'))
    await waitFor(() => {
      expect(ordersAPI.getAll).toHaveBeenCalledTimes(2)
    })
  })
})
