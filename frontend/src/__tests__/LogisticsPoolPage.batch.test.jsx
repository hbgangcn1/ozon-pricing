import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import LogisticsPoolPage, { BATCH_SIZE } from '../pages/LogisticsPoolPage';
import { logisticsPoolAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  logisticsPoolAPI: {
    getAll: vi.fn(),
    importXlsx: vi.fn(),
    addToMyLogistics: vi.fn(),
    batchAddToMyLogistics: vi.fn(),
    deleteAll: vi.fn(),
  },
}));

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
  },
}));

vi.mock('../components/ui/card', () => ({
  Card: ({ children }) => <div>{children}</div>,
  CardContent: ({ children, className }) => <div className={className}>{children}</div>,
}));

vi.mock('../components/ui/table', () => ({
  Table: ({ children }) => <table>{children}</table>,
  TableHeader: ({ children }) => <thead>{children}</thead>,
  TableBody: ({ children }) => <tbody>{children}</tbody>,
  TableRow: ({ children }) => <tr>{children}</tr>,
  TableHead: ({ children }) => <th>{children}</th>,
  TableCell: ({ children, colSpan, className }) => <td colSpan={colSpan} className={className}>{children}</td>,
}));

vi.mock('../components/ui/button', () => ({
  Button: ({ children, onClick, disabled, className }) => (
    <button type="button" onClick={onClick} disabled={disabled} className={className}>{children}</button>
  ),
}));

vi.mock('../components/ui/badge', () => ({
  Badge: ({ children, className }) => <span className={className}>{children}</span>,
}));

vi.mock('../components/ui/checkbox', () => ({
  Checkbox: ({ checked, onCheckedChange, 'aria-label': ariaLabel }) => (
    <input
      type="checkbox"
      aria-label={ariaLabel}
      checked={!!checked}
      onChange={(e) => onCheckedChange?.(e.target.checked)}
    />
  ),
}));

