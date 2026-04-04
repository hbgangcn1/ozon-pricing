import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PaymentPage from '../pages/PaymentPage';
import { toast } from 'sonner';

vi.mock('lucide-react', () => ({
  Download: () => null,
  Search: () => null,
  Maximize2: () => null,
  RefreshCw: () => null,
  Info: () => null,
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() },
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

describe('PaymentPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    global.URL.createObjectURL = vi.fn(() => 'blob:mock');
    global.URL.revokeObjectURL = vi.fn();
  });

  it('renders "支付与订单管理" heading', () => {
    render(<PaymentPage />);
    expect(screen.getByText(/支付与订单管理/)).toBeInTheDocument();
  });

  it('renders order table with all 10 mock orders on page 1', () => {
    render(<PaymentPage />);
    expect(screen.getByText('ORD20260322001')).toBeInTheDocument();
    expect(screen.getByText('ORD20260215001')).toBeInTheDocument();
    const statusBadges = screen.getAllByText('已支付');
    expect(statusBadges.length).toBeGreaterThan(0);
  });

  it('renders pagination info showing total records', () => {
    render(<PaymentPage />);
    expect(screen.getByText(/共 10 条记录/)).toBeInTheDocument();
  });

  it('filters orders by search text', () => {
    render(<PaymentPage />);
    const searchInput = screen.getByPlaceholderText('搜索订单号或套餐');
    fireEvent.change(searchInput, { target: { value: '专业版' } });
    expect(screen.getByText('ORD20260322001')).toBeInTheDocument();
    expect(screen.queryByText('ORD20260321001')).not.toBeInTheDocument();
  });

  it('CSV export button triggers export and shows success toast', () => {
    render(<PaymentPage />);
    const exportButton = screen.getByText(/导出CSV/);
    expect(exportButton).toBeInTheDocument();
    const mockAnchor = { href: '', download: '', click: vi.fn() };
    vi.spyOn(document, 'createElement').mockReturnValueOnce(mockAnchor);
    fireEvent.click(exportButton);
    expect(toast.success).toHaveBeenCalledWith('导出成功');
  });

  it('info notice renders navigation hint text', () => {
    render(<PaymentPage />);
    expect(screen.getByText(/如需订阅或升级套餐/)).toBeInTheDocument();
  });
});
