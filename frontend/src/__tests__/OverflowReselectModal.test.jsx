import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import OverflowReselectModal from '../components/OverflowReselectModal';
import { overflowAPI } from '../services/api';
import { toast } from 'sonner';

vi.mock('../services/api', () => ({
  overflowAPI: {
    getStatus: vi.fn(),
    reselect: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

const items = [
  { id: 1, name: 'Rule A', is_active: 1, disabled_by_overflow: 0 },
  { id: 2, name: 'Rule B', is_active: 1, disabled_by_overflow: 0 },
  { id: 3, name: 'Rule C', is_active: 1, disabled_by_overflow: 1 },
  { id: 4, name: 'Inactive', is_active: 0, disabled_by_overflow: 0 },
];

describe('OverflowReselectModal', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    vi.clearAllMocks();
  });

  it('renders nothing when has_open_window=false', async () => {
    overflowAPI.getStatus.mockResolvedValue({ has_open_window: false });
    const { container } = render(<OverflowReselectModal items={items} />);
    await waitFor(() => expect(overflowAPI.getStatus).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it('auto-opens once when has_open_window=true and lists active candidates', async () => {
    overflowAPI.getStatus.mockResolvedValue({ has_open_window: true, new_limit: 2 });
    render(<OverflowReselectModal items={items} />);
    expect(await screen.findByText('请重新选择物流规则')).toBeInTheDocument();
    expect(screen.getByText('Rule A')).toBeInTheDocument();
    expect(screen.getByText('Rule B')).toBeInTheDocument();
    expect(screen.getByText('Rule C')).toBeInTheDocument();
    expect(screen.queryByText('Inactive')).not.toBeInTheDocument();
    expect(sessionStorage.getItem('overflow_reselect_modal_shown')).toBe('1');
  });

  it('does not auto-open when sessionStorage flag already set', async () => {
    sessionStorage.setItem('overflow_reselect_modal_shown', '1');
    overflowAPI.getStatus.mockResolvedValue({ has_open_window: true, new_limit: 2 });
    render(<OverflowReselectModal items={items} />);
    await waitFor(() => expect(overflowAPI.getStatus).toHaveBeenCalled());
    expect(screen.queryByText('请重新选择物流规则')).not.toBeInTheDocument();
  });

  it('blocks submit when selection exceeds limit (toast error, no API call)', async () => {
    const user = userEvent.setup();
    overflowAPI.getStatus.mockResolvedValue({ has_open_window: true, new_limit: 1 });
    render(<OverflowReselectModal items={items} />);
    await screen.findByText('请重新选择物流规则');

    await user.click(screen.getByLabelText('选择 Rule A'));
    await user.click(screen.getByLabelText('选择 Rule B'));

    const submitBtn = screen.getByRole('button', { name: '提交' });
    expect(submitBtn).toBeDisabled();
    expect(overflowAPI.reselect).not.toHaveBeenCalled();
  });

  it('submits selected ids, toasts success, calls onCompleted', async () => {
    const user = userEvent.setup();
    overflowAPI.getStatus.mockResolvedValue({ has_open_window: true, new_limit: 3 });
    overflowAPI.reselect.mockResolvedValue({ status: 'ok', enabled_ids: [1, 2], disabled_ids: [3] });
    const onCompleted = vi.fn();

    render(<OverflowReselectModal items={items} onCompleted={onCompleted} />);
    await screen.findByText('请重新选择物流规则');

    await user.click(screen.getByLabelText('选择 Rule A'));
    await user.click(screen.getByLabelText('选择 Rule B'));
    await user.click(screen.getByRole('button', { name: '提交' }));

    await waitFor(() => expect(overflowAPI.reselect).toHaveBeenCalledWith([1, 2]));
    expect(toast.success).toHaveBeenCalledWith('已重新选择');
    expect(onCompleted).toHaveBeenCalledTimes(1);
  });

  it('shows error toast when API rejects', async () => {
    const user = userEvent.setup();
    overflowAPI.getStatus.mockResolvedValue({ has_open_window: true, new_limit: 3 });
    overflowAPI.reselect.mockRejectedValue({ response: { data: { detail: '窗口已关闭' } } });

    render(<OverflowReselectModal items={items} />);
    await screen.findByText('请重新选择物流规则');

    await user.click(screen.getByLabelText('选择 Rule A'));
    await user.click(screen.getByRole('button', { name: '提交' }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith('窗口已关闭'));
  });
});
