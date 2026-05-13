import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import CommissionCategoriesPage from '../pages/CommissionCategoriesPage';
import { commissionCategoriesAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  commissionCategoriesAPI: {
    getAll: vi.fn(),
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
  },
}));

// Mock UI components
vi.mock('../components/ui/card', () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardHeader: ({ children }) => <div>{children}</div>,
  CardTitle: ({ children }) => <div>{children}</div>,
  CardContent: ({ children }) => <div>{children}</div>,
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableRow: ({ children }) => <tr>{children}</tr>,
  TableHead: ({ children }) => <th>{children}</th>,
  TableCell: ({ children, colSpan }) => <td colSpan={colSpan}>{children}</td>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, _variant, _size, className, disabled, title }) => (
    <button type="button" onClick={onClick} className={className} disabled={disabled} title={title}>{children}</button>
  ),
}));

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ children, open, _onOpenChange }) => open ? <div>{children}</div> : null,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <div>{children}</div>,
  DialogFooter: ({ children }) => <div>{children}</div>,
}));

vi.mock('../components/ui/input', () => ({
  Input: ({ value, onChange, placeholder, type, id, step }) => (
    <input 
      data-testid={`input-${id}`} 
      value={value} 
      onChange={onChange} 
      placeholder={placeholder} 
      type={type} 
      id={id}
      step={step}
    />
  ),
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor }) => <label htmlFor={htmlFor}>{children}</label>,
}));

const mockCategories = [
  {
    id: 1,
    name: '服装',
    rfbs_tier1_rate: 0.08,
    rfbs_tier2_rate: 0.07,
    rfbs_tier3_rate: 0.06,
  },
  {
    id: 2,
    name: '电子产品',
    rfbs_tier1_rate: 0.05,
    rfbs_tier2_rate: 0.04,
    rfbs_tier3_rate: 0.03,
  },
];

