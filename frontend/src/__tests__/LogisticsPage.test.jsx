import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LogisticsPage from '../pages/LogisticsPage';
import { logisticsAPI } from '../services/api';
import { useLogisticsStore } from '../stores/logisticsStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  logisticsAPI: {
    getAll: vi.fn(),
    getById: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
    batchDelete: vi.fn(),
  },
}));

vi.mock('../stores/logisticsStore', () => ({
  useLogisticsStore: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, type, variant, size, 'aria-label': ariaLabel }) => (
    <button onClick={onClick} disabled={disabled} className={className} type={type} aria-label={ariaLabel}>{children}</button>
  ),
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor, className }) => <label htmlFor={htmlFor} className={className}>{children}</label>,
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className, variant }) => <span className={className}>{children}</span>,
}));

vi.mock('../components/ui/select', () => {
  const SelectContext = React.createContext({ value: '', onValueChange: () => {} });

  return {
    Select: ({ children, onValueChange, value }) => (
      <SelectContext.Provider value={{ value, onValueChange }}>
        <div>{children}</div>
      </SelectContext.Provider>
    ),
    SelectTrigger: ({ children, className }) => <div className={className}>{children}</div>,
    SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
    SelectContent: ({ children }) => <div>{children}</div>,
    SelectItem: ({ children, value }) => {
      const { onValueChange } = React.useContext(SelectContext);
      return (
        <button type="button" data-value={value} onClick={() => onValueChange(value)}>
          {children}
        </button>
      );
    },
  };
});

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }) => open ? <div>{children}</div> : null,
  DialogContent: ({ children, className }) => <div className={className}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

vi.mock('../components/ui/tabs', () => {
  const TabsContext = React.createContext({ value: 'land', onValueChange: () => {} });

  return {
    Tabs: ({ children, value, onValueChange }) => (
      <TabsContext.Provider value={{ value, onValueChange }}>
        <div>{children}</div>
      </TabsContext.Provider>
    ),
    TabsList: ({ children, className }) => <div className={className}>{children}</div>,
    TabsTrigger: ({ children, value }) => {
      const ctx = React.useContext(TabsContext);
      return <button type="button" onClick={() => ctx.onValueChange(value)}>{children}</button>;
    },
    TabsContent: ({ children, value }) => {
      const ctx = React.useContext(TabsContext);
      return ctx.value === value ? <div>{children}</div> : null;
    },
  };
});

vi.mock('../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, disabled }) => (
    <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onCheckedChange && onCheckedChange(e.target.checked)} />
  ),
}));

