import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import SideMenu from '../components/SideMenu';
import { useAuthStore } from '../stores/authStore';
import apiClient from '../services/api';

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

const mockNavigate = vi.fn();

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom');
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useLocation: () => ({ pathname: '/pricing' }),
  };
});

describe('SideMenu Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.get.mockResolvedValue({
      'RUB/CNY': 0.1,
      'CNY/RUB': 10,
      'USD/CNY': 7,
      'CNY/USD': 0.14,
    });
  });

  test('renders all admin menu items when user is admin', async () => {
    useAuthStore.mockReturnValue({ user: { role: 'admin' } });
    render(
      <MemoryRouter>
        <SideMenu />
      </MemoryRouter>
    );
    
    expect(screen.getByText('💰 定价计算')).toBeInTheDocument();
    expect(screen.getByText('⚙️ 系统设置')).toBeInTheDocument();
    expect(screen.getByText('👥 用户管理')).toBeInTheDocument();
  });

  test('renders only user menu items when user is regular user', async () => {
    useAuthStore.mockReturnValue({ user: { role: 'user' } });
    render(
      <MemoryRouter>
        <SideMenu />
      </MemoryRouter>
    );
    
    expect(screen.getByText('💰 定价计算')).toBeInTheDocument();
    expect(screen.queryByText('⚙️ 系统设置')).not.toBeInTheDocument();
    expect(screen.queryByText('👥 用户管理')).not.toBeInTheDocument();
  });

  test('calls navigate on menu item click', async () => {
    useAuthStore.mockReturnValue({ user: { role: 'user' } });
    render(
      <MemoryRouter>
        <SideMenu />
      </MemoryRouter>
    );
    
    const menuItem = screen.getByText('💰 定价计算');
    fireEvent.click(menuItem);
    
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/pricing');
    });
  });

  test('ExchangeRateWidget renders and fetches data', async () => {
    useAuthStore.mockReturnValue({ user: { role: 'user' } });
    render(
      <MemoryRouter>
        <SideMenu />
      </MemoryRouter>
    );
    
    expect(apiClient.get).toHaveBeenCalledWith('/exchange/rates');
    await waitFor(() => {
      expect(screen.getByText('RUB/CNY')).toBeInTheDocument();
    });
  });

  test('toggle collapse button works', async () => {
    useAuthStore.mockReturnValue({ user: { role: 'user' } });
    const { container } = render(
      <MemoryRouter>
        <SideMenu />
      </MemoryRouter>
    );
    
    expect(screen.getByText('📦 物流定价')).toBeInTheDocument();
    
    const toggleBtn = container.querySelector('.anticon-menu-fold');
    if (toggleBtn) {
      fireEvent.click(toggleBtn.parentElement);
      expect(screen.getByText('📦')).toBeInTheDocument();
    }
  });
});
