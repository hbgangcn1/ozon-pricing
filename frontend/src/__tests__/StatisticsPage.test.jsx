import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import StatisticsPage from '../pages/StatisticsPage';

vi.mock('lucide-react', () => ({
  Download: () => null,
  RefreshCw: () => null,
  Search: () => null,
  TrendingUp: () => null,
  Users: () => null,
  DollarSign: () => null,
  Activity: () => null,
  AlertTriangle: () => null,
  Target: () => null,
}));

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, variant, size }) => (
    <button onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className, variant }) => <span className={className}>{children}</span>,
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableCell: ({ children, className }) => <td className={className}>{children}</td>,
  TableHead: ({ children, className }) => <th className={className}>{children}</th>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableRow: ({ children }) => <tr>{children}</tr>,
}));

vi.mock('../components/ui/tabs', () => ({
  Tabs: ({ children, value, onValueChange }) => <div data-active={value}>{children}</div>,
  TabsList: ({ children }) => <div role="tablist">{children}</div>,
  TabsTrigger: ({ children, value, onClick }) => (
    <button role="tab" data-value={value} onClick={onClick}>{children}</button>
  ),
  TabsContent: ({ children, value }) => <div data-tab={value}>{children}</div>,
}));

vi.mock('../components/ui/progress', () => ({
  Progress: ({ value, className }) => <div className={className} data-progress={value} />,
}));

describe('StatisticsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "数据统计" heading', () => {
    render(<StatisticsPage />);
    expect(screen.getByText(/数据统计/)).toBeInTheDocument();
  });

  it('renders tab triggers for all sections', () => {
    render(<StatisticsPage />);
    expect(screen.getAllByText(/总览/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/留存分析/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/用户活跃/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/充值与收入/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/操作日志/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/登录记录/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/异常监控/).length).toBeGreaterThan(0);
  });

  it('overview tab shows key statistics from mock data', () => {
    render(<StatisticsPage />);
    expect(screen.getByText('总用户数')).toBeInTheDocument();
    expect(screen.getAllByText('42').length).toBeGreaterThan(0);
    expect(screen.getByText('活跃用户')).toBeInTheDocument();
    expect(screen.getByText('今日新增')).toBeInTheDocument();
  });

  it('renders retention data percentages', () => {
    render(<StatisticsPage />);
    expect(screen.getAllByText('95%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('88%').length).toBeGreaterThan(0);
    expect(screen.getAllByText('82%').length).toBeGreaterThan(0);
  });

  it('renders admin logs in logs tab content', () => {
    render(<StatisticsPage />);
    expect(screen.getByText('添加物流规则: China Post e邮宝')).toBeInTheDocument();
  });
});
