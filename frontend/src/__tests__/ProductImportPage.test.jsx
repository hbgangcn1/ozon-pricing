import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import ProductImportPage from '../pages/ProductImportPage';
import { productImportAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  productImportAPI: {
    preview: vi.fn(),
    confirm: vi.fn(),
  },
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

// Mock UI components
vi.mock('../components/ui/card', () => ({
  Card: ({ children, className }) => <div className={className}>{children}</div>,
  CardHeader: ({ children, className }) => <div className={className}>{children}</div>,
  CardTitle: ({ children, className }) => <div className={className}>{children}</div>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className, variant }) => (
    <button type="button" onClick={onClick} disabled={disabled} className={className} data-variant={variant}>{children}</button>
  ),
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor, className }) => <label htmlFor={htmlFor} className={className}>{children}</label>,
}));

vi.mock('../components/ui/select', () => ({
  Select: ({ children, value, onValueChange }) => (
    <select data-testid="mock-select" value={value} onChange={(e) => onValueChange(e.target.value)}>
      {children}
    </select>
  ),
  SelectTrigger: ({ children }) => <>{children}</>,
  SelectValue: ({ placeholder }) => <option value="none" disabled>{placeholder}</option>,
  SelectContent: ({ children }) => <>{children}</>,
  SelectItem: ({ children, value }) => <option value={value}>{children}</option>,
}));

vi.mock('../components/ui/radio-group', () => ({
  RadioGroup: ({ children, value, onValueChange }) => (
    <div data-testid="mock-radio-group" value={value} onChange={(e) => onValueChange(e.target.value)}>
      {children}
    </div>
  ),
  RadioGroupItem: ({ value, id }) => (
    <input type="radio" id={id} value={value} name="duplicate-behavior" />
  ),
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableRow: ({ children }) => <tr>{children}</tr>,
  TableHead: ({ children, className }) => <th className={className}>{children}</th>,
  TableCell: ({ children, className }) => <td className={className}>{children}</td>,
}));

const mockPreviewData = {
  columns: ['产品名称', '重量', '长', '宽', '高'],
  preview_rows: [
    { '产品名称': '测试产品 A', '重量': 500, '长': 10, '宽': 10, '高': 10 },
    { '产品名称': '测试产品 B', '重量': 300, '长': 5, '宽': 5, '高': 5 },
  ]
};

const mockLargePreviewData = {
  columns: ['name', 'weight_g', 'length_cm', 'width_cm', 'height_cm'],
  preview_rows: Array.from({ length: 12 }, (_, index) => ({
    name: `Product ${index + 1}`,
    weight_g: 100 + index,
    length_cm: 10,
    width_cm: 5,
    height_cm: 3,
  })),
};

