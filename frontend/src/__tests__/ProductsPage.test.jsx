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

vi.mock('antd', () => {
  return {
    Table: ({ columns, dataSource }) => (
      <div data-testid="table">
        <div data-testid="columns">
          {columns.map(c => <span key={c.key}>{c.title}</span>)}
        </div>
        <div data-testid="datasource">
          {dataSource?.map(item => (
            <div key={item.id} data-testid="row">
              <span>{item.name}</span>
              {columns.find(c => c.key === 'action')?.render(null, item)}
            </div>
          ))}
        </div>
      </div>
    ),
    Button: ({ children, onClick }) => (
      <button onClick={onClick}>{children}</button>
    ),
    Modal: ({ open, title, onOk, onCancel, okText = '确定', cancelText = '取消', children }) => (
      open ? (
        <div data-testid="modal">
          <h2>{title}</h2>
          <div data-testid="modal-content">{children}</div>
          <button onClick={onOk}>{okText}</button>
          <button onClick={onCancel}>{cancelText}</button>
        </div>
      ) : null
    ),
    Form: Object.assign(
      ({ children }) => <form data-testid="form">{children}</form>,
      {
        Item: ({ label, children }) => (
          <div data-testid="form-item">
            <label>{label}</label>
            {children}
          </div>
        ),
        useForm: () => [{
          resetFields: vi.fn(),
          setFieldsValue: vi.fn(),
          validateFields: vi.fn().mockResolvedValue({ name: 'New Product' }),
        }],
      }
    ),
    Input: (props) => <input data-testid="input" {...props} />,
    InputNumber: (props) => <input type="number" data-testid="input-number" {...props} />,
    message: {
      success: vi.fn(),
      error: vi.fn(),
    },
  };
});

vi.mock('@ant-design/icons', () => ({
  PlusOutlined: () => <span>PlusIcon</span>,
  DeleteOutlined: () => <span>DeleteIcon</span>,
  EditOutlined: () => <span>EditIcon</span>,
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
    expect(screen.getByText('添加产品')).toBeInTheDocument();
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
    
    fireEvent.click(screen.getAllByText('添加产品')[0]);
    
    expect(screen.getAllByText('添加产品').length).toBeGreaterThan(1);
    expect(screen.getByTestId('modal')).toBeInTheDocument();
  });

  it('opens edit modal with pre-filled data on edit button click', () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    renderComponent();
    
    const editButtons = screen.getAllByText('编辑');
    fireEvent.click(editButtons[0]);
    
    expect(screen.getByText('编辑产品')).toBeInTheDocument();
    expect(screen.getByTestId('modal')).toBeInTheDocument();
  });

  it('calls productsAPI.delete + removeProduct on delete confirmation', async () => {
    productsAPI.getAll.mockResolvedValueOnce([]);
    productsAPI.delete.mockResolvedValueOnce();
    
    renderComponent();
    
    const deleteButtons = screen.getAllByText('删除');
    fireEvent.click(deleteButtons[0]);
    
    expect(screen.getByText('确认删除')).toBeInTheDocument();
    
    fireEvent.click(screen.getByText('确定删除'));
    
    await waitFor(() => {
      expect(productsAPI.delete).toHaveBeenCalledWith(1);
      expect(mockRemoveProduct).toHaveBeenCalledWith(1);
    });
  });

  it('shows error message on fetch failure', async () => {
    productsAPI.getAll.mockRejectedValueOnce(new Error('Failed'));
    
    const { message } = await import('antd');
    
    renderComponent();
    
    await waitFor(() => {
      expect(productsAPI.getAll).toHaveBeenCalled();
      expect(message.error).toHaveBeenCalledWith('获取产品列表失败');
    });
  });
});
