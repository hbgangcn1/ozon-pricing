import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import PlanManagementPage from '../pages/PlanManagementPage';
import { toast } from 'sonner';

vi.mock('lucide-react', () => ({
  Edit: () => null,
  Save: () => null,
  X: () => null,
  Check: () => null,
  Plus: () => null,
  List: () => null,
  Settings: () => null,
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
    <button role="tab" data-value={value} onClick={onClick}>{children}</button>
  ),
  TabsContent: ({ children, value }) => <div data-tab={value}>{children}</div>,
}));

describe('PlanManagementPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders "套餐管理" heading', () => {
    render(<PlanManagementPage />);
    expect(screen.getByText(/套餐管理/)).toBeInTheDocument();
  });

  it('renders all 4 plan cards in list tab', () => {
    render(<PlanManagementPage />);
    expect(screen.getByText('免费版')).toBeInTheDocument();
    expect(screen.getByText('效率版')).toBeInTheDocument();
    expect(screen.getByText('专业版')).toBeInTheDocument();
    expect(screen.getByText('企业版')).toBeInTheDocument();
  });

  it('shows edit form when edit button is clicked', () => {
    render(<PlanManagementPage />);
    const editButtons = screen.getAllByText(/编辑/);
    fireEvent.click(editButtons[0]);
    expect(screen.getByText(/编辑套餐:/)).toBeInTheDocument();
  });

  it('cancels edit and returns to plan card view', () => {
    render(<PlanManagementPage />);
    const editButtons = screen.getAllByText(/编辑/);
    fireEvent.click(editButtons[0]);
    expect(screen.getByText(/编辑套餐:/)).toBeInTheDocument();
    fireEvent.click(screen.getByText(/取消/));
    expect(screen.queryByText(/编辑套餐:/)).not.toBeInTheDocument();
  });

  it('saves plan changes and shows success toast', () => {
    render(<PlanManagementPage />);
    const editButtons = screen.getAllByText(/编辑/);
    fireEvent.click(editButtons[0]);
    fireEvent.click(screen.getByText(/保存/));
    expect(toast.success).toHaveBeenCalledWith('保存成功');
    expect(screen.queryByText(/编辑套餐:/)).not.toBeInTheDocument();
  });

  it('renders "新增套餐" tab trigger', () => {
    render(<PlanManagementPage />);
    expect(screen.getAllByText(/新增套餐/).length).toBeGreaterThan(0);
  });
});
