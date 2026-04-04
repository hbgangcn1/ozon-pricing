import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import AboutPage from '../pages/AboutPage';

vi.mock('lucide-react', () => ({
  Building2: () => null,
}));

describe('AboutPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "关于我们" heading', () => {
    render(<AboutPage />);
    expect(screen.getByText('关于我们')).toBeInTheDocument();
  });

  it('renders company info section with correct labels and values', () => {
    render(<AboutPage />);
    expect(screen.getByText('公司信息')).toBeInTheDocument();
    expect(screen.getByText('公司名称')).toBeInTheDocument();
    expect(screen.getByText('深圳超凡酷玩电子商务有限公司')).toBeInTheDocument();
    expect(screen.getByText('联系电话')).toBeInTheDocument();
    expect(screen.getByText('19328702460')).toBeInTheDocument();
    expect(screen.getByText('办公地址')).toBeInTheDocument();
  });

  it('renders business section with description', () => {
    render(<AboutPage />);
    expect(screen.getByText('业务简介')).toBeInTheDocument();
    expect(screen.getByText(/我们是一家专注于跨境电商服务的公司/)).toBeInTheDocument();
    expect(screen.getByText(/通过智能化的定价系统/)).toBeInTheDocument();
  });
});
