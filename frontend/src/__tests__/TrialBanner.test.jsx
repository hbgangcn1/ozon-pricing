import React from 'react';
import { render, screen, waitFor, act } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import TrialBanner from '../components/TrialBanner';
import { trialAPI } from '../services/api';
import { useAuthStore } from '../stores/authStore';

vi.mock('../services/api', () => ({
  trialAPI: {
    getStatus: vi.fn(),
    claim: vi.fn(),
  },
  authAPI: {
    getMe: vi.fn(),
  },
}));

vi.mock('sonner', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

describe('TrialBanner', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    useAuthStore.setState({ user: null, isAuthenticated: false, token: null });
  });

  afterEach(() => {
    vi.useRealTimers();
    useAuthStore.setState({ user: null, isAuthenticated: false, token: null });
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

  it('renders nothing for admin role and does not call trial API', async () => {
    useAuthStore.setState({
      user: { id: 1, username: 'admin', role: 'admin', subscription_type: 'permanent' },
      isAuthenticated: true,
    });
    const { container } = render(<TrialBanner />);
    await waitFor(() => {
      expect(container.firstChild).toBeNull();
    });
    expect(trialAPI.getStatus).not.toHaveBeenCalled();
  });

  it('does not setState after unmount on polling interval', async () => {
    vi.useFakeTimers();
    const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
    
    let resolveSlowFetch;
    const slowFetchPromise = new Promise(resolve => { resolveSlowFetch = resolve; });
    trialAPI.getStatus.mockReturnValue(slowFetchPromise);
    
    const { unmount } = render(<TrialBanner />);
    
    unmount();
    
    resolveSlowFetch({
      eligible: true,
      in_trial: false,
      trial_used: false,
      remaining_seconds: 0,
      trial_expires_at: 0,
    });
    
    await act(async () => {
      await Promise.resolve(); // flush microtasks
      vi.advanceTimersByTime(60_010);
    });
    
    // Vitest will complain if setState is called after unmount, and consoleError will be called
    expect(consoleErrorSpy).not.toHaveBeenCalledWith(expect.stringContaining('unmounted component'));
    consoleErrorSpy.mockRestore();
  });
});
