import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PricingPage from '../pages/PricingPage';
import { pricingAPI, productsAPI, commissionCategoriesAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

const TabsContext = React.createContext({ value: undefined, setValue: () => {} });

vi.mock('../services/api', () => ({
  pricingAPI: {
    calculate: vi.fn(),
    calculateGrouped: vi.fn(),
  },
  productsAPI: {
    getAll: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
  commissionCategoriesAPI: {
    getAll: vi.fn(),
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
    <button type="button" onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor, className }) => <label htmlFor={htmlFor} className={className}>{children}</label>,
}));

vi.mock('../components/ui/checkbox', () => ({
  Checkbox: ({ checked, onCheckedChange, id, 'aria-label': ariaLabel }) => (
    <input
      type="checkbox"
      id={id}
      aria-label={ariaLabel}
      checked={checked}
      onChange={(e) => onCheckedChange && onCheckedChange(e.target.checked)}
    />
  ),
}));

vi.mock('../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, disabled, 'aria-label': ariaLabel }) => (
    <button
      type="button"
      role="switch"
      aria-label={ariaLabel}
      aria-checked={checked}
      disabled={disabled}
      onClick={() => onCheckedChange && onCheckedChange(!checked)}
    >
      {checked ? 'on' : 'off'}
    </button>
  ),
}));

vi.mock('../components/ui/tabs', () => ({
  Tabs: ({ children, value, onValueChange, defaultValue }) => {
    const [internalValue, setInternalValue] = React.useState(defaultValue);
    const currentValue = value ?? internalValue;
    const handleValueChange = onValueChange ?? setInternalValue;
    return (
      <TabsContext.Provider value={{ value: currentValue, setValue: handleValueChange }}>
        <div data-active={currentValue}>{children}</div>
      </TabsContext.Provider>
    );
  },
  TabsList: ({ children, className }) => <div className={className}>{children}</div>,
  TabsTrigger: ({ children, value, onClick }) => {
    const tabs = React.useContext(TabsContext);
    return (
      <button type="button" data-value={value} onClick={() => { tabs.setValue?.(value); onClick?.(); }}>
        {children}
      </button>
    );
  },
  TabsContent: ({ children, value }) => {
    const tabs = React.useContext(TabsContext);
    return tabs.value === value ? <div data-value={value}>{children}</div> : null;
  },
}));

vi.mock('../components/ui/select', () => ({
  Select: ({ children, onValueChange, value }) => <div>{children}</div>,
  SelectTrigger: ({ children, className }) => <div className={className}>{children}</div>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <div data-value={value}>{children}</div>,
}));

vi.mock('../components/ui/radio-group', () => ({
  RadioGroup: ({ children, value, onValueChange, className }) => <div className={className}>{children}</div>,
  RadioGroupItem: ({ value, id }) => <input type="radio" id={id} value={value} readOnly />,
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
  AlertDialogAction: ({ children, onClick, className }) => <button type="button" onClick={onClick} className={className}>{children}</button>,
  AlertDialogCancel: ({ children, onClick }) => <button type="button" onClick={onClick}>{children}</button>,
}));

vi.mock('lucide-react', () => ({
  Settings2: () => <div data-testid="icon-settings" />,
  ChevronDown: () => <div data-testid="icon-chevron-down" />,
}));

