import React from 'react';
import { render, screen } from '@testing-library/react';
import { vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import Sidebar from '../components/Sidebar';
import { useAuthStore } from '@/stores/authStore';
import apiClient from '@/services/api';

vi.mock('@/stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('@/services/api', () => ({
  default: {
    get: vi.fn(),
  },
}));

vi.mock('@/lib/utils', () => ({
  cn: (...args) => args.filter(Boolean).join(' '),
}));

describe('Sidebar Component', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiClient.get.mockResolvedValue({
      'RUB/CNY': 0.1,
      'CNY/RUB': 10,
      'USD/CNY': 7,
      'CNY/USD': 0.14,
    });
  });

  test('renders correct menu items based on admin role', () => {
    useAuthStore.mockReturnValue({ isAdmin: () => true });
    render(
      <MemoryRouter initialEntries={['/pricing']}>
        <Sidebar />
      </MemoryRouter>
    );
    const titleElems = screen.getAllByText('物流定价');
    expect(titleElems.length).toBeGreaterThan(0);
    expect(screen.getByText('系统设置')).toBeInTheDocument();
  });

  test('renders correct menu items based on user role', () => {
    useAuthStore.mockReturnValue({ isAdmin: () => false });
    render(
      <MemoryRouter initialEntries={['/pricing']}>
        <Sidebar />
      </MemoryRouter>
    );
    const titleElems = screen.getAllByText('物流定价');
    expect(titleElems.length).toBeGreaterThan(0);
    expect(screen.queryByText('系统设置')).not.toBeInTheDocument();
  });

  test('ExchangeRatePanel displays rates directly', async () => {
    useAuthStore.mockReturnValue({ isAdmin: () => false });
    render(
      <MemoryRouter initialEntries={['/pricing']}>
        <Sidebar />
      </MemoryRouter>
    );
    
    expect(apiClient.get).toHaveBeenCalledWith('/exchange/rates', expect.any(Object));
    
    const rateText = await screen.findByText('RUB/CNY');
    expect(rateText).toBeInTheDocument();
    expect(screen.getByText('实时汇率')).toBeInTheDocument();
  });

  test('sidebar is always expanded with fixed width', () => {
    useAuthStore.mockReturnValue({ isAdmin: () => false });
    const { container } = render(
      <MemoryRouter initialEntries={['/pricing']}>
        <Sidebar />
      </MemoryRouter>
    );
    
    const titleElems = screen.getAllByText('物流定价');
    expect(titleElems.length).toBe(2);
    expect(screen.queryByText('收起')).not.toBeInTheDocument();
    
    const sidebar = container.firstChild;
    expect(sidebar.className).toContain('w-64');
  });

  test('active item highlighted based on location', () => {
    useAuthStore.mockReturnValue({ isAdmin: () => true });
    render(
      <MemoryRouter initialEntries={['/logistics']}>
        <Sidebar />
      </MemoryRouter>
    );
    
    const activeLink = screen.getByText('物流管理').closest('a');
    expect(activeLink.className).toContain('border-primary');
  });
});
