import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import DashboardPage from '../pages/DashboardPage';
import { productsAPI, logisticsAPI } from '../services/api';

vi.mock('../services/api', () => ({
  productsAPI: {
    getAll: vi.fn(),
  },
  logisticsAPI: {
    getAll: vi.fn(),
  },
}));

vi.mock('../components/ui/skeleton', () => ({
  Skeleton: ({ className }) => <div data-testid="skeleton" className={className} />,
}));

describe('DashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter>
        <DashboardPage />
      </MemoryRouter>
    );
  };

  it('renders "系统概览" heading', () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    logisticsAPI.getAll.mockResolvedValueOnce([]);
    
    renderComponent();
    expect(screen.getByText('系统概览')).toBeInTheDocument();
  });

  it('shows loading skeletons initially', () => {
    let resolveProducts;
    const productsPromise = new Promise(resolve => {
      resolveProducts = resolve;
    });
    
    let resolveLogistics;
    const logisticsPromise = new Promise(resolve => {
      resolveLogistics = resolve;
    });
    
    productsAPI.getAll.mockReturnValue(productsPromise);
    logisticsAPI.getAll.mockReturnValue(logisticsPromise);
    
    renderComponent();
    
    expect(screen.getAllByTestId('skeleton')).toHaveLength(6);
    
    resolveProducts([]);
    resolveLogistics([]);
  });

  it('displays product count and logistics count after data loads', async () => {
    productsAPI.getAll.mockResolvedValueOnce([{}, {}, {}]);
    logisticsAPI.getAll.mockResolvedValueOnce([{}, {}]);
    
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('3')).toBeInTheDocument();
      expect(screen.getByText('2')).toBeInTheDocument();
    });
    
    expect(screen.queryByTestId('skeleton')).not.toBeInTheDocument();
  });

  it('shows "用户角色" as "管理员" and "系统状态" as "正常"', async () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    logisticsAPI.getAll.mockResolvedValueOnce([]);
    
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('管理员')).toBeInTheDocument();
      expect(screen.getAllByText('正常').length).toBeGreaterThan(0);
    });
  });

  it('shows trend badges ("稳定", "正常")', async () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    logisticsAPI.getAll.mockResolvedValueOnce([]);
    
    renderComponent();
    
    await waitFor(() => {
      const stableBadges = screen.getAllByText('稳定');
      expect(stableBadges).toHaveLength(2);
      
      const normalBadges = screen.getAllByText('正常');
      expect(normalBadges.length).toBeGreaterThanOrEqual(2);
    });
  });

  it('handles API error gracefully', async () => {
    productsAPI.getAll.mockRejectedValueOnce(new Error('Network error'));
    logisticsAPI.getAll.mockResolvedValueOnce([]);
    
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getAllByText('0').length).toBeGreaterThan(0);
      expect(screen.queryByTestId('skeleton')).not.toBeInTheDocument();
    });
  });
});
