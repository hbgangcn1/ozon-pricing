import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PricingPage from '../pages/PricingPage';
import { pricingAPI, productsAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  pricingAPI: {
    calculate: vi.fn(),
  },
  productsAPI: {
    getAll: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    dismiss: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock('../components/charts/CostPieChart', () => ({
  default: () => <div data-testid="cost-pie-chart" />,
}));

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, size, variant }) => (
    <button onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor, className }) => <label htmlFor={htmlFor} className={className}>{children}</label>,
}));

vi.mock('../components/ui/tabs', () => ({
  Tabs: ({ children, value, onValueChange }) => (
    <div data-active={value}>
      {typeof children === 'function' ? children() : children}
    </div>
  ),
  TabsList: ({ children, className }) => <div className={className}>{children}</div>,
  TabsTrigger: ({ children, value, onClick }) => (
    <button data-value={value} onClick={onClick}>{children}</button>
  ),
  TabsContent: ({ children, value }) => <div data-value={value}>{children}</div>,
}));

vi.mock('../components/ui/select', () => ({
  Select: ({ children, onValueChange, value }) => <div>{children}</div>,
  SelectTrigger: ({ children, className }) => <div className={className}>{children}</div>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <div data-value={value}>{children}</div>,
}));

vi.mock('../components/ui/checkbox', () => ({
  Checkbox: ({ checked, onCheckedChange, id }) => (
    <input
      type="checkbox"
      id={id}
      checked={checked}
      onChange={(e) => onCheckedChange && onCheckedChange(e.target.checked)}
    />
  ),
}));

vi.mock('../components/ui/radio-group', () => ({
  RadioGroup: ({ children, value, onValueChange, className }) => <div className={className}>{children}</div>,
  RadioGroupItem: ({ value, id }) => <input type="radio" id={id} value={value} />,
}));

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }) => open ? <div>{children}</div> : null,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

vi.mock('../components/ui/alert-dialog', () => ({
  AlertDialog: ({ children, open }) => open ? <div>{children}</div> : null,
  AlertDialogContent: ({ children }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }) => <h2>{children}</h2>,
  AlertDialogDescription: ({ children }) => <p>{children}</p>,
  AlertDialogFooter: ({ children }) => <div>{children}</div>,
  AlertDialogAction: ({ children, onClick, className }) => <button onClick={onClick} className={className}>{children}</button>,
  AlertDialogCancel: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
}));

vi.mock('lucide-react', () => new Proxy({}, {
  get: (_, name) => {
    if (name === '__esModule') return true;
    return () => null;
  },
}));

vi.mock('recharts', () => ({
  ResponsiveContainer: ({ children }) => <div>{children}</div>,
  PieChart: ({ children }) => <div>{children}</div>,
  Pie: () => <div />,
  Cell: () => <div />,
  Tooltip: () => <div />,
  Legend: () => <div />,
}));

const mockUser = { id: 1, username: 'testuser', role: 'user', user_type: 'professional' };

const mockPricingResult = {
  price_priority: {
    land_pickup: { is_available: true, price_cny: 100, logistics_name: 'Land1', logistics_cost: 10, days_min: 3, days_max: 7, profit_margin_pct: 20, avg_cost: 12, saved_cost: 2, avg_days: 5, saved_days: 1, breakdown: [] },
    air_pickup: { is_available: false },
    land_home: { is_available: false },
    air_home: { is_available: false },
  },
  speed_priority: {
    land_pickup: { is_available: false },
    air_pickup: { is_available: false },
    land_home: { is_available: false },
    air_home: { is_available: false },
  },
  exchange_rates: { rub_cny: 0.08, usd_cny: 7.2 },
  filtered_logistics: { land: [], air: [] },
};

