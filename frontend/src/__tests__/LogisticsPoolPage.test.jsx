import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LogisticsPoolPage from '../pages/LogisticsPoolPage';
import { logisticsPoolAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  logisticsPoolAPI: {
    getAll: vi.fn(),
    importXlsx: vi.fn(),
    addToMyLogistics: vi.fn(),
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
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableRow: ({ children }) => <tr>{children}</tr>,
  TableHead: ({ children }) => <th>{children}</th>,
  TableCell: ({ children, colSpan, className }) => <td colSpan={colSpan} className={className}>{children}</td>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className }) => (
    <button onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className }) => <span className={className}>{children}</span>,
}));

const mockLogistics = [
  {
    id: 1,
    name: '测试物流 1',
    fulfillment_type: 'rfbs',
    destination: 'RU',
    fbp_service_level: null,
    is_smart: 0,
    is_active: true,
  },
  {
    id: 2,
    name: '智能物流 FBP',
    fulfillment_type: 'fbp',
    destination: 'BY',
    fbp_service_level: 'standard',
    is_smart: 1,
    is_active: false,
  },
];

describe('LogisticsPoolPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    logisticsPoolAPI.getAll.mockResolvedValue(mockLogistics);
    useAuthStore.mockReturnValue({ isAdmin: () => false });
  });

  it('renders correctly and fetches logistics on mount', async () => {
    render(<LogisticsPoolPage />);
    
    expect(screen.getByText('公共物流池')).toBeInTheDocument();
    
    // Check loading state
    expect(screen.getByText('加载中...')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(logisticsPoolAPI.getAll).toHaveBeenCalledTimes(1);
    });
    
    // Check rendered items
    expect(screen.getByText('测试物流 1')).toBeInTheDocument();
    expect(screen.getByText('rfbs')).toBeInTheDocument();
    expect(screen.getByText('RU')).toBeInTheDocument();
    
    expect(screen.getByText('智能物流 FBP')).toBeInTheDocument();
    expect(screen.getByText('fbp')).toBeInTheDocument();
    expect(screen.getByText('BY')).toBeInTheDocument();
    expect(screen.getByText('standard')).toBeInTheDocument();
    expect(screen.getByText('智能分配')).toBeInTheDocument();
    expect(screen.getByText('生效中')).toBeInTheDocument();
    expect(screen.getByText('已停用')).toBeInTheDocument();
    
    // Check that import button is not visible for non-admins
    expect(screen.queryByText('导入 Excel')).not.toBeInTheDocument();
  });

  it('handles API error during fetch', async () => {
    logisticsPoolAPI.getAll.mockRejectedValue(new Error('Fetch error'));
    
    render(<LogisticsPoolPage />);
    
    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('获取物流池数据失败');
    });
    
    expect(screen.getByText('暂无物流数据')).toBeInTheDocument();
  });

  it('shows import button for admins', async () => {
    useAuthStore.mockReturnValue({ isAdmin: () => true });
    
    render(<LogisticsPoolPage />);
    
    expect(screen.getByText('导入 Excel')).toBeInTheDocument();
  });

  it('handles importing xlsx file successfully', async () => {
    useAuthStore.mockReturnValue({ isAdmin: () => true });
    logisticsPoolAPI.importXlsx.mockResolvedValue({});
    
    // Create a dummy file
    const file = new File(['dummy content'], 'test.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    
    render(<LogisticsPoolPage />);
    
    // Find the hidden file input
    // The component renders the input with type="file" inside a div where the button is
    const input = document.querySelector('input[type="file"]');
    
    fireEvent.change(input, { target: { files: [file] } });
    
    await waitFor(() => {
      expect(logisticsPoolAPI.importXlsx).toHaveBeenCalledTimes(1);
      expect(toast.success).toHaveBeenCalledWith('导入成功');
      expect(logisticsPoolAPI.getAll).toHaveBeenCalledTimes(2); // Initial + after import
    });
  });

  it('adds a logistics item to my logistics', async () => {
    logisticsPoolAPI.addToMyLogistics.mockResolvedValue({});
    
    render(<LogisticsPoolPage />);
    
    await waitFor(() => {
      expect(screen.getByText('测试物流 1')).toBeInTheDocument();
    });
    
    const addButtons = screen.getAllByText('添加到我的');
    fireEvent.click(addButtons[0]); // Click first item's button
    
    await waitFor(() => {
      expect(logisticsPoolAPI.addToMyLogistics).toHaveBeenCalledWith(1);
      expect(toast.success).toHaveBeenCalledWith('已成功添加到我的物流');
    });
  });

  it('handles error when adding to my logistics', async () => {
    logisticsPoolAPI.addToMyLogistics.mockRejectedValue(new Error('Conflict'));
    
    render(<LogisticsPoolPage />);
    
    await waitFor(() => {
      expect(screen.getByText('测试物流 1')).toBeInTheDocument();
    });
    
    const addButtons = screen.getAllByText('添加到我的');
    fireEvent.click(addButtons[0]);
    
    await waitFor(() => {
      expect(logisticsPoolAPI.addToMyLogistics).toHaveBeenCalledWith(1);
      expect(toast.error).toHaveBeenCalledWith('添加失败，可能已经存在');
    });
  });
});
