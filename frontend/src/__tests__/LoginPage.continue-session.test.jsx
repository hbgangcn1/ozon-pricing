import React from 'react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter } from 'react-router-dom';
import LoginPage from '../pages/LoginPage';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock('sonner', () => ({
  toast: { error: vi.fn(), success: vi.fn(), info: vi.fn() },
}));

const mockLogout = vi.fn();
vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(() => ({
    setAuth: vi.fn(),
    isAuthenticated: true,
    user: { id: 1, username: 'alice', role: 'user' },
    logout: mockLogout,
  })),
}));

vi.mock('../services/api', () => ({
  authAPI: {
    getMe: vi.fn(),
    login: vi.fn(),
  },
  settingsAPI: {
    get: vi.fn().mockResolvedValue({ open_registration: true }),
  },
}));

import { authAPI } from '../services/api';
import { toast } from 'sonner';

beforeEach(() => {
  vi.clearAllMocks();
});

function renderAt(path = '/login?returnTo=%2Fpricing') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <LoginPage />
    </MemoryRouter>
  );
}

describe('LoginPage continue session', () => {
  it('getMe success navigates to returnTo', async () => {
    authAPI.getMe.mockResolvedValueOnce({ id: 1, username: 'alice' });

    renderAt('/login?returnTo=%2Fsettings');

    await userEvent.click(screen.getByRole('button', { name: /继续使用/ }));

    await waitFor(() => {
      expect(authAPI.getMe).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith('/settings', { replace: true });
    });
  });

  it('getMe success with no returnTo navigates to /pricing', async () => {
    authAPI.getMe.mockResolvedValueOnce({ id: 1, username: 'alice' });

    renderAt('/login');

    await userEvent.click(screen.getByRole('button', { name: /继续使用/ }));

    await waitFor(() => {
      expect(authAPI.getMe).toHaveBeenCalledTimes(1);
      expect(mockNavigate).toHaveBeenCalledWith('/pricing', { replace: true });
    });
  });

  it("getMe 401 logs out and shows expired toast", async () => {
    authAPI.getMe.mockRejectedValueOnce({ response: { status: 401 } });

    renderAt();

    await userEvent.click(screen.getByRole('button', { name: /继续使用/ }));

    await waitFor(() => {
      expect(mockLogout).toHaveBeenCalledTimes(1);
      expect(toast.error).toHaveBeenCalledWith('登录已失效,请重新登录');
    });
    expect(mockNavigate).not.toHaveBeenCalled();
  });

  it('getMe network error shows retry toast without logout or navigation', async () => {
    authAPI.getMe.mockRejectedValueOnce(new Error('Network Error'));

    renderAt();

    await userEvent.click(screen.getByRole('button', { name: /继续使用/ }));

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith('网络错误,请重试');
    });
    expect(mockLogout).not.toHaveBeenCalled();
    expect(mockNavigate).not.toHaveBeenCalled();
  });
});
