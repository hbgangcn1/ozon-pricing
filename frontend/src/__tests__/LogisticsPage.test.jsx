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

vi.mock('../components/ui/select', () => ({
  Select: ({ children, onValueChange, value }) => <div>{children}</div>,
  SelectTrigger: ({ children, className }) => <div className={className}>{children}</div>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => <div data-value={value}>{children}</div>,
}));

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ children, open, onOpenChange }) => open ? <div>{children}</div> : null,
  DialogContent: ({ children, className }) => <div className={className}>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

vi.mock('../components/ui/tabs', () => ({
  Tabs: ({ children, defaultValue }) => <div>{children}</div>,
  TabsList: ({ children, className }) => <div className={className}>{children}</div>,
  TabsTrigger: ({ children, value }) => <button>{children}</button>,
  TabsContent: ({ children, value }) => <div>{children}</div>,
}));

vi.mock('../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange }) => (
    <input type="checkbox" checked={checked} onChange={(e) => onCheckedChange && onCheckedChange(e.target.checked)} />
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
  AlertDialogAction: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
  AlertDialogCancel: ({ children, onClick }) => <button onClick={onClick}>{children}</button>,
}));

vi.mock('lucide-react', () => ({
  Plus: () => null, Pencil: () => null, Trash2: () => null, Zap: () => null,
  Droplets: () => null, HelpCircle: () => null, Search: () => null, X: () => null,
  ChevronLeft: () => null, ChevronRight: () => null, Edit: () => null, Check: () => null,
}));

const mockLogistics = [
  { id: 1, name: '陆运测试', type: 'land', is_active: true, delivery_method: 'pickup', min_days: 3, max_days: 7, base_fee: 10, continue_fee: 2, continue_unit: 'kg', allow_battery: false, allow_liquid: false },
  { id: 2, name: '空运测试', type: 'air', is_active: true, delivery_method: 'door', min_days: 1, max_days: 3, base_fee: 20, continue_fee: 5, continue_unit: 'kg', allow_battery: true, allow_liquid: false },
];

const mockStore = {
  logistics: mockLogistics,
  setLogistics: vi.fn(),
  addLogistics: vi.fn(),
  updateLogistics: vi.fn(),
  removeLogistics: vi.fn(),
};

describe('LogisticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useLogisticsStore.mockReturnValue(mockStore);
    logisticsAPI.getAll.mockResolvedValue(mockLogistics);
  });

  it('renders logistics page heading', () => {
    render(<LogisticsPage />);
    expect(screen.getByText('物流规则管理')).toBeInTheDocument();
  });

  it('renders add logistics button', () => {
    render(<LogisticsPage />);
    expect(screen.getByText('添加物流规则')).toBeInTheDocument();
  });

  it('calls logisticsAPI.getAll on mount', async () => {
    render(<LogisticsPage />);
    await waitFor(() => {
      expect(logisticsAPI.getAll).toHaveBeenCalled();
    });
  });

  it('renders logistics items from store', () => {
    render(<LogisticsPage />);
    expect(screen.getByText('陆运测试')).toBeInTheDocument();
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
    fireEvent.click(screen.getByText('创建'));

    await waitFor(() => {
      expect(logisticsAPI.create).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith('创建成功');
    });
  });

  it('opens edit dialog with existing data when edit button clicked', async () => {
    render(<LogisticsPage />);

    const editBtns = screen.getAllByLabelText('编辑');
    fireEvent.click(editBtns[0]);

    await waitFor(() => {
      expect(screen.getByText('编辑物流规则')).toBeInTheDocument();
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
});