describe('ProductImportPage', () => {
  const makeStore = (subscriptionType = 'enterprise') => ({
    user: { subscription_type: subscriptionType },
    hasEnterpriseAccess: () => ['enterprise', 'gratitude', 'test'].includes(subscriptionType),
  })

  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.mockReturnValue(makeStore('enterprise'));
  });

  it('renders step 1 correctly', () => {
    render(<ProductImportPage />);
    
    expect(screen.getByText('产品批量导入')).toBeInTheDocument();
    expect(screen.getByText('上传产品数据表')).toBeInTheDocument();
    expect(screen.getByText('选择 Excel 文件')).toBeInTheDocument();
  });

  it('handles file upload and transitions to step 2', async () => {
    productImportAPI.preview.mockResolvedValue(mockPreviewData);
    
    render(<ProductImportPage />);
    
    const file = new File(['dummy content'], 'products.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const input = document.querySelector('input[type="file"]');
    
    fireEvent.change(input, { target: { files: [file] } });
    
    expect(screen.getByText('正在解析文件...')).toBeInTheDocument();
    
    await waitFor(() => {
      expect(productImportAPI.preview).toHaveBeenCalledTimes(1);
      expect(toast.success).toHaveBeenCalledWith('文件解析成功，请确认列映射');
    });
    
    // Step 2 assertions
    expect(screen.getByText('字段映射')).toBeInTheDocument();
    expect(screen.getByText('数据预览 (前 2 行)')).toBeInTheDocument();
    
    // Check preview data rendered
    expect(screen.getByText('测试产品 A')).toBeInTheDocument();
    expect(screen.getByText('测试产品 B')).toBeInTheDocument();
  });

  it('removes currency field mapping option and shows total count while previewing first rows only', async () => {
    productImportAPI.preview.mockResolvedValue(mockLargePreviewData);

    render(<ProductImportPage />);

    const file = new File(['dummy content'], 'products.xlsx');
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('字段映射')).toBeInTheDocument();
    });

    expect(screen.queryByText('货币 (CNY/RUB)')).not.toBeInTheDocument();
    expect(screen.getByText('数据预览 (前 10 行)')).toBeInTheDocument();
    expect(screen.getByText('共 12 条数据')).toBeInTheDocument();
    expect(screen.getByText('Product 10')).toBeInTheDocument();
    expect(screen.queryByText('Product 11')).not.toBeInTheDocument();
    expect(screen.queryByText('Product 12')).not.toBeInTheDocument();
  });

  it('handles API error during file upload', async () => {
    productImportAPI.preview.mockRejectedValue(new Error('Parse error'));
    
    render(<ProductImportPage />);
    
    const file = new File(['dummy content'], 'products.xlsx');
    const input = document.querySelector('input[type="file"]');
    
    fireEvent.change(input, { target: { files: [file] } });
    
    await waitFor(() => {
      expect(productImportAPI.preview).toHaveBeenCalledTimes(1);
      expect(toast.error).toHaveBeenCalledWith('文件解析失败，请检查文件格式');
    });
    
    // Should still be on step 1
    expect(screen.getByText('上传产品数据表')).toBeInTheDocument();
  });

  it('validates required mapping before confirming import', async () => {
    productImportAPI.preview.mockResolvedValue({
      columns: ['NameX', 'WeightX'],
      preview_rows: [{ 'NameX': 'Product 1', 'WeightX': 100 }]
    }); // No automatic mapping for 'name' because column names don't match
    
    render(<ProductImportPage />);
    
    // Upload file
    const file = new File(['dummy content'], 'products.xlsx');
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [file] } });
    
    await waitFor(() => {
      expect(screen.getByText('字段映射')).toBeInTheDocument();
    });
    
    // Try to confirm without mapping the name column
    fireEvent.click(screen.getByText('开始导入'));
    
    expect(toast.error).toHaveBeenCalledWith('必须映射"产品名称"列');
    expect(productImportAPI.confirm).not.toHaveBeenCalled();
  });

  it('confirms import and transitions to step 3', async () => {
    // 1. Upload file
    productImportAPI.preview.mockResolvedValue(mockPreviewData);
    
    render(<ProductImportPage />);
    
    const file = new File(['dummy content'], 'products.xlsx');
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [file] } });
    
    await waitFor(() => {
      expect(screen.getByText('字段映射')).toBeInTheDocument();
    });
    
    // 2. Change duplicate handling (using mock radio group input)
    const radioOverwrite = screen.getByDisplayValue('overwrite');
    fireEvent.click(radioOverwrite);
    
    // 3. Confirm import
    productImportAPI.confirm.mockResolvedValue({
      imported: 5,
      skipped: 1,
      overwritten: 2,
      errors: 0
    });
    
    fireEvent.click(screen.getByText('开始导入'));
    
    await waitFor(() => {
      expect(productImportAPI.confirm).toHaveBeenCalledTimes(1);
      expect(productImportAPI.confirm).toHaveBeenCalledWith(expect.objectContaining({
        rows: expect.any(Array),
        conflict_action: expect.any(String),
      }));
      expect(toast.success).toHaveBeenCalledWith('导入完成');
    });
    
    // 4. Verify step 3
    expect(screen.getByText('导入处理完成')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument(); // imported
    expect(screen.getByText('1')).toBeInTheDocument(); // skipped
    expect(screen.getByText('2')).toBeInTheDocument(); // overwritten
    expect(screen.getByText('0')).toBeInTheDocument(); // errors
  });

  it('sends all preview rows on confirm even when table only shows first rows', async () => {
    productImportAPI.preview.mockResolvedValue(mockLargePreviewData);
    productImportAPI.confirm.mockResolvedValue({
      imported: 12,
      skipped: 0,
      overwritten: 0,
      errors: 0,
    });

    render(<ProductImportPage />);

    const file = new File(['dummy content'], 'products.xlsx');
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText('字段映射')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByText('开始导入'));

    await waitFor(() => {
      expect(productImportAPI.confirm).toHaveBeenCalledWith(expect.objectContaining({
        rows: mockLargePreviewData.preview_rows,
      }));
    });
  });

  it('allows resetting from step 3 back to step 1', async () => {
    productImportAPI.preview.mockResolvedValue(mockPreviewData);
    productImportAPI.confirm.mockResolvedValue({ imported: 5 });
    
    render(<ProductImportPage />);
    
    // Go to step 3
    const input = document.querySelector('input[type="file"]');
    fireEvent.change(input, { target: { files: [new File([''], 'file.xlsx')] } });
    await waitFor(() => expect(screen.getByText('开始导入')).toBeInTheDocument());
    fireEvent.click(screen.getByText('开始导入'));
    await waitFor(() => expect(screen.getByText('继续导入')).toBeInTheDocument());
    
    // Reset
    fireEvent.click(screen.getByText('继续导入'));
    
    expect(screen.getByText('上传产品数据表')).toBeInTheDocument();
  });

  it('shows upgrade prompt for non-enterprise tiers', () => {
    useAuthStore.mockReturnValue(makeStore('professional'));

    render(<ProductImportPage />);

    expect(screen.getByText('升级到企业版，解锁 Excel 产品导入')).toBeInTheDocument();
    expect(screen.queryByText('上传产品数据表')).not.toBeInTheDocument();
    expect(productImportAPI.preview).not.toHaveBeenCalled();
  });
});
