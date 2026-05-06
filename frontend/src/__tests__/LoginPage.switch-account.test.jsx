import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn() }
}));

const mockLogout = vi.fn();
vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({
    setAuth: vi.fn(),
    isAuthenticated: true,
    user: { id: 1, username: 'alice', role: 'user' },
    logout: mockLogout,
  }))
}));

vi.mock('../services/api', () => ({
  authAPI: { login: vi.fn(), getMe: vi.fn() },
  settingsAPI: { get: vi.fn().mockResolvedValue({ open_registration: true }) }
}));

beforeEach(() => { vi.clearAllMocks(); });

describe('LoginPage switch account', () => {
  const renderComponent = () => render(
    <MemoryRouter initialEntries={['/login']}>
      <LoginPage />
    </MemoryRouter>
  );

  it('clicking 切换账号 calls logout', async () => {
    const user = userEvent.setup();
    renderComponent();

    await user.click(screen.getByRole('button', { name: /切换账号/ }));

    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('shows 已登录为 alice greeting before clicking', () => {
    renderComponent();

    expect(screen.getByText(/已登录为\s*alice/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /继续使用/ })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /切换账号/ })).toBeInTheDocument();
    expect(screen.queryByPlaceholderText('请输入用户名')).not.toBeInTheDocument();
  });
});
