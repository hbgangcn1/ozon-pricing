import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import AccountPage from '../pages/AccountPage';
import { authAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  authAPI: {
    changePassword: vi.fn(),
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

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children }) => <div>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

describe('AccountPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => render(<AccountPage />);

  it('renders "账户管理" heading', () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' } });
    renderComponent();
    expect(screen.getByText(/账户管理 — 管理账户信息和密码/)).toBeInTheDocument();
  });

  it('shows "修改密码" card with password form', () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' } });
    renderComponent();
    expect(screen.getByText('🔒 修改密码')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('请输入当前密码')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('请输入新密码（至少13位）')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('请再次输入新密码')).toBeInTheDocument();
  });

  it('shows account info card with username and role', () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user', user_type: 'premium' } });
    renderComponent();
    expect(screen.getByText('ℹ️ 账户信息')).toBeInTheDocument();
    expect(screen.getByText('testuser')).toBeInTheDocument();
    expect(screen.getByText('普通用户')).toBeInTheDocument();
    expect(screen.getByText('premium')).toBeInTheDocument();
  });

  it('shows "管理员" for admin users, "普通用户" for regular users', () => {
    useAuthStore.mockReturnValue({ user: { username: 'admin', role: 'admin' } });
    renderComponent();
    expect(screen.getByText('管理员')).toBeInTheDocument();
  });

  it('password mismatch shows error toast "新密码与确认密码不匹配"', async () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' } });
    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入当前密码'), { target: { value: 'oldpass123' } });
    fireEvent.change(screen.getByPlaceholderText('请输入新密码（至少13位）'), { target: { value: 'newpass123456!' } });
    fireEvent.change(screen.getByPlaceholderText('请再次输入新密码'), { target: { value: 'newpass123456@' } });
    
    fireEvent.click(screen.getByRole('button', { name: '修改密码' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('新密码与确认密码不匹配');
    });
  });

  it('successful password change calls authAPI.changePassword and shows success toast', async () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' } });
    authAPI.changePassword.mockResolvedValueOnce({});
    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入当前密码'), { target: { value: 'oldpass123' } });
    fireEvent.change(screen.getByPlaceholderText('请输入新密码（至少13位）'), { target: { value: 'newpass123456!' } });
    fireEvent.change(screen.getByPlaceholderText('请再次输入新密码'), { target: { value: 'newpass123456!' } });
    
    fireEvent.click(screen.getByRole('button', { name: '修改密码' }));

    await waitFor(() => {
      expect(authAPI.changePassword).toHaveBeenCalledWith({
        current_password: 'oldpass123',
        new_password: 'newpass123456!',
      });
      expect(toast.success).toHaveBeenCalledWith('密码修改成功');
    });

    expect(screen.getByPlaceholderText('请输入当前密码').value).toBe('');
    expect(screen.getByPlaceholderText('请输入新密码（至少13位）').value).toBe('');
    expect(screen.getByPlaceholderText('请再次输入新密码').value).toBe('');
  });

  it('failed password change shows error toast', async () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' } });
    authAPI.changePassword.mockRejectedValueOnce({ response: { data: { detail: '原密码错误' } } });
    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入当前密码'), { target: { value: 'oldpass123' } });
    fireEvent.change(screen.getByPlaceholderText('请输入新密码（至少13位）'), { target: { value: 'newpass123456!' } });
    fireEvent.change(screen.getByPlaceholderText('请再次输入新密码'), { target: { value: 'newpass123456!' } });
    
    fireEvent.click(screen.getByRole('button', { name: '修改密码' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('原密码错误');
    });
  });

  it('submit button shows "修改中..." when loading', async () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' } });
    authAPI.changePassword.mockImplementationOnce(() => new Promise((resolve) => setTimeout(resolve, 100)));
    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入当前密码'), { target: { value: 'oldpass123' } });
    fireEvent.change(screen.getByPlaceholderText('请输入新密码（至少13位）'), { target: { value: 'newpass123456!' } });
    fireEvent.change(screen.getByPlaceholderText('请再次输入新密码'), { target: { value: 'newpass123456!' } });
    
    fireEvent.click(screen.getByRole('button', { name: '修改密码' }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: '修改中...' })).toBeInTheDocument();
    });
  });
});
