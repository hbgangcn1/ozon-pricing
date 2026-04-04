import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import SettingsPage from '../pages/SettingsPage';
import { settingsAPI, logoutUser } from '../services/api';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  settingsAPI: {
    get: vi.fn(),
    updateOpenRegistration: vi.fn(),
    getBackups: vi.fn(),
    createBackup: vi.fn(),
    getBackupSettings: vi.fn(),
    getBackupStats: vi.fn(),
    deleteBackup: vi.fn(),
    restoreBackup: vi.fn(),
    downloadBackup: vi.fn(),
  },
  logoutUser: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    loading: vi.fn(() => 'toast-id'),
    dismiss: vi.fn(),
    info: vi.fn(),
  },
}));

vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children }) => <h2>{children}</h2>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, type }) => (
    <button onClick={onClick} disabled={disabled} className={className} type={type}>{children}</button>
  ),
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input {...props} />,
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className }) => <span className={className}>{children}</span>,
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableCell: ({ children, className }) => <td className={className}>{children}</td>,
  TableHead: ({ children, className }) => <th className={className}>{children}</th>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableRow: ({ children, className }) => <tr className={className}>{children}</tr>,
}));

vi.mock('../components/ui/tabs', () => ({
  Tabs: ({ children, defaultValue }) => <div data-default={defaultValue}>{children}</div>,
  TabsList: ({ children, className }) => <div className={className}>{children}</div>,
  TabsTrigger: ({ children, value }) => <button data-value={value}>{children}</button>,
  TabsContent: ({ children, value }) => <div data-value={value}>{children}</div>,
}));

vi.mock('../components/ui/switch', () => ({
  Switch: ({ checked, onCheckedChange, disabled }) => (
    <input
      type="checkbox"
      checked={checked}
      disabled={disabled}
      onChange={(e) => onCheckedChange && onCheckedChange(e.target.checked)}
      data-testid="switch"
    />
  ),
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor, className }) => <label htmlFor={htmlFor} className={className}>{children}</label>,
}));

vi.mock('../components/ui/alert-dialog', () => ({
  AlertDialog: ({ children, open }) => open ? <div>{children}</div> : null,
  AlertDialogContent: ({ children }) => <div>{children}</div>,
  AlertDialogHeader: ({ children }) => <div>{children}</div>,
  AlertDialogTitle: ({ children }) => <h2>{children}</h2>,
  AlertDialogDescription: ({ children }) => <p>{children}</p>,
  AlertDialogFooter: ({ children }) => <div>{children}</div>,
  AlertDialogAction: ({ children, onClick, className, disabled }) => (
    <button onClick={onClick} className={className} disabled={disabled}>{children}</button>
  ),
  AlertDialogCancel: ({ children, disabled }) => <button disabled={disabled}>{children}</button>,
}));

vi.mock('lucide-react', () => ({
  Download: () => null, RefreshCw: () => null, Settings: () => null, FolderOpen: () => null,
  Info: () => null, ChevronDown: () => null, Clock: () => null, HardDrive: () => null,
  Database: () => null, Trash2: () => null, PlayCircle: () => null, Loader2: () => null,
  AlertTriangle: () => null, Check: () => null, X: () => null, ChevronRight: () => null,
}));

const defaultSettings = { open_registration: true };
const defaultBackupSettings = { enabled: true, interval_hours: 6, max_backups: 28, next_backup: null };
const defaultBackupStats = { count: 3, total_size_mb: 10 };

describe('SettingsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    settingsAPI.get.mockResolvedValue(defaultSettings);
    settingsAPI.getBackups.mockResolvedValue([]);
    settingsAPI.getBackupSettings.mockResolvedValue(defaultBackupSettings);
    settingsAPI.getBackupStats.mockResolvedValue(defaultBackupStats);
  });

  it('renders settings page heading', async () => {
    render(<SettingsPage />);
    expect(screen.getByText(/系统设置/)).toBeInTheDocument();
  });

  it('renders system config section with open registration switch', async () => {
    render(<SettingsPage />);
    expect(screen.getByText('开放注册')).toBeInTheDocument();
    expect(screen.getByText('开启后，新用户可以自行注册账号')).toBeInTheDocument();
  });

  it('renders backup management section', async () => {
    render(<SettingsPage />);
    expect(screen.getByText(/数据库备份管理/)).toBeInTheDocument();
  });

  it('calls settingsAPI.get on mount and loads open_registration state', async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(settingsAPI.get).toHaveBeenCalled();
    });
  });

  it('loads backup list and settings on mount', async () => {
    render(<SettingsPage />);
    await waitFor(() => {
      expect(settingsAPI.getBackups).toHaveBeenCalled();
      expect(settingsAPI.getBackupSettings).toHaveBeenCalled();
      expect(settingsAPI.getBackupStats).toHaveBeenCalled();
    });
  });

  it('shows empty backup message when no backups', async () => {
    settingsAPI.getBackups.mockResolvedValue([]);
    render(<SettingsPage />);
    await waitFor(() => {
      expect(screen.getByText('暂无备份文件')).toBeInTheDocument();
    });
  });

  it('updates open registration and shows success toast', async () => {
    settingsAPI.updateOpenRegistration.mockResolvedValue({});
    render(<SettingsPage />);

    await waitFor(() => {
      expect(settingsAPI.get).toHaveBeenCalled();
    });

    const switches = screen.getAllByTestId('switch');
    fireEvent.click(switches[0]);

    await waitFor(() => {
      expect(settingsAPI.updateOpenRegistration).toHaveBeenCalled();
      expect(toast.success).toHaveBeenCalledWith('设置已更新');
    });
  });

  it('shows error toast when open registration update fails', async () => {
    settingsAPI.updateOpenRegistration.mockRejectedValue({ response: { data: { message: '更新失败' } } });
    render(<SettingsPage />);

    const switches = screen.getAllByTestId('switch');
    fireEvent.click(switches[0]);

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(expect.stringContaining('更新失败'));
    });
  });

  it('renders FAQ section', async () => {
    render(<SettingsPage />);
    expect(screen.getByText(/常见问题/)).toBeInTheDocument();
    expect(screen.getByText('备份文件格式是什么？')).toBeInTheDocument();
  });

  it('expands FAQ item when clicked', async () => {
    render(<SettingsPage />);
    const faqBtn = screen.getByText('备份文件格式是什么？');
    fireEvent.click(faqBtn);
    await waitFor(() => {
      expect(screen.getByText(/标准导出格式/)).toBeInTheDocument();
    });
  });
});