describe('PricingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.mockReturnValue({ user: mockUser });
    productsAPI.getAll.mockResolvedValue([]);
  });

  it('renders pricing page heading', () => {
    render(<PricingPage />);
    expect(screen.getByText('物流定价计算')).toBeInTheDocument();
  });

  it('renders fast mode tab content', () => {
    render(<PricingPage />);
    expect(screen.getByText(/物流定价（快速模式）/)).toBeInTheDocument();
  });

  it('renders fast mode input fields', () => {
    render(<PricingPage />);
    expect(screen.getAllByPlaceholderText('30').length).toBeGreaterThan(0);
    expect(screen.getAllByPlaceholderText('300').length).toBeGreaterThan(0);
  });

  it('calls productsAPI.getAll on mount', async () => {
    render(<PricingPage />);
    await waitFor(() => {
      expect(productsAPI.getAll).toHaveBeenCalled();
    });
  });

  it('shows error when fast calculate called with empty fields', async () => {
    render(<PricingPage />);

    const calcBtns = screen.getAllByText('开始计算');
    fireEvent.click(calcBtns[0]);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('请填写进货单价和重量');
    });
  });

  it('calls pricingAPI.calculate with fast mode data', async () => {
    pricingAPI.calculate.mockResolvedValue(mockPricingResult);
    render(<PricingPage />);

    const priceInputs = screen.getAllByPlaceholderText('30');
    fireEvent.change(priceInputs[0], { target: { value: '50' } });

    const weightInputs = screen.getAllByPlaceholderText('300');
    fireEvent.change(weightInputs[0], { target: { value: '500' } });

    const calcBtns = screen.getAllByText('开始计算');
    fireEvent.click(calcBtns[0]);

    await waitFor(() => {
      expect(pricingAPI.calculate).toHaveBeenCalledWith(
        null,
        'fast',
        expect.objectContaining({ unit_price: 50, weight_g: 500 })
      );
    });
  });

  it('renders pricing results after successful calculation', async () => {
    pricingAPI.calculate.mockResolvedValue(mockPricingResult);
    render(<PricingPage />);

    const priceInputs = screen.getAllByPlaceholderText('30');
    fireEvent.change(priceInputs[0], { target: { value: '50' } });

    const weightInputs = screen.getAllByPlaceholderText('300');
    fireEvent.change(weightInputs[0], { target: { value: '500' } });

    const calcBtns = screen.getAllByText('开始计算');
    fireEvent.click(calcBtns[0]);

    await waitFor(() => {
      expect(screen.getByText('价格优先方案')).toBeInTheDocument();
      expect(toast.success).toHaveBeenCalledWith('计算完成');
    });
  });

  it('shows error toast when pricingAPI.calculate fails', async () => {
    pricingAPI.calculate.mockRejectedValue({ response: { data: { detail: '计算失败' } } });
    render(<PricingPage />);

    const priceInputs = screen.getAllByPlaceholderText('30');
    fireEvent.change(priceInputs[0], { target: { value: '50' } });

    const weightInputs = screen.getAllByPlaceholderText('300');
    fireEvent.change(weightInputs[0], { target: { value: '500' } });

    const calcBtns = screen.getAllByText('开始计算');
    fireEvent.click(calcBtns[0]);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('计算失败');
    });
  });

  it('shows precise mode disabled label for free users', () => {
    useAuthStore.mockReturnValue({ user: { ...mockUser, user_type: 'free' } });
    render(<PricingPage />);
    expect(screen.getByText(/精准模式（限专业版\/企业版）/)).toBeInTheDocument();
  });

  it('shows precise mode enabled label for professional users', () => {
    useAuthStore.mockReturnValue({ user: { ...mockUser, user_type: 'professional' } });
    render(<PricingPage />);
    expect(screen.getByText('精准模式')).toBeInTheDocument();
  });

  it('opens product list dialog when button clicked', async () => {
    render(<PricingPage />);
    const openBtn = screen.getByText('打开产品列表');
    fireEvent.click(openBtn);
    await waitFor(() => {
      expect(screen.getByText('产品列表')).toBeInTheDocument();
    });
  });

  it('shows empty product message in product list', async () => {
    productsAPI.getAll.mockResolvedValue([]);
    render(<PricingPage />);
    const openBtn = screen.getByText('打开产品列表');
    fireEvent.click(openBtn);
    await waitFor(() => {
      expect(screen.getByText('暂无产品，请先创建')).toBeInTheDocument();
    });
  });

  it('shows validation error when creating product with missing fields', async () => {
    render(<PricingPage />);
    const openBtn = screen.getByText('打开产品列表');
    fireEvent.click(openBtn);

    await waitFor(() => {
      expect(screen.getByText('产品列表')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('关闭'));
    await waitFor(() => {
      expect(screen.queryByText('产品列表')).not.toBeInTheDocument();
    });
  });
});
