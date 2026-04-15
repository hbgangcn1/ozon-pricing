import { describe, it, expect, beforeEach, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import PaymentQRDialog from '../components/PaymentQRDialog'
import { paymentAPI } from '../services/api'

vi.mock('react-router-dom', () => ({
  useNavigate: vi.fn(() => vi.fn()),
}))

vi.mock('../services/api', () => ({
  paymentAPI: {
    createOrder: vi.fn(),
    getStatus: vi.fn(),
  },
}))

vi.mock('qrcode.react', () => ({
  QRCodeSVG: ({ value, size }) => <div data-testid="qrcode" data-value={value}>{value}</div>,
}))

vi.mock('lucide-react', () => ({
  Loader2: () => null,
  CheckCircle2: () => null,
  XCircle: () => null,
}))

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}))

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }) => open ? (
    <div data-testid="qr-dialog">
      <button type="button" data-testid="close-dialog" onClick={() => onOpenChange(false)}>Close</button>
      {children}
    </div>
  ) : null,
  DialogContent: ({ children, className }) => <div className={className}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children, className }) => <h3 className={className}>{children}</h3>,
  DialogDescription: ({ children }) => <p>{children}</p>,
}))

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, ...rest }) => (
    <button onClick={onClick} disabled={disabled} className={className} {...rest}>{children}</button>
  ),
}))

const defaultProps = {
  open: true,
  onOpenChange: vi.fn(),
  planCode: 'efficiency',
  planName: '效率版',
  billingCycle: 'month',
  amount: 49,
  onSuccess: vi.fn(),
}

describe('PaymentQRDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    paymentAPI.createOrder.mockResolvedValue({
      order_id: 'ORDER123',
      code_url: 'weixin://wxpay/bizpayurl?pr=abc123',
    })
  })

  it('does not render when open=false', () => {
    render(<PaymentQRDialog {...defaultProps} open={false} />)
    expect(screen.queryByTestId('qr-dialog')).not.toBeInTheDocument()
  })

  it('renders loading state initially when open=true', () => {
    paymentAPI.createOrder.mockReturnValue(new Promise(() => {}))
    render(<PaymentQRDialog {...defaultProps} />)
    expect(screen.getByText('正在创建订单...')).toBeInTheDocument()
  })

  it('shows QR code after createOrder resolves with code_url', async () => {
    render(<PaymentQRDialog {...defaultProps} />)
    await waitFor(() => {
      expect(screen.getByTestId('qrcode')).toBeInTheDocument()
    })
  })

  it('shows error message when createOrder fails', async () => {
    paymentAPI.createOrder.mockRejectedValue(new Error('创建订单失败'))
    render(<PaymentQRDialog {...defaultProps} />)
    await waitFor(() => {
      expect(screen.getByText('二维码已过期')).toBeInTheDocument()
    })
  })

  it('calls onOpenChange when dialog is closed', () => {
    paymentAPI.createOrder.mockReturnValue(new Promise(() => {}))
    const onOpenChange = vi.fn()
    render(<PaymentQRDialog {...defaultProps} onOpenChange={onOpenChange} />)
    fireEvent.click(screen.getByTestId('close-dialog'))
    expect(onOpenChange).toHaveBeenCalledWith(false)
  })
})
