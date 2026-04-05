import React from 'react';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import ProductsPage from '../pages/ProductsPage';
import { productsAPI } from '../services/api';

vi.mock('../services/api', () => ({
  productsAPI: {
    getAll: vi.fn(),
    create: vi.fn(),
    update: vi.fn(),
    delete: vi.fn(),
  },
}));

const mockSetProducts = vi.fn();
const mockAddProduct = vi.fn();
const mockUpdateProduct = vi.fn();
const mockRemoveProduct = vi.fn();

vi.mock('../stores/productStore', () => ({
  useProductStore: () => ({
    products: [
      { id: 1, name: 'Product A', category: 'Cat A', unit_price: 10, weight_g: 100 }
    ],
    setProducts: mockSetProducts,
    addProduct: mockAddProduct,
    updateProduct: mockUpdateProduct,
    removeProduct: mockRemoveProduct,
  }),
}));

vi.mock('lucide-react', () => ({
  Plus: () => <span data-testid="icon-plus">PlusIcon</span>,
  Pencil: () => <span data-testid="icon-pencil">EditIcon</span>,
  Trash2: () => <span data-testid="icon-trash">DeleteIcon</span>,
  Loader2: () => <span data-testid="icon-loader">LoaderIcon</span>,
  Package: () => <span data-testid="icon-package">PackageIcon</span>,
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, className }) => (
    <button onClick={onClick} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table data-testid="table">{children}</table>,
  TableHeader: ({ children }) => <thead data-testid="table-header">{children}</thead>,
  TableBody: ({ children }) => <tbody data-testid="table-body">{children}</tbody>,
  TableRow: ({ children, className }) => <tr className={className} data-testid="table-row">{children}</tr>,
  TableHead: ({ children, className }) => <th className={className} data-testid="table-head">{children}</th>,
  TableCell: ({ children, colSpan, className }) => <td className={className} data-testid="table-cell" colSpan={colSpan}>{children}</td>,
}));

vi.mock('../components/ui/dialog', () => ({
  Dialog: ({ open, children, onOpenChange }) => open ? <div data-testid="dialog">{children}</div> : null,
  DialogContent: ({ children, className }) => <div className={className} data-testid="dialog-content">{children}</div>,
  DialogHeader: ({ children }) => <div data-testid="dialog-header">{children}</div>,
  DialogTitle: ({ children, className }) => <h2 className={className} data-testid="dialog-title">{children}</h2>,
  DialogFooter: ({ children, className }) => <div className={className} data-testid="dialog-footer">{children}</div>,
}));

vi.mock('../components/ui/input', () => ({
  Input: (props) => <input data-testid="input" {...props} />,
}));

vi.mock('../components/ui/label', () => ({
  Label: ({ children, htmlFor, className }) => <label className={className} htmlFor={htmlFor} data-testid="label">{children}</label>,
}));

describe('ProductsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  const renderComponent = () => {
    return render(
      <MemoryRouter>
        <ProductsPage />
      </MemoryRouter>
    );
  };

  it('renders "添加产品" button', () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    renderComponent();
    expect(screen.getByText(/添加产品/)).toBeInTheDocument();
  });

  it('fetches and displays products on mount', async () => {
    const mockProducts = [{ id: 1, name: 'Product A' }];
    productsAPI.getAll.mockResolvedValueOnce(mockProducts);
    renderComponent();
    await waitFor(() => {
      expect(productsAPI.getAll).toHaveBeenCalled();
      expect(mockSetProducts).toHaveBeenCalledWith(mockProducts);
    });
  });

  it('shows table with product columns (ID, 产品名称, 类别, 单价, 重量)', () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    renderComponent();
    expect(screen.getByText('ID')).toBeInTheDocument();
    expect(screen.getByText('产品名称')).toBeInTheDocument();
    expect(screen.getByText('类别')).toBeInTheDocument();
    expect(screen.getByText('单价')).toBeInTheDocument();
    expect(screen.getByText('重量(g)')).toBeInTheDocument();
  });

  it('opens add modal on "添加产品" click', () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    renderComponent();
    
    const addButton = screen.getAllByText(/添加产品/)[0].closest('button');
    fireEvent.click(addButton);
    
    expect(screen.getByTestId('dialog')).toBeInTheDocument();
  });

  it('opens edit modal with pre-filled data on edit button click', async () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Product A')).toBeInTheDocument();
    });

    const editButton = screen.getByText('编辑').closest('button');
    fireEvent.click(editButton);
    
    expect(screen.getByText('编辑产品')).toBeInTheDocument();
    expect(screen.getByTestId('dialog')).toBeInTheDocument();
  });

  it('calls productsAPI.delete + removeProduct on delete confirmation', async () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    productsAPI.delete.mockResolvedValueOnce();
    renderComponent();
    
    await waitFor(() => {
      expect(screen.getByText('Product A')).toBeInTheDocument();
    });

    const deleteButton = screen.getByText('删除').closest('button');
    fireEvent.click(deleteButton);
    
    expect(screen.getByText('确认删除')).toBeInTheDocument();
    
    fireEvent.click(screen.getByText('确定删除'));
    
    await waitFor(() => {
      expect(productsAPI.delete).toHaveBeenCalledWith(1);
      expect(mockRemoveProduct).toHaveBeenCalledWith(1);
    });
  });

  it('shows error message on fetch failure', async () => {
    productsAPI.getAll.mockRejectedValueOnce(new Error('Failed'));
    const { toast } = await import('sonner');
    renderComponent();
    
    await waitFor(() => {
      expect(productsAPI.getAll).toHaveBeenCalled();
      expect(toast.error).toHaveBeenCalledWith('获取产品列表失败');
    });
  });
});