describe('CommissionCategoriesPage', () => {
  const makeStore = (subscriptionType = 'enterprise') => ({
    user: { subscription_type: subscriptionType },
    hasProfessionalAccess: () => ['professional', 'enterprise', 'gratitude', 'test'].includes(subscriptionType),
  })

  beforeEach(() => {
    vi.clearAllMocks();
    commissionCategoriesAPI.getAll.mockResolvedValue(mockCategories);
    useAuthStore.mockReturnValue(makeStore('enterprise'));
    
    // Mock window.confirm
    vi.spyOn(window, 'confirm').mockImplementation(() => true);
  });

  it('renders correctly and fetches categories on mount', async () => {
    render(<CommissionCategoriesPage />);
    
    expect(screen.getByText('佣金类目管理')).toBeInTheDocument();
    
    // Check loading state
    expect(screen.getByText('加载中...')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(1);
    });

    // Check rendered categories (wait for async state update + render)
    expect(await screen.findByText('服装')).toBeInTheDocument();
    expect(screen.getByText('8.00%')).toBeInTheDocument();
    expect(screen.getByText('电子产品')).toBeInTheDocument();
  });

  it('handles API error during fetch', async () => {
    commissionCategoriesAPI.getAll.mockRejectedValue(new Error('Fetch error'));
    
    render(<CommissionCategoriesPage />);
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('获取佣金类目失败');
    });
    
    expect(screen.getByText('暂无佣金类目数据')).toBeInTheDocument();
  });

  it('opens dialog for creating new category', async () => {
    render(<CommissionCategoriesPage />);
    
    await waitFor(() => {
      expect(screen.getByText('服装')).toBeInTheDocument();
    });
    
    // Click "新增类目"
    fireEvent.click(screen.getByText('新增类目'));
    
    expect(screen.getByText('新增佣金类目')).toBeInTheDocument();
  });

  it('creates a new category', async () => {
    commissionCategoriesAPI.create.mockResolvedValue({ id: 3, name: '家具' });
    
    render(<CommissionCategoriesPage />);
    
    await waitFor(() => {
      expect(screen.getByText('服装')).toBeInTheDocument();
    });
    
    // Open dialog
    fireEvent.click(screen.getByText('新增类目'));
    
    // Fill form
    fireEvent.change(screen.getByTestId('input-name'), { target: { value: '家具' } });
    fireEvent.change(screen.getByTestId('input-tier1'), { target: { value: '10' } });
    
    // Submit
    fireEvent.click(screen.getByText('保存'));
    
    await waitFor(() => {
      expect(commissionCategoriesAPI.create).toHaveBeenCalledWith({
        name: '家具',
        rfbs_tier1_rate: 0.1,
        rfbs_tier2_rate: 0,
        rfbs_tier3_rate: 0
      });
      expect(toast.success).toHaveBeenCalledWith('创建成功');
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(2); // Initial + after create
    });
  });

  it('edits an existing category', async () => {
    commissionCategoriesAPI.update.mockResolvedValue({ id: 1, name: '服装编辑' });
    
    render(<CommissionCategoriesPage />);
    
    await waitFor(() => {
      expect(screen.getByText('服装')).toBeInTheDocument();
    });
    
    // We mocked lucide-react Edit2, but button children has the icon. We need to find the edit button.
    // The edit button has the edit icon inside, since we didn't mock lucide-react, the svg might render. 
    // We can find all buttons and click the first edit button (the second button on the page is edit since first is create).
    const buttons = screen.getAllByRole('button');
    // First button: "新增类目", Second button: Edit for cat 1, Third: Delete for cat 1
    fireEvent.click(buttons[1]);
    
    expect(screen.getByText('编辑佣金类目')).toBeInTheDocument();
    
    // Edit form
    fireEvent.change(screen.getByTestId('input-name'), { target: { value: '服装编辑' } });
    
    // Submit
    fireEvent.click(screen.getByText('保存'));
    
    await waitFor(() => {
      expect(commissionCategoriesAPI.update).toHaveBeenCalledWith(1, {
        name: '服装编辑',
        rfbs_tier1_rate: 0.08,
        rfbs_tier2_rate: 0.07,
        rfbs_tier3_rate: 0.06
      });
      expect(toast.success).toHaveBeenCalledWith('更新成功');
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(2);
    });
  });

  it('deletes a category', async () => {
    commissionCategoriesAPI.delete.mockResolvedValue({});
    
    render(<CommissionCategoriesPage />);
    
    await waitFor(() => {
      expect(screen.getByText('服装')).toBeInTheDocument();
    });
    
    const buttons = screen.getAllByRole('button');
    // First button: "新增类目", Second button: Edit for cat 1, Third: Delete for cat 1
    fireEvent.click(buttons[2]);
    
    expect(window.confirm).toHaveBeenCalledWith('确认删除此佣金类目吗？');
    
    await waitFor(() => {
      expect(commissionCategoriesAPI.delete).toHaveBeenCalledWith(1);
      expect(toast.success).toHaveBeenCalledWith('删除成功');
      expect(commissionCategoriesAPI.getAll).toHaveBeenCalledTimes(2);
    });
  });

  it('shows upgrade prompt and skips fetch for free tier without trial', async () => {
    useAuthStore.mockReturnValue(makeStore('free'));

    render(<CommissionCategoriesPage />);

    expect(screen.getByText('当前方案暂不支持此功能')).toBeInTheDocument();
    expect(screen.queryByText('新增类目')).not.toBeInTheDocument();
    expect(screen.getByText('暂无佣金类目数据')).toBeInTheDocument();

    await new Promise((resolve) => setTimeout(resolve, 50));
    expect(commissionCategoriesAPI.getAll).not.toHaveBeenCalled();
  });

  it('grants full management UI to free tier user during active trial', async () => {
    useAuthStore.mockReturnValue({
      user: { subscription_type: 'free' },
      hasProfessionalAccess: () => true,
    });

    render(<CommissionCategoriesPage />);

    await waitFor(() => {
      expect(screen.getByText('服装')).toBeInTheDocument();
    });

    expect(screen.queryByText('当前方案暂不支持此功能')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '新增类目' })).toBeInTheDocument();
    expect(commissionCategoriesAPI.getAll).toHaveBeenCalled();
  });

  it('shows normal management UI for professional tier', async () => {
    useAuthStore.mockReturnValue(makeStore('professional'));

    render(<CommissionCategoriesPage />);

    await waitFor(() => {
      expect(screen.getByText('服装')).toBeInTheDocument();
    });

    expect(screen.queryByText('当前方案暂不支持此功能')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '新增类目' })).toBeInTheDocument();

    const buttons = screen.getAllByRole('button');
    expect(buttons[1]).not.toBeDisabled();
    expect(buttons[2]).not.toBeDisabled();
  });
});
