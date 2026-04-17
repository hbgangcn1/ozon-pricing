import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import UserManagementPage from '../pages/UserManagementPage';
import { adminAPI } from '../services/api';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  adminAPI: {
    getUsers: vi.fn(),
    createUser: vi.fn(),
    updateUser: vi.fn(),
    deleteUser: vi.fn(),
    resetPassword: vi.fn(),
    extendSubscription: vi.fn(),
    adjustCalculations: vi.fn(),
    setUserType: vi.fn(),
  },
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
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, type, _variant, _size }) => (
    <button onClick={onClick} disabled={disabled} className={className} type={type}>{children}</button>
  ),
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className, _variant }) => <span className={className}>{children}</span>,
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableCell: ({ children, className }) => <td className={className}>{children}</td>,
  TableHead: ({ children, className }) => <th className={className}>{children}</th>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableRow: ({ children, onClick, className }) => <tr onClick={onClick} className={className}>{children}</tr>,
}));

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ children, open, _onOpenChange }) => open ? <div>{children}</div> : null,
  DialogContent: ({ children }) => <div>{children}</div>,
  DialogHeader: ({ children }) => <div>{children}</div>,
  DialogTitle: ({ children }) => <h2>{children}</h2>,
  DialogFooter: ({ children }) => <div>{children}</div>,
  DialogTrigger: ({ children }) => <div>{children}</div>,
}));

vi.mock('../components/ui/select', () => ({
  Select: ({ children, _onValueChange, _value }) => <div>{children}</div>,
  SelectTrigger: ({ children, className }) => <div className={className}>{children}</div>,
  SelectValue: ({ placeholder }) => <span>{placeholder}</span>,
  SelectContent: ({ children }) => <div>{children}</div>,
  SelectItem: ({ children, value }) => (
    <div data-value={value} onClick={() => {}}>{children}</div>
  ),
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor }) => <label htmlFor={htmlFor}>{children}</label>,
}));

vi.mock('lucide-react', () => ({
  UserPlus: () => null, Key: () => null, Trash2: () => null, RefreshCw: () => null,
  Search: () => null, X: () => null, Plus: () => null, User: () => null,
  Lock: () => null, Shield: () => null, Check: () => null, ChevronLeft: () => null,
  ChevronRight: () => null, Edit: () => null, Eye: () => null, EyeOff: () => null,
}));

const mockUsersResponse = {
  users: [
    { id: 1, username: 'admin', role: 'admin', user_type: '永久有效', status: '正常' },
    { id: 2, username: 'testuser', role: 'user', user_type: '专业版', status: '正常' },
  ],
  total: 2,
  page: 1,
  page_size: 20,
};

describe('UserManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    adminAPI.getUsers.mockResolvedValue(mockUsersResponse);
    window.confirm = vi.fn(() => true);
  });

  it('renders page heading', async () => {
    render(<UserManagementPage />);
    expect(screen.getByText(/用户管理/)).toBeInTheDocument();
  });

  it('renders user list after loading', async () => {
    render(<UserManagementPage />);
    await waitFor(() => {
      const adminCells = screen.getAllByText('admin');
      expect(adminCells.some(el => el.tagName === 'TD')).toBe(true);
      const testuserCells = screen.getAllByText('testuser');
      expect(testuserCells.some(el => el.tagName === 'TD')).toBe(true);
    });
  });

  it('calls adminAPI.getUsers on mount', async () => {
    render(<UserManagementPage />);
    await waitFor(() => {
      expect(adminAPI.getUsers).toHaveBeenCalledWith(1, 20, '');
    });
  });

  it('shows add user form section', async () => {
    render(<UserManagementPage />);
    expect(screen.getByRole('heading', { name: /添加新用户/ })).toBeInTheDocument();
    expect(screen.getByPlaceholderText('请输入用户名')).toBeInTheDocument();
  });

  it('creates user when form is submitted', async () => {
    adminAPI.createUser.mockResolvedValue({ id: 3, username: 'newuser', role: 'user' });
    render(<UserManagementPage />);

    const usernameInput = screen.getByPlaceholderText('请输入用户名');
    fireEvent.change(usernameInput, { target: { value: 'newuser' } });

    const passwordInput = screen.getByPlaceholderText('请输入密码');
    fireEvent.change(passwordInput, { target: { value: 'password123' } });

    const form = usernameInput.closest('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(adminAPI.createUser).toHaveBeenCalledWith(
        expect.objectContaining({ username: 'newuser', password: 'password123' })
      );
      expect(toast.success).toHaveBeenCalledWith('用户创建成功');
    });
  });

  it('shows validation error when creating user with empty fields', async () => {
    render(<UserManagementPage />);

    const usernameInput = screen.getByPlaceholderText('请输入用户名');
    const form = usernameInput.closest('form');
    fireEvent.submit(form);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('请填写所有必填字段');
    });
  });

  it('shows user actions panel when user is selected', async () => {
    render(<UserManagementPage />);

    await waitFor(() => {
      const adminCells = screen.getAllByText('admin');
      expect(adminCells.some(el => el.tagName === 'TD')).toBe(true);
    });

    const adminTd = screen.getAllByText('admin').find(el => el.tagName === 'TD');
    const adminRow = adminTd.closest('tr');
    fireEvent.click(adminRow);

    await waitFor(() => {
      expect(screen.getByText(/用户操作/)).toBeInTheDocument();
    });
  });

  it('resets password and shows toast', async () => {
    render(<UserManagementPage />);

    await waitFor(() => {
      const adminCells = screen.getAllByText('admin');
      expect(adminCells.some(el => el.tagName === 'TD')).toBe(true);
    });

    const adminTd = screen.getAllByText('admin').find(el => el.tagName === 'TD');
    const adminRow = adminTd.closest('tr');
    fireEvent.click(adminRow);

    await waitFor(() => {
      expect(screen.getByText(/重置密码/)).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText(/重置密码/));
    expect(toast.success).toHaveBeenCalledWith(expect.stringContaining('密码已重置'));
  });

  it('shows error toast when getUsers fails', async () => {
    adminAPI.getUsers.mockRejectedValue({ response: { data: { detail: '获取失败' } } });
    render(<UserManagementPage />);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('获取失败');
    });
  });

  it('opens subscription dialog and extends subscription', async () => {
    adminAPI.extendSubscription.mockResolvedValue({});
    render(<UserManagementPage />);

    await waitFor(() => {
      expect(screen.getAllByText('订阅').length).toBeGreaterThan(0);
    });

    const subscribeButtons = screen.getAllByRole('button', { name: '订阅' });
    fireEvent.click(subscribeButtons[0]);

    await waitFor(() => {
      const headings = screen.getAllByRole('heading');
      expect(headings.some(h => h.textContent.includes('订阅管理 -'))).toBe(true);
    });

    const daysInput = screen.getByPlaceholderText('正数延长，负数缩短');
    fireEvent.change(daysInput, { target: { value: '30' } });
    
    const extendBtn = screen.getAllByText('调整')[0];
    fireEvent.click(extendBtn);

    await waitFor(() => {
      expect(adminAPI.extendSubscription).toHaveBeenCalledWith(1, 30);
      expect(toast.success).toHaveBeenCalledWith('到期时间调整成功');
    });
  });
});
