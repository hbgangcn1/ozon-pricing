import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter, useNavigate } from 'react-router-dom';
import TopHeader from '../components/TopHeader';
import { useAuthStore } from '../stores/authStore';

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: vi.fn(),
  };
});

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('TopHeader Component', () => {
  const mockNavigate = vi.fn();
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    useNavigate.mockReturnValue(mockNavigate);
  });

  test('renders system title', () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' }, logout: mockLogout });
    render(
      <MemoryRouter>
        <TopHeader />
      </MemoryRouter>
    );
    expect(screen.getByText('物流定价系统')).toBeInTheDocument();
  });

  test('shows username from authStore', () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' }, logout: mockLogout });
    render(
      <MemoryRouter>
        <TopHeader />
      </MemoryRouter>
    );
    expect(screen.getByText('testuser 欢迎回来！')).toBeInTheDocument();
  });

  test('shows admin badge when user role is admin', () => {
    useAuthStore.mockReturnValue({ user: { username: 'adminuser', role: 'admin' }, logout: mockLogout });
    render(
      <MemoryRouter>
        <TopHeader />
      </MemoryRouter>
    );
    expect(screen.getByText('管理员')).toBeInTheDocument();
  });

  test('does not show admin badge for regular users', () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' }, logout: mockLogout });
    render(
      <MemoryRouter>
        <TopHeader />
      </MemoryRouter>
    );
    expect(screen.queryByText('管理员')).not.toBeInTheDocument();
  });

  test('calls logout and navigates to login on logout button click', () => {
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user' }, logout: mockLogout });
    render(
      <MemoryRouter>
        <TopHeader />
      </MemoryRouter>
    );
    
    const logoutBtn = screen.getByRole('button', { name: /退出/i });
    fireEvent.click(logoutBtn);
    
    expect(mockLogout).toHaveBeenCalledTimes(1);
    expect(mockNavigate).toHaveBeenCalledWith('/login');
  });
});
