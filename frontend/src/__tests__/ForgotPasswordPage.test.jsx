import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ForgotPasswordPage from '../pages/ForgotPasswordPage';
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
    startRecovery: vi.fn(),
    verifySecurity: vi.fn(),
    resetPassword: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

describe('ForgotPasswordPage', () => {
  const sessionStorageMock = {
    store: {},
    getItem: vi.fn((key) => (key in sessionStorageMock.store ? sessionStorageMock.store[key] : null)),
    setItem: vi.fn((key, value) => {
      sessionStorageMock.store[key] = String(value);
    }),
    removeItem: vi.fn((key) => {
      delete sessionStorageMock.store[key];
    }),
    clear: vi.fn(() => {
      sessionStorageMock.store = {};
    }),
  };

  const renderComponent = () => render(
    <MemoryRouter>
      <ForgotPasswordPage />
    </MemoryRouter>
  );

  beforeEach(() => {
    vi.clearAllMocks();
    sessionStorageMock.clear();
    Object.defineProperty(window, 'sessionStorage', {
      value: sessionStorageMock,
      configurable: true,
      writable: true,
    });
  });

  it('step 1 submits username, calls startRecovery and shows step 2 questions', async () => {
    authAPI.startRecovery.mockResolvedValueOnce({
      message: '如该账号存在且已设置安全问题，将引导您回答安全问题',
      questions: ['问题一？', '问题二？'],
    });

    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入需要找回的用户名'), {
      target: { value: 'alice' },
    });
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    await waitFor(() => {
      expect(authAPI.startRecovery).toHaveBeenCalledWith('alice');
      expect(screen.getByText('回答安全问题')).toBeInTheDocument();
      expect(screen.getByText('问题一？')).toBeInTheDocument();
      expect(screen.getByText('问题二？')).toBeInTheDocument();
    });
  });

  it('step 2 verifies correct answers and shows step 3', async () => {
    authAPI.startRecovery.mockResolvedValueOnce({ questions: ['问题一？', '问题二？'] });
    authAPI.verifySecurity.mockResolvedValueOnce({ reset_token: 'memory-only-token' });

    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入需要找回的用户名'), {
      target: { value: 'alice' },
    });
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    await screen.findByText('问题一？');

    fireEvent.change(screen.getByPlaceholderText('请输入第一个答案'), {
      target: { value: 'a1' },
    });
    fireEvent.change(screen.getByPlaceholderText('请输入第二个答案'), {
      target: { value: 'a2' },
    });
    fireEvent.click(screen.getByRole('button', { name: '验证答案' }));

    await waitFor(() => {
      expect(authAPI.verifySecurity).toHaveBeenCalledWith('alice', 'a1', 'a2');
      expect(screen.getByText('设置新密码')).toBeInTheDocument();
      expect(screen.getByPlaceholderText('请再次输入新密码')).toBeInTheDocument();
    });
    expect(sessionStorageMock.getItem('reset_token')).toBeNull();
    expect(sessionStorageMock.store.reset_token).toBeUndefined();
  });

  it('step 2 failure shows generic error toast and stays on step 2', async () => {
    authAPI.startRecovery.mockResolvedValueOnce({ questions: ['问题一？', '问题二？'] });
    authAPI.verifySecurity.mockRejectedValueOnce({
      response: { data: { detail: '验证失败，请检查您的回答' } },
    });

    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入需要找回的用户名'), {
      target: { value: 'alice' },
    });
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));

    await screen.findByText('问题一？');

    fireEvent.change(screen.getByPlaceholderText('请输入第一个答案'), {
      target: { value: 'wrong1' },
    });
    fireEvent.change(screen.getByPlaceholderText('请输入第二个答案'), {
      target: { value: 'wrong2' },
    });
    fireEvent.click(screen.getByRole('button', { name: '验证答案' }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('验证失败，请检查您的回答');
    });
    expect(screen.getByText('回答安全问题')).toBeInTheDocument();
    expect(screen.queryByText('设置新密码')).not.toBeInTheDocument();
  });

  it('step 3 submits new password and navigates to /login', async () => {
    authAPI.startRecovery.mockResolvedValueOnce({ questions: ['问题一？', '问题二？'] });
    authAPI.verifySecurity.mockResolvedValueOnce({ reset_token: 'memory-only-token' });
    authAPI.resetPassword.mockResolvedValueOnce({ message: '密码已重置，请重新登录' });

    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入需要找回的用户名'), {
      target: { value: 'alice' },
    });
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    await screen.findByText('问题一？');

    fireEvent.change(screen.getByPlaceholderText('请输入第一个答案'), {
      target: { value: 'a1' },
    });
    fireEvent.change(screen.getByPlaceholderText('请输入第二个答案'), {
      target: { value: 'a2' },
    });
    fireEvent.click(screen.getByRole('button', { name: '验证答案' }));
    await screen.findByText('设置新密码');

    fireEvent.change(screen.getByPlaceholderText('13位以上，含大小写字母、数字和特殊字符'), {
      target: { value: 'ValidPassword123!' },
    });
    fireEvent.change(screen.getByPlaceholderText('请再次输入新密码'), {
      target: { value: 'ValidPassword123!' },
    });
    fireEvent.click(screen.getByRole('button', { name: '重置密码' }));

    await waitFor(() => {
      expect(authAPI.resetPassword).toHaveBeenCalledWith('memory-only-token', 'ValidPassword123!');
      expect(toast.success).toHaveBeenCalledWith('密码重置成功，请重新登录');
      expect(mockNavigate).toHaveBeenCalledWith('/login');
    });
    expect(sessionStorageMock.store.reset_token).toBeUndefined();
  });

  it('step 3 weak password fails zod validation and does not call API', async () => {
    authAPI.startRecovery.mockResolvedValueOnce({ questions: ['问题一？', '问题二？'] });
    authAPI.verifySecurity.mockResolvedValueOnce({ reset_token: 'memory-only-token' });

    renderComponent();

    fireEvent.change(screen.getByPlaceholderText('请输入需要找回的用户名'), {
      target: { value: 'alice' },
    });
    fireEvent.click(screen.getByRole('button', { name: '下一步' }));
    await screen.findByText('问题一？');

    fireEvent.change(screen.getByPlaceholderText('请输入第一个答案'), {
      target: { value: 'a1' },
    });
    fireEvent.change(screen.getByPlaceholderText('请输入第二个答案'), {
      target: { value: 'a2' },
    });
    fireEvent.click(screen.getByRole('button', { name: '验证答案' }));
    await screen.findByText('设置新密码');

    fireEvent.change(screen.getByPlaceholderText('13位以上，含大小写字母、数字和特殊字符'), {
      target: { value: 'weak' },
    });
    fireEvent.change(screen.getByPlaceholderText('请再次输入新密码'), {
      target: { value: 'weak' },
    });
    fireEvent.click(screen.getByRole('button', { name: '重置密码' }));

    await waitFor(() => {
      expect(screen.getByText('密码至少13位')).toBeInTheDocument();
    });
    expect(authAPI.resetPassword).not.toHaveBeenCalled();
    expect(sessionStorageMock.store.reset_token).toBeUndefined();
  });
});
