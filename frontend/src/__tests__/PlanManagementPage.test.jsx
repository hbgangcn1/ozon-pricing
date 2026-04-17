import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import PlanManagementPage from '../pages/PlanManagementPage';
import { toast } from 'sonner';

const mockPlans = [
  { id: 1, code: 'free', name: '免费版', display_price_month: 0, display_price_year: 0, actual_price_month: 0, actual_price_year: 0, test_price_month: 0, test_price_year: 0, calc_limit: -1, logistics_limit: 1, sort: 1, status: 1, description: '免费', features: ['基础功能'] },
  { id: 2, code: 'efficiency', name: '效率版', display_price_month: 29.9, display_price_year: 299, actual_price_month: 29.9, actual_price_year: 299, test_price_month: 0.01, test_price_year: 0.01, calc_limit: -1, logistics_limit: 5, sort: 2, status: 1, description: '效率', features: ['极速模式'] },
  { id: 3, code: 'pro', name: '专业版', display_price_month: 59.9, display_price_year: 599, actual_price_month: 59.9, actual_price_year: 599, test_price_month: 0.01, test_price_year: 0.01, calc_limit: -1, logistics_limit: -1, sort: 3, status: 1, description: '专业', features: ['无限模板'] },
  { id: 4, code: 'enterprise', name: '企业版', display_price_month: 199, display_price_year: 1999, actual_price_month: 199, actual_price_year: 1999, test_price_month: 0.01, test_price_year: 0.01, calc_limit: -1, logistics_limit: -1, sort: 4, status: 1, description: '企业', features: ['专属服务'] },
];

vi.mock('../services/api', () => ({
  plansAPI: {
    getAll: vi.fn(() => Promise.resolve(mockPlans)),
    create: vi.fn(() => Promise.resolve({})),
    update: vi.fn(() => Promise.resolve({})),
    delete: vi.fn(() => Promise.resolve({})),
    toggleActive: vi.fn(() => Promise.resolve({})),
  },
}));

vi.mock('lucide-react', () => ({
  Edit: () => null,
  Save: () => null,
  X: () => null,
  Check: () => null,
  Plus: () => null,
  List: () => null,
  Settings: () => null,
  Trash2: () => null,
  Power: () => null,
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
  Button: ({ children, onClick, disabled, className, variant, size, type }) => (
    <button type={type} onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className, variant }) => <span className={className}>{children}</span>,
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor }) => <label htmlFor={htmlFor}>{children}</label>,
}));

vi.mock('../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, disabled }) => (
    <input type="checkbox" checked={checked} onChange={(e) => onCheckedChange(e.target.checked)} disabled={disabled} />
  ),
}));

vi.mock('../components/ui/textarea', () => ({
  Textarea: ({ value, onChange, placeholder, rows, className }) => (
    <textarea value={value} onChange={onChange} placeholder={placeholder} rows={rows} className={className} />
  ),
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
    <button type="button" role="tab" data-value={value} onClick={onClick}>{children}</button>
  ),
  TabsContent: ({ children, value }) => <div data-tab={value}>{children}</div>,
}));

vi.mock('../components/ui/alert-dialog', () => ({
  AlertDialog: ({ children, open }) => open ? <div data-testid="alert-dialog">{children}</div> : null,
  AlertDialogContent: ({ children }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }) => <h3>{children}</h3>,
  AlertDialogDescription: ({ children }) => <p>{children}</p>,
  AlertDialogFooter: ({ children }) => <div>{children}</div>,
  AlertDialogAction: ({ children, onClick }) => <button type="button" onClick={onClick}>{children}</button>,
  AlertDialogCancel: ({ children, onClick }) => <button type="button" onClick={onClick}>{children}</button>,
}));

describe('PlanManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "套餐管理" heading', () => {
    render(<PlanManagementPage />);
    expect(screen.getByText(/套餐管理/)).toBeInTheDocument();
  });

  it('renders all 4 plan cards in list tab', async () => {
    render(<PlanManagementPage />);
    await waitFor(() => {
      expect(screen.getByText('免费版')).toBeInTheDocument();
    });
    expect(screen.getByText('效率版')).toBeInTheDocument();
    expect(screen.getByText('专业版')).toBeInTheDocument();
    expect(screen.getByText('企业版')).toBeInTheDocument();
  });

  it('shows edit form when edit button is clicked', async () => {
    render(<PlanManagementPage />);
    await waitFor(() => {
      expect(screen.getByText('免费版')).toBeInTheDocument();
    });
    const editButtons = screen.getAllByText(/编辑/);
    fireEvent.click(editButtons[0]);
    expect(screen.getByText(/编辑套餐:/)).toBeInTheDocument();
  });

  it('cancels edit and returns to plan card view', async () => {
    render(<PlanManagementPage />);
    await waitFor(() => {
      expect(screen.getByText('免费版')).toBeInTheDocument();
    });
    const editButtons = screen.getAllByText(/编辑/);
    fireEvent.click(editButtons[0]);
    expect(screen.getByText(/编辑套餐:/)).toBeInTheDocument();
    const cancelButtons = screen.getAllByText(/取消/);
    fireEvent.click(cancelButtons[0]);
    expect(screen.queryByText(/编辑套餐:/)).not.toBeInTheDocument();
  });

  it('saves plan changes and shows success toast', async () => {
    render(<PlanManagementPage />);
    await waitFor(() => {
      expect(screen.getByText('免费版')).toBeInTheDocument();
    });
    const editButtons = screen.getAllByText(/编辑/);
    fireEvent.click(editButtons[0]);
    const saveButtons = screen.getAllByText(/保存/);
    fireEvent.click(saveButtons[0]);
    await waitFor(() => {
      expect(toast.success).toHaveBeenCalledWith('保存成功');
    });
  });

  it('renders "新增套餐" tab trigger', () => {
    render(<PlanManagementPage />);
    expect(screen.getAllByText(/新增套餐/).length).toBeGreaterThan(0);
  });

  it('displays prices with 2 decimal places in edit form', async () => {
    render(<PlanManagementPage />);
    await waitFor(() => {
      expect(screen.getByText('效率版')).toBeInTheDocument();
    });
    // Click edit on 效率版 (second plan)
    const editButtons = screen.getAllByText(/编辑/);
    fireEvent.click(editButtons[1]);
    // Check that price inputs show 2 decimal places
    const priceInputs = screen.getAllByDisplayValue('29.90');
    expect(priceInputs.length).toBeGreaterThan(0);
  });
});
