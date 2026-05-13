import React from 'react';
import { render, fireEvent } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import ProductImportPage from '../pages/ProductImportPage';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';
import { productImportAPI } from '../services/api';

vi.mock('sonner', () => ({
  toast: { error: vi.fn() },
}));

vi.mock('../services/api', () => ({
  productImportAPI: {
    preview: vi.fn(),
  },
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('ProductImportPage fileValidation', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAuthStore.mockReturnValue({
      user: { subscription_type: 'enterprise' },
      hasEnterpriseAccess: () => true,
    });
  });

  it('rejects files larger than 50MB', () => {
    render(<ProductImportPage />);
    const input = document.querySelector('input[type="file"]');
    
    const file = new File(['x'.repeat(1024)], 'test.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    Object.defineProperty(file, 'size', { value: 50 * 1024 * 1024 + 1 });
    
    fireEvent.change(input, { target: { files: [file] } });
    
    expect(toast.error).toHaveBeenCalledWith('文件大小不能超过 50MB');
    expect(productImportAPI.preview).not.toHaveBeenCalled();
  });

  it('rejects files with invalid extensions', () => {
    render(<ProductImportPage />);
    const input = document.querySelector('input[type="file"]');
    
    const file = new File(['test'], 'test.txt', { type: 'text/plain' });
    
    fireEvent.change(input, { target: { files: [file] } });
    
    expect(toast.error).toHaveBeenCalledWith('仅支持 .xlsx / .xls 文件');
    expect(productImportAPI.preview).not.toHaveBeenCalled();
  });

  it('accepts valid files under 50MB', async () => {
    productImportAPI.preview.mockResolvedValue({ columns: [], preview_rows: [] });
    render(<ProductImportPage />);
    const input = document.querySelector('input[type="file"]');
    
    const file = new File(['test'], 'test.xlsx', { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    Object.defineProperty(file, 'size', { value: 5 * 1024 * 1024 });
    
    fireEvent.change(input, { target: { files: [file] } });
    
    expect(toast.error).not.toHaveBeenCalled();
    expect(productImportAPI.preview).toHaveBeenCalled();
  });
});