vi.mock('../components/ui/radio-group', () => ({
  RadioGroup: ({ children, value, onValueChange, className }) => <div className={className}>{children}</div>,
  RadioGroupItem: ({ value, id, className }) => <input type="radio" id={id} value={value} className={className} />,
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

vi.mock('../components/ui/alert-dialog', () => ({
  AlertDialog: ({ children, open, onOpenChange }) => open ? <div>{children}</div> : null,
  AlertDialogContent: ({ children }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }) => <h2>{children}</h2>,
  AlertDialogDescription: ({ children }) => <p>{children}</p>,
  AlertDialogFooter: ({ children }) => <div>{children}</div>,
  AlertDialogAction: ({ children, onClick }) => <button type="button" onClick={onClick}>{children}</button>,
  AlertDialogCancel: ({ children, onClick }) => <button type="button" onClick={onClick}>{children}</button>,
}));

vi.mock('../components/ui/dropdown-menu', () => ({
  DropdownMenu: ({ children }) => <div>{children}</div>,
  DropdownMenuTrigger: ({ children }) => <div>{children}</div>,
  DropdownMenuContent: ({ children }) => <div>{children}</div>,
  DropdownMenuItem: ({ children, onClick, className }) => (
    <button onClick={onClick} className={className} aria-label={typeof children[1] === 'string' ? children[1].trim() : ''}>
      {children}
    </button>
  ),
}));

vi.mock('lucide-react', () => ({
  Plus: () => null, Pencil: () => null, Trash2: () => null, Zap: () => null,
  Droplets: () => null, HelpCircle: () => null, Search: () => null, X: () => null,
  ChevronLeft: () => null, ChevronRight: () => null, Edit: () => null, Check: () => null,
  ArrowLeftRight: () => null, MoreHorizontal: () => null,
}));

const mockLogistics = [
  {
    id: 1,
    name: '陆运RFBS-RU',
    type: 'land',
    fulfillment_type: 'rfbs',
    destination: 'RU',
    is_active: true,
    delivery_method: 'pickup',
    min_days: 3,
    max_days: 7,
    base_fee: 10,
    continue_fee: 2,
    continue_unit: 'kg',
    price_limit_cny: 120,
    price_min_cny: 30,
    allow_battery: false,
    allow_liquid: false,
  },
  {
    id: 2,
    name: '空运FBP-BY',
    type: 'air',
    fulfillment_type: 'fbp',
    destination: 'BY',
    is_smart: 1,
    is_active: true,
    delivery_method: 'door',
    min_days: 1,
    max_days: 3,
    base_fee: 20,
    continue_fee: 5,
    continue_unit: 'kg',
    price_limit_cny: 220,
    price_min_cny: 60,
    allow_battery: true,
    allow_liquid: false,
  },
  {
    id: 3,
    name: '陆运RFBS-KZ',
    type: 'land',
    fulfillment_type: 'rfbs',
    destination: 'KZ',
    is_active: true,
    delivery_method: 'pickup',
    min_days: 5,
    max_days: 9,
    base_fee: 15,
    continue_fee: 3,
    continue_unit: 'kg',
    price_limit_cny: 180,
    price_min_cny: 40,
    allow_battery: false,
    allow_liquid: true,
  },
];

const mockStore = {
  logistics: mockLogistics,
  setLogistics: vi.fn(),
  addLogistics: vi.fn(),
  updateLogistics: vi.fn(),
  removeLogistics: vi.fn(),
};

const mockLandLogistics = mockLogistics.filter(l => l.type === 'land');
const mockAirLogistics = mockLogistics.filter(l => l.type === 'air');

describe('LogisticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useLogisticsStore.mockReturnValue(mockStore);
    logisticsAPI.getAll.mockImplementation((params) => {
      const type = params?.type || 'land';
      const items = type === 'air' ? mockAirLogistics : mockLandLogistics;
      return Promise.resolve({ items, total: items.length });
    });
  });

  it('renders logistics page heading', () => {
    render(<LogisticsPage />);
    expect(screen.getByText('物流规则管理')).toBeInTheDocument();
  });

  it('renders add logistics button', () => {
    render(<LogisticsPage />);
    expect(screen.getByText('添加物流规则')).toBeInTheDocument();
  });

  it('calls logisticsAPI.getAll on mount with type param', async () => {
    render(<LogisticsPage />);
    await waitFor(() => {
      expect(logisticsAPI.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'land' })
      );
    });
  });

  it('renders logistics items from store', () => {
    render(<LogisticsPage />);
    expect(screen.getByText('陆运RFBS-RU')).toBeInTheDocument();
  });

  it('renders tab labels without counts', () => {
    render(<LogisticsPage />);

    expect(screen.getByRole('button', { name: '陆运' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '空运' })).toBeInTheDocument();
  });

  it('filters rendered rules by fulfillment type with server-side type param', async () => {
    render(<LogisticsPage />);

    fireEvent.click(screen.getByRole('button', { name: 'FBP' }));

    await waitFor(() => {
      expect(logisticsAPI.getAll).toHaveBeenLastCalledWith(
        expect.objectContaining({ fulfillment_type: 'fbp', type: 'land' })
      );
    });
  });

  it('filters rendered rules by destination with server-side type param', async () => {
    render(<LogisticsPage />);

    fireEvent.click(screen.getByRole('button', { name: '阿塞拜疆(AZ)' }));

    await waitFor(() => {
      expect(logisticsAPI.getAll).toHaveBeenLastCalledWith(
        expect.objectContaining({ destination: 'AZ', type: 'land' })
      );
    });
  });

  it('opens add dialog when add button is clicked', () => {
    render(<LogisticsPage />);
    fireEvent.click(screen.getByText('添加物流规则'));
    expect(screen.getByText('添加物流规则', { selector: 'h2' })).toBeInTheDocument();
  });

  it('shows validation error when submitting empty form', async () => {
    render(<LogisticsPage />);
    fireEvent.click(screen.getByText('添加物流规则'));

    await waitFor(() => {
      expect(screen.getByText('创建')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('创建'));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('请填写名称');
    });
  });

  it('creates logistics item when form is filled and submitted', async () => {
    const newItem = { id: 3, name: '新物流', type: 'land', is_active: true };
    logisticsAPI.create.mockResolvedValue(newItem);

    render(<LogisticsPage />);
    fireEvent.click(screen.getByText('添加物流规则'));

    await waitFor(() => {
      expect(screen.getByPlaceholderText('请输入名称')).toBeInTheDocument();
    });

    fireEvent.change(screen.getByPlaceholderText('请输入名称'), { target: { value: '新物流' } });
    const zeroFields = screen.getAllByPlaceholderText('0.00');
    fireEvent.change(zeroFields[zeroFields.length - 2], { target: { value: '199.99' } });
    fireEvent.change(zeroFields[zeroFields.length - 1], { target: { value: '88.88' } });
    fireEvent.click(screen.getByText('创建'));

    await waitFor(() => {
      expect(logisticsAPI.create).toHaveBeenCalledWith(expect.objectContaining({
        name: '新物流',
        price_limit_cny: 199.99,
        price_min_cny: 88.88,
      }));
      expect(toast.success).toHaveBeenCalledWith('创建成功');
    });
  });

  it('opens edit dialog with existing data when edit button clicked', async () => {
    render(<LogisticsPage />);

    const editBtns = screen.getAllByLabelText('编辑');
    fireEvent.click(editBtns[0]);

    await waitFor(() => {
      expect(screen.getByText('编辑物流规则')).toBeInTheDocument();
      expect(screen.getByDisplayValue('120.00')).toBeInTheDocument();
      expect(screen.getByDisplayValue('30.00')).toBeInTheDocument();
    });
  });

  it('shows CNY limit fields without currency selector', async () => {
    render(<LogisticsPage />);

    fireEvent.click(screen.getByText('添加物流规则'));

    await waitFor(() => {
      expect(screen.getByText('价格上限（元）')).toBeInTheDocument();
      expect(screen.getByText('价格下限（元）')).toBeInTheDocument();
      expect(screen.queryByText('货币单位')).not.toBeInTheDocument();
    });
  });

  it('deletes logistics item after confirmation', async () => {
    logisticsAPI.delete.mockResolvedValue({});

    render(<LogisticsPage />);

    const deleteBtns = screen.getAllByLabelText('删除');
    fireEvent.click(deleteBtns[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '确认删除' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));

    await waitFor(() => {
      expect(logisticsAPI.delete).toHaveBeenCalledWith(mockLogistics[0].id);
      expect(toast.success).toHaveBeenCalledWith('删除成功');
    });
  });

  it('renders new fields fulfillment_type, destination and is_smart', async () => {
    const newMockLand = [
      { id: 1, name: '陆运测试', type: 'land', fulfillment_type: 'rfbs', destination: 'RU', is_smart: 0, is_active: true },
    ];
    const newMockAir = [
      { id: 2, name: '空运测试', type: 'air', fulfillment_type: 'fbp', destination: 'BY', is_smart: 1, is_active: true },
    ];
    logisticsAPI.getAll.mockImplementation((params) => {
      const type = params?.type || 'land';
      const items = type === 'air' ? newMockAir : newMockLand;
      return Promise.resolve({ items, total: items.length });
    });
    useLogisticsStore.mockReturnValue({ ...mockStore, logistics: newMockLand });

    render(<LogisticsPage />);
    
    await waitFor(() => {
      expect(screen.getByText('陆运测试')).toBeInTheDocument();
    });

    const airTab = screen.getByRole('button', { name: '空运' });
    fireEvent.click(airTab);

    await waitFor(() => {
      expect(logisticsAPI.getAll).toHaveBeenCalledWith(
        expect.objectContaining({ type: 'air' })
      );
    });
  });

  it('shows error toast when delete fails', async () => {
    logisticsAPI.delete.mockRejectedValue(new Error('删除失败'));

    render(<LogisticsPage />);

    const deleteBtns = screen.getAllByLabelText('删除');
    fireEvent.click(deleteBtns[0]);

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '确认删除' })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole('button', { name: '确认删除' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('删除失败');
    });
  });

  it('shows error when getAll fails on mount', async () => {
    logisticsAPI.getAll.mockRejectedValue(new Error('服务器错误'));
    render(<LogisticsPage />);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('获取物流规则列表失败');
    });
  });

  it('shows specific error detail when getAll returns 429', async () => {
    const error = new Error('Too many requests');
    error.response = { data: { detail: 'Too many requests' } };
    logisticsAPI.getAll.mockRejectedValue(error);
    render(<LogisticsPage />);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Too many requests');
    });
  });

  it('toggles active status without refetching list', async () => {
    const updatedItem = { ...mockLogistics[0], is_active: false };
    logisticsAPI.update.mockResolvedValue(updatedItem);

    render(<LogisticsPage />);

    await waitFor(() => {
      expect(screen.getByText('陆运RFBS-RU')).toBeInTheDocument();
    });

    const callCountBefore = logisticsAPI.getAll.mock.calls.length;
    const checkboxes = screen.getAllByRole('checkbox');
    const switchCheckbox = checkboxes.find(el => el.checked === true);
    fireEvent.click(switchCheckbox);

    await waitFor(() => {
      expect(logisticsAPI.update).toHaveBeenCalledWith(
        expect.any(Number),
        expect.objectContaining({ is_active: false })
      );
      expect(mockStore.updateLogistics).toHaveBeenCalled();
    });

    // Should NOT have called getAll again after toggle
    expect(logisticsAPI.getAll.mock.calls.length).toBe(callCountBefore);
  });

  it('shows specific error when toggle active fails with detail', async () => {
    const error = new Error('Rate limited');
    error.response = { data: { detail: 'Too many requests' } };
    logisticsAPI.update.mockRejectedValue(error);

    render(<LogisticsPage />);

    await waitFor(() => {
      expect(screen.getByText('陆运RFBS-RU')).toBeInTheDocument();
    });

    const checkboxes = screen.getAllByRole('checkbox');
    const switchCheckbox = checkboxes.find(el => el.checked === true);
    fireEvent.click(switchCheckbox);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('Too many requests');
    });
  });
});
