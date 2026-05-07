import React from 'react';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import TrialExpiredModal from '../components/TrialExpiredModal';
import { trialAPI } from '../services/api';

vi.mock('../services/api', () => ({
  trialAPI: { getStatus: vi.fn(), claim: vi.fn() },
}));

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async (orig) => {
  const actual = await orig();
  return { ...actual, useNavigate: () => mockNavigate };
});

const renderWithRouter = (ui) => render(<MemoryRouter>{ui}</MemoryRouter>);

const SEEN_PREFIX = 'trial_expired_modal_seen_';

describe('TrialExpiredModal', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  it('opens once when trial just expired and writes localStorage on close', async () => {
    const user = userEvent.setup();
    const expiresAt = Math.floor(Date.now() / 1000) - 3600;
    trialAPI.getStatus.mockResolvedValue({
      eligible: false,
      in_trial: false,
      trial_used: true,
      remaining_seconds: 0,
      trial_expires_at: expiresAt,
    });

    renderWithRouter(<TrialExpiredModal />);
    expect(await screen.findByText('专业版试用已结束')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: '稍后再说' }));
    await waitFor(() => {
      expect(screen.queryByText('专业版试用已结束')).not.toBeInTheDocument();
    });
    expect(localStorage.getItem(`${SEEN_PREFIX}${expiresAt}`)).toBe('1');
  });

  it('does not open when localStorage flag already set', async () => {
    const expiresAt = Math.floor(Date.now() / 1000) - 3600;
    localStorage.setItem(`${SEEN_PREFIX}${expiresAt}`, '1');
    trialAPI.getStatus.mockResolvedValue({
      eligible: false, in_trial: false, trial_used: true,
      remaining_seconds: 0, trial_expires_at: expiresAt,
    });
    renderWithRouter(<TrialExpiredModal />);
    await waitFor(() => expect(trialAPI.getStatus).toHaveBeenCalled());
    expect(screen.queryByText('专业版试用已结束')).not.toBeInTheDocument();
  });

  it('does not open when trial expired more than 48h ago', async () => {
    const expiresAt = Math.floor(Date.now() / 1000) - (49 * 3600);
    trialAPI.getStatus.mockResolvedValue({
      eligible: false, in_trial: false, trial_used: true,
      remaining_seconds: 0, trial_expires_at: expiresAt,
    });
    renderWithRouter(<TrialExpiredModal />);
    await waitFor(() => expect(trialAPI.getStatus).toHaveBeenCalled());
    expect(screen.queryByText('专业版试用已结束')).not.toBeInTheDocument();
  });

  it('does not open when in_trial=true', async () => {
    trialAPI.getStatus.mockResolvedValue({
      eligible: false, in_trial: true, trial_used: true,
      remaining_seconds: 86400, trial_expires_at: Math.floor(Date.now() / 1000) + 86400,
    });
    renderWithRouter(<TrialExpiredModal />);
    await waitFor(() => expect(trialAPI.getStatus).toHaveBeenCalled());
    expect(screen.queryByText('专业版试用已结束')).not.toBeInTheDocument();
  });

  it('navigates to /subscriptions on upgrade click', async () => {
    const user = userEvent.setup();
    const expiresAt = Math.floor(Date.now() / 1000) - 3600;
    trialAPI.getStatus.mockResolvedValue({
      eligible: false, in_trial: false, trial_used: true,
      remaining_seconds: 0, trial_expires_at: expiresAt,
    });
    renderWithRouter(<TrialExpiredModal />);
    await screen.findByText('专业版试用已结束');

    await user.click(screen.getByRole('button', { name: '立即升级' }));
    expect(mockNavigate).toHaveBeenCalledWith('/subscriptions');
    expect(localStorage.getItem(`${SEEN_PREFIX}${expiresAt}`)).toBe('1');
  });
});