vi.mock('../components/ui/virtual-table', () => ({
  // 真实 VirtualTable 只渲染可视窗口（不是全部 408 行）。这里同样只渲染一批，
  // 否则 jsdom 每轮要挂 4000+ DOM 节点 → 单用例耗时 10-15s，正好卡在 15s 超时线上，
  // 出现"单独跑 5/6 挂、全量跑 1 挂"的时序 flaky（2026-10-28 实测定位）。
  VirtualTable: ({ items, columns }) => (
    <table>
      <thead>
        <tr>
          {columns.map((column) => (
            <th key={column.key}>{column.header}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {items.slice(0, 20).map((item, index) => (
          <tr key={item.id ?? index}>
            {columns.map((column) => (
              <td key={column.key}>{column.render(item, index)}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  ),
  useVirtualRows: () => ({}),
}));

const TOTAL_ITEMS = 408;

const buildItems = (count) =>
  Array.from({ length: count }, (_, i) => ({
    id: i + 1,
    name: `物流 ${i + 1}`,
    fulfillment_type: 'rfbs',
    destination: 'RU',
    fbp_service_level: null,
    is_smart: 0,
    is_active: true,
  }));

describe('LogisticsPoolPage batch add', () => {
  const setup = async (items = buildItems(TOTAL_ITEMS)) => {
    logisticsPoolAPI.getAll.mockResolvedValue(items);
    useAuthStore.mockReturnValue({
      isAdmin: () => false,
      user: { subscription_type: 'free' },
      hasEnterpriseAccess: () => false,
    });
    render(<LogisticsPoolPage />);
    await waitFor(() => expect(logisticsPoolAPI.getAll).toHaveBeenCalled());
    const selectAll = await screen.findByLabelText('全选');
    fireEvent.click(selectAll);
    return items;
  };

  const clickBatchButton = async () => {
    const btn = await screen.findByText('全部添加到我的物流');
    fireEvent.click(btn);
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exports BATCH_SIZE = 200', () => {
    expect(BATCH_SIZE).toBe(200);
  });

  it('all-success across 3 batches → success toast and selection cleared', async () => {
    logisticsPoolAPI.batchAddToMyLogistics
      .mockResolvedValueOnce({ added: 200 })
      .mockResolvedValueOnce({ added: 200 })
      .mockResolvedValueOnce({ added: 8 });

    await setup();
    await clickBatchButton();

    await waitFor(() => {
      expect(logisticsPoolAPI.batchAddToMyLogistics).toHaveBeenCalledTimes(3);
    });
    expect(logisticsPoolAPI.batchAddToMyLogistics.mock.calls[0][0]).toHaveLength(200);
    expect(logisticsPoolAPI.batchAddToMyLogistics.mock.calls[1][0]).toHaveLength(200);
    expect(logisticsPoolAPI.batchAddToMyLogistics.mock.calls[2][0]).toHaveLength(8);
    expect(toast.success).toHaveBeenCalledWith('已成功添加 408 条到我的物流');
    expect(logisticsPoolAPI.getAll).toHaveBeenCalledTimes(2);
  }, 15000);

  it('batch 2 returns 403 → loop stops, warning toast, untried ids retained', async () => {
    const quotaErr = new Error('quota');
    quotaErr.response = { status: 403, data: { detail: '物流规则数量已达上限' } };
    logisticsPoolAPI.batchAddToMyLogistics
      .mockResolvedValueOnce({ added: 200 })
      .mockRejectedValueOnce(quotaErr);

    await setup();
    await clickBatchButton();

    await waitFor(() => {
      expect(logisticsPoolAPI.batchAddToMyLogistics).toHaveBeenCalledTimes(2);
    });
    expect(toast.warning).toHaveBeenCalledWith('已添加 200 条，剩余 208 条因物流规则上限未添加');
    expect(toast.success).not.toHaveBeenCalled();
  }, 15000);

  it('first batch 422 array detail (regression) → no React unmount, message normalized', async () => {
    const validationErr = new Error('Request failed');
    validationErr.response = {
      status: 422,
      data: { detail: [{ loc: ['body', 'ids'], msg: '单次最多添加 200 条', type: 'value_error' }] },
    };
    logisticsPoolAPI.batchAddToMyLogistics.mockRejectedValueOnce(validationErr);

    await setup();
    await clickBatchButton();

    await waitFor(() => {
      expect(logisticsPoolAPI.batchAddToMyLogistics).toHaveBeenCalledTimes(1);
    });
    expect(toast.error).toHaveBeenCalledWith('单次最多添加 200 条');
    expect(toast.success).not.toHaveBeenCalled();
    expect(toast.warning).not.toHaveBeenCalled();
    expect(document.body.textContent.length).toBeGreaterThan(0);
  }, 15000);

  it('mid-loop network error → warning network variant', async () => {
    const netErr = new Error('Network Error');
    logisticsPoolAPI.batchAddToMyLogistics
      .mockResolvedValueOnce({ added: 200 })
      .mockRejectedValueOnce(netErr);

    await setup();
    await clickBatchButton();

    await waitFor(() => {
      expect(logisticsPoolAPI.batchAddToMyLogistics).toHaveBeenCalledTimes(2);
    });
    expect(toast.warning).toHaveBeenCalledWith('已添加 200 条，剩余 208 条因网络错误未添加');
  }, 15000);

  it('first batch 403 with addedTotal 0 → error toast', async () => {
    const quotaErr = new Error('quota');
    quotaErr.response = { status: 403, data: { detail: '已达到物流规则上限' } };
    logisticsPoolAPI.batchAddToMyLogistics.mockRejectedValueOnce(quotaErr);

    await setup();
    await clickBatchButton();

    await waitFor(() => {
      expect(logisticsPoolAPI.batchAddToMyLogistics).toHaveBeenCalledTimes(1);
    });
    expect(toast.error).toHaveBeenCalledWith('已达到物流规则上限');
    expect(toast.warning).not.toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
  }, 15000);
});
