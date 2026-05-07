import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import TrialBanner from '../components/TrialBanner';
import { trialAPI } from '../services/api';

vi.mock('../services/api', () => ({
  trialAPI: {
    getStatus: vi.fn(),
    claim: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe('TrialBanner', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders claim button when eligible and not yet used', async () => {
    trialAPI.getStatus.mockResolvedValue({
      eligible: true,
      in_trial: false,
      trial_used: false,
      remaining_seconds: 0,
      trial_expires_at: 0,
    });
    render(<TrialBanner />);
    expect(await screen.findByRole('button', { name: '开始 7 天专业版试用' })).toBeInTheDocument();
  });

  it('renders remaining days when in_trial', async () => {
    trialAPI.getStatus.mockResolvedValue({
      eligible: false,
      in_trial: true,
      trial_used: true,
      remaining_seconds: 3 * 86400 + 100,
      trial_expires_at: 9999999999,
    });
    render(<TrialBanner />);
    expect(await screen.findByText(/剩余 4 天/)).toBeInTheDocument();
  });

  it('dismiss writes localStorage and hides banner; reappears after 24h', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });

    trialAPI.getStatus.mockResolvedValue({
      eligible: false,
      in_trial: true,
      trial_used: true,
      remaining_seconds: 5 * 86400,
      trial_expires_at: 9999999999,
    });

    const { unmount } = render(<TrialBanner />);
    const dismissBtn = await screen.findByRole('button', { name: '关闭试用提示' });
    await user.click(dismissBtn);

    await waitFor(() => {
      expect(screen.queryByText(/剩余/)).not.toBeInTheDocument();
    });
    const stored = localStorage.getItem('trial_banner_dismissed_until');
    expect(stored).toBeTruthy();
    expect(Number.parseInt(stored, 10)).toBeGreaterThan(Date.now());

    unmount();

    act(() => {
      vi.advanceTimersByTime(24 * 3600 * 1000 + 1000);
    });

    render(<TrialBanner />);
    expect(await screen.findByText(/剩余/)).toBeInTheDocument();
  });
});
