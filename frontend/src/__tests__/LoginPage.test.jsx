import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';
import { authAPI } from '../services/api';
import { toast } from 'sonner';

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock('../services/api', () => ({
  authAPI: {
    login: vi.fn(),
  },
  settingsAPI: {
    get: vi.fn().mockResolvedValue({ open_registration: true }),
  },
}));

const mockSetAuth = vi.fn();
vi.mock('../stores/authStore', () => ({
  useAuthStore: () => ({
    setAuth: mockSetAuth,
    isAuthenticated: false,
    user: null,
    logout: vi.fn(),
  }),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
  };

  it('renders login form with username/password fields', () => {
    renderComponent();
    expect(screen.getByPlaceholderText('请输入用户名')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('请输入密码')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: '登录' })).toBeInTheDocument();
  });

  it('shows validation errors for empty fields', async () => {
    renderComponent();
    
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    
    await waitFor(() => {
      expect(screen.getByText('请输入用户名')).toBeInTheDocument();
      expect(screen.getByText('密码至少13位')).toBeInTheDocument();
    });
  });

  it('shows password min length error (min 13)', async () => {
    renderComponent();
    
    fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: '123456' } });
    
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    
    await waitFor(() => {
      expect(screen.getByText('密码至少13位')).toBeInTheDocument();
      expect(screen.queryByText('请输入用户名')).not.toBeInTheDocument();
    });
  });

  it('toggles password visibility on eye icon click', () => {
    renderComponent();
    
    const passwordInput = screen.getByPlaceholderText('请输入密码');
    expect(passwordInput).toHaveAttribute('type', 'password');
    
    const toggleBtn = passwordInput.nextElementSibling;
    fireEvent.click(toggleBtn);
    
    expect(passwordInput).toHaveAttribute('type', 'text');
    
    fireEvent.click(toggleBtn);
    expect(passwordInput).toHaveAttribute('type', 'password');
  });

  it('calls authAPI.login and setAuth + navigates on success', async () => {
    authAPI.login.mockResolvedValueOnce({
      access_token: 'fake-token',
      user: { id: 1, username: 'admin' }
    });
    
    renderComponent();
    
    fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: '1234567890123' } });
    
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    
    await waitFor(() => {
      expect(authAPI.login).toHaveBeenCalledWith('admin', '1234567890123');
      expect(mockSetAuth).toHaveBeenCalledWith({ id: 1, username: 'admin' }, 'fake-token');
      expect(toast.success).toHaveBeenCalledWith('登录成功');
      expect(mockNavigate).toHaveBeenCalledWith('/pricing');
    });
  });

  it('shows error message on login failure (API error)', async () => {
    authAPI.login.mockRejectedValueOnce({
      response: { data: { detail: '无效的用户名或密码' } }
    });
    
    renderComponent();
    
    fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: '1234567890123' } });
    
    fireEvent.click(screen.getByRole('button', { name: '登录' }));
    
    await waitFor(() => {
      expect(authAPI.login).toHaveBeenCalled();
      expect(toast.error).toHaveBeenCalledWith('无效的用户名或密码');
      expect(screen.getByText('无效的用户名或密码')).toBeInTheDocument();
    });
  });

  it('shows "去注册" link that navigates to /register', () => {
    renderComponent();
    
    const registerLink = screen.getByText('去注册');
    expect(registerLink).toBeInTheDocument();
    
    fireEvent.click(registerLink);
    expect(mockNavigate).toHaveBeenCalledWith('/register');
  });

  it('shows forgot password link to /forgot-password', () => {
    renderComponent();

    const forgotLink = screen.getByText('忘记密码？').closest('a');

    expect(forgotLink).toBeInTheDocument();
    expect(forgotLink).toHaveAttribute('href', '/forgot-password');
  });

  it('submit button shows "登录中..." when loading', async () => {
    let resolveLogin;
    const loginPromise = new Promise(resolve => {
      resolveLogin = resolve;
    });
    authAPI.login.mockReturnValue(loginPromise);
    
    renderComponent();
    
    fireEvent.change(screen.getByPlaceholderText('请输入用户名'), { target: { value: 'admin' } });
    fireEvent.change(screen.getByPlaceholderText('请输入密码'), { target: { value: '1234567890123' } });
    
    const submitBtn = screen.getByRole('button', { name: '登录' });
    fireEvent.click(submitBtn);
    
    await waitFor(() => {
      expect(screen.getByRole('button', { name: '登录中...' })).toBeInTheDocument();
      expect(screen.getByRole('button', { name: '登录中...' })).toBeDisabled();
    });
    
    resolveLogin({ access_token: 't', user: {} });
  });
});
