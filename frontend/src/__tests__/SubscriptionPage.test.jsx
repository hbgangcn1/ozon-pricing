import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import SubscriptionPage from '../pages/SubscriptionPage';

vi.mock('lucide-react', () => ({
  Crown: () => null,
  CheckCircle: () => null,
  ArrowUp: () => null,
  Info: () => null,
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, variant }) => (
    <button onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className, variant }) => <span className={className}>{children}</span>,
}));

import { useAuthStore } from '../stores/authStore';

describe('SubscriptionPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.mockReturnValue({ user: { username: 'testuser', role: 'user', user_type: 'free' } });
  });

  it('renders "订阅管理" heading', async () => {
    render(<SubscriptionPage />);
    await waitFor(() => {
      expect(screen.getByText(/订阅管理/)).toBeInTheDocument();
    });
  });

  it('renders current plan section', async () => {
    render(<SubscriptionPage />);
    await waitFor(() => {
      expect(screen.getAllByText(/当前套餐/).length).toBeGreaterThan(0);
    });
  });

  it('renders plan comparison section with all 4 plans', async () => {
    render(<SubscriptionPage />);
    await waitFor(() => {
      expect(screen.getAllByText(/套餐对比/).length).toBeGreaterThan(0);
      expect(screen.getAllByText('免费版').length).toBeGreaterThan(0);
      expect(screen.getAllByText('效率版').length).toBeGreaterThan(0);
      expect(screen.getAllByText('专业版').length).toBeGreaterThan(0);
      expect(screen.getAllByText('企业版').length).toBeGreaterThan(0);
    });
  });

  it('shows admin plan label for admin users', async () => {
    useAuthStore.mockReturnValue({ user: { username: 'admin', role: 'admin', user_type: 'free' } });
    render(<SubscriptionPage />);
    await waitFor(() => {
      expect(screen.getByText('管理员')).toBeInTheDocument();
    });
  });

  it('shows free plan name for free user', async () => {
    render(<SubscriptionPage />);
    await waitFor(() => {
      expect(screen.getAllByText('免费版').length).toBeGreaterThan(0);
    });
  });
});