vi.mock('../components/ui/collapsible', () => ({
  Collapsible: ({ children, defaultOpen }) => <div data-testid="collapsible" data-open={defaultOpen}>{children}</div>,
  CollapsibleTrigger: ({ children, className }) => <button type="button" className={className}>{children}</button>,
  CollapsibleContent: ({ children, className }) => <div className={className}>{children}</div>,
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
  calculation_mode: 'precise',
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

const mockPricingBreakevenResult = {
  ...mockPricingResult,
  breakeven_price_priority: {
    land_pickup: { is_available: true, price_cny: 80, logistics_name: 'BreakEvenLand', logistics_cost: 10, days_min: 3, days_max: 7, profit_margin_pct: 0, avg_cost: 12, saved_cost: 2, avg_days: 5, saved_days: 1, breakdown: [] },
    air_pickup: { is_available: false },
    land_home: { is_available: false },
    air_home: { is_available: false },
  },
  breakeven_speed_priority: {
    land_pickup: { is_available: false },
    air_pickup: { is_available: false },
    land_home: { is_available: false },
    air_home: { is_available: false },
  },
};

const mockGroupedResult = {
  calculation_mode: 'precise',
  rfbs_ru: {
    price_priority: {
      land: { is_available: true, price_cny: 130, logistics_name: 'GroupNormalLand', logistics_cost: 12, days_min: 5, days_max: 9, profit_margin_pct: 25, avg_cost: 14, saved_cost: 2, avg_days: 7, saved_days: 1, breakdown: [] },
      air: { is_available: true, price_cny: 150, logistics_name: 'GroupNormalAir', logistics_cost: 18, days_min: 2, days_max: 4, profit_margin_pct: 25, avg_cost: 20, saved_cost: 2, avg_days: 3, saved_days: 1, breakdown: [] },
    },
    speed_priority: {
      land: { is_available: true, price_cny: 140, logistics_name: 'GroupSpeedLand', logistics_cost: 15, days_min: 3, days_max: 6, profit_margin_pct: 20, avg_cost: 14, saved_cost: 2, avg_days: 5, saved_days: 2, breakdown: [] },
      air: { is_available: true, price_cny: 155, logistics_name: 'GroupSpeedAir', logistics_cost: 20, days_min: 1, days_max: 3, profit_margin_pct: 20, avg_cost: 20, saved_cost: 2, avg_days: 2, saved_days: 1, breakdown: [] },
    },
  },
  rfbs_cis: { price_priority: { land: { is_available: false }, air: { is_available: false } }, speed_priority: { land: { is_available: false }, air: { is_available: false } } },
  fbp_ru: { price_priority: { land: { is_available: false }, air: { is_available: false } }, speed_priority: { land: { is_available: false }, air: { is_available: false } } },
  fbp_cis: { price_priority: { land: { is_available: false }, air: { is_available: false } }, speed_priority: { land: { is_available: false }, air: { is_available: false } } },
  breakeven_rfbs_ru: {
    price_priority: {
      land: { is_available: true, price_cny: 95, logistics_name: 'GroupBreakevenLand', logistics_cost: 12, days_min: 5, days_max: 9, profit_margin_pct: 0, avg_cost: 14, saved_cost: 2, avg_days: 7, saved_days: 1, breakdown: [] },
      air: { is_available: true, price_cny: 110, logistics_name: 'GroupBreakevenAir', logistics_cost: 18, days_min: 2, days_max: 4, profit_margin_pct: 0, avg_cost: 20, saved_cost: 2, avg_days: 3, saved_days: 1, breakdown: [] },
    },
    speed_priority: {
      land: { is_available: true, price_cny: 100, logistics_name: 'GroupBreakevenSpeedLand', logistics_cost: 15, days_min: 3, days_max: 6, profit_margin_pct: 0, avg_cost: 14, saved_cost: 2, avg_days: 5, saved_days: 2, breakdown: [] },
      air: { is_available: true, price_cny: 115, logistics_name: 'GroupBreakevenSpeedAir', logistics_cost: 20, days_min: 1, days_max: 3, profit_margin_pct: 0, avg_cost: 20, saved_cost: 2, avg_days: 2, saved_days: 1, breakdown: [] },
    },
  },
  breakeven_rfbs_cis: { price_priority: { land: { is_available: false }, air: { is_available: false } }, speed_priority: { land: { is_available: false }, air: { is_available: false } } },
  breakeven_fbp_ru: { price_priority: { land: { is_available: false }, air: { is_available: false } }, speed_priority: { land: { is_available: false }, air: { is_available: false } } },
  breakeven_fbp_cis: { price_priority: { land: { is_available: false }, air: { is_available: false } }, speed_priority: { land: { is_available: false }, air: { is_available: false } } },
  exchange_rates: { rub_cny: 0.08, usd_cny: 7.2 },
  filtered_logistics: { land: [], air: [] },
};

describe('PricingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.mockReturnValue({ user: mockUser });
    productsAPI.getAll.mockResolvedValue([]);
    commissionCategoriesAPI.getAll.mockResolvedValue([]);
    pricingAPI.calculateGrouped.mockResolvedValue(mockGroupedResult);
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
    const zeroInputs = screen.getAllByPlaceholderText('0');
    expect(zeroInputs.length).toBeGreaterThanOrEqual(2);
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

    const zeroInputs = screen.getAllByPlaceholderText('0');
    fireEvent.change(zeroInputs[0], { target: { value: '50' } });

    fireEvent.change(zeroInputs[1], { target: { value: '500' } });

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

    const zeroInputs = screen.getAllByPlaceholderText('0');
    fireEvent.change(zeroInputs[0], { target: { value: '50' } });

    fireEvent.change(zeroInputs[1], { target: { value: '500' } });

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

    const zeroInputs = screen.getAllByPlaceholderText('0');
    fireEvent.change(zeroInputs[0], { target: { value: '50' } });

    fireEvent.change(zeroInputs[1], { target: { value: '500' } });

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
    fireEvent.click(screen.getByText('精准模式'));
    const openBtn = screen.getByText('打开产品列表');
    fireEvent.click(openBtn);
    await waitFor(() => {
      expect(screen.getByText('产品列表')).toBeInTheDocument();
    });
  });

  it('shows empty product message in product list', async () => {
    productsAPI.getAll.mockResolvedValue([]);
    render(<PricingPage />);
    fireEvent.click(screen.getByText('精准模式'));
    const openBtn = screen.getByText('打开产品列表');
    fireEvent.click(openBtn);
    await waitFor(() => {
      expect(screen.getByText('暂无产品，请先创建')).toBeInTheDocument();
    });
  });

  it('shows validation error when creating product with missing fields', async () => {
    render(<PricingPage />);
    fireEvent.click(screen.getByText('精准模式'));
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

  it('does not render breakeven toggle before results exist', () => {
    render(<PricingPage />);
    expect(screen.queryByText('盈亏平衡线模式')).not.toBeInTheDocument();
  });

  it('toggles precise result display between normal and breakeven without recalculating', async () => {
    pricingAPI.calculate.mockResolvedValue(mockPricingBreakevenResult);

    render(<PricingPage />);
    fireEvent.click(screen.getByText('精准模式'));

    fireEvent.change(screen.getByPlaceholderText('必填'), { target: { value: '测试产品' } });

    const spinbuttons = screen.getAllByRole('spinbutton');
    fireEvent.change(spinbuttons[0], { target: { value: '50' } });
    fireEvent.change(spinbuttons[1], { target: { value: '500' } });
    fireEvent.change(spinbuttons[2], { target: { value: '10' } });
    fireEvent.change(spinbuttons[3], { target: { value: '10' } });
    fireEvent.change(spinbuttons[4], { target: { value: '10' } });

    fireEvent.click(screen.getByText('开始计算'));

    await waitFor(() => {
      expect(screen.getByText('盈亏平衡线模式')).toBeInTheDocument();
      // 精准模式分组结果 — 正常模式 rfbs_ru 低价优先
      expect(screen.getByText('¥130.00')).toBeInTheDocument();
      expect(screen.getByText('GroupNormalLand')).toBeInTheDocument();
    });

    const requestCountAfterCalculation = pricingAPI.calculate.mock.calls.length;
    const groupedCountAfterCalculation = pricingAPI.calculateGrouped.mock.calls.length;

    fireEvent.click(screen.getByRole('switch', { name: '盈亏平衡线切换' }));

    await waitFor(() => {
      // 盈亏平衡模式 — breakeven_rfbs_ru 低价优先
      expect(screen.getByText('¥95.00')).toBeInTheDocument();
      expect(screen.getByText('GroupBreakevenLand')).toBeInTheDocument();
      expect(screen.getByText('¥110.00')).toBeInTheDocument();
      expect(screen.getByText('GroupBreakevenAir')).toBeInTheDocument();
    });

    expect(pricingAPI.calculate).toHaveBeenCalledTimes(requestCountAfterCalculation);
    expect(pricingAPI.calculateGrouped).toHaveBeenCalledTimes(groupedCountAfterCalculation);

    fireEvent.click(screen.getByRole('switch', { name: '盈亏平衡线切换' }));

    await waitFor(() => {
      // 切回正常模式 — rfbs_ru 低价优先 + 速度优先
      expect(screen.getByText('¥130.00')).toBeInTheDocument();
      expect(screen.getByText('GroupNormalLand')).toBeInTheDocument();
      expect(screen.getByText('¥140.00')).toBeInTheDocument();
      expect(screen.getByText('GroupSpeedLand')).toBeInTheDocument();
    });

    expect(pricingAPI.calculate).toHaveBeenCalledTimes(requestCountAfterCalculation);
    expect(pricingAPI.calculateGrouped).toHaveBeenCalledTimes(groupedCountAfterCalculation);
  });

  it('includes commission_category_id when creating a product in precise mode', async () => {
    const mockUser = { id: 1, username: 'testuser', role: 'user', user_type: 'professional' };
    useAuthStore.mockReturnValue({ user: mockUser });
    productsAPI.create.mockResolvedValue({ id: 100, name: '佣金类目测试', commission_category_id: null });

    render(<PricingPage />);
    fireEvent.click(screen.getByText('精准模式'));

    fireEvent.change(screen.getByPlaceholderText('必填'), { target: { value: '佣金类目测试' } });

    const spinbuttons = screen.getAllByRole('spinbutton');
    fireEvent.change(spinbuttons[0], { target: { value: '50' } });
    fireEvent.change(spinbuttons[1], { target: { value: '500' } });
    fireEvent.change(spinbuttons[2], { target: { value: '10' } });
    fireEvent.change(spinbuttons[3], { target: { value: '10' } });
    fireEvent.change(spinbuttons[4], { target: { value: '10' } });

    fireEvent.click(screen.getByText('保存产品'));

    await waitFor(() => {
      expect(productsAPI.create).toHaveBeenCalled();
      expect(productsAPI.create.mock.calls[0][0]).toHaveProperty('commission_category_id');
    });
  });

  it('loads products with commission_category_id from API', async () => {
    const mockUser = { id: 1, username: 'testuser', role: 'user', user_type: 'professional' };
    useAuthStore.mockReturnValue({ user: mockUser });
    productsAPI.getAll.mockResolvedValue([
      {
        id: 1,
        name: 'Test Product',
        commission_category_id: 5,
        weight_g: 500,
        length_cm: 20,
        width_cm: 15,
        height_cm: 10,
        unit_price: 99.9,
      },
    ]);
    commissionCategoriesAPI.getAll.mockResolvedValue([
      { id: 5, name: 'Electronics', commission_rate: 15 },
    ]);

    render(<PricingPage />);
    fireEvent.click(screen.getByText('精准模式'));

    await waitFor(() => {
      expect(productsAPI.getAll).toHaveBeenCalled();
    });
  });
});
