import { renderHook, act } from '@testing-library/react';
import { vi, describe, it, expect, beforeEach, afterEach } from 'vitest';
import { useTokenRefresh } from '../hooks/useTokenRefresh';
import { useAuthStore } from '../stores/authStore';

vi.mock('../stores/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('useTokenRefresh', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.useRealTimers();
    vi.clearAllMocks();
  });

  it('should not call refreshToken if unmounted during interval', async () => {
    const shouldRefreshTokenMock = vi.fn().mockReturnValue(true);
    let resolveRefresh;
    const refreshTokenMock = vi.fn().mockReturnValue(new Promise(resolve => {
      resolveRefresh = resolve;
    }));

    useAuthStore.mockImplementation((selector) => {
      const state = {
        isAuthenticated: true,
        shouldRefreshToken: shouldRefreshTokenMock,
        refreshToken: refreshTokenMock,
      };
      return selector(state);
    });

    const { unmount } = renderHook(() => useTokenRefresh());

    // checkAndRefresh is called immediately
    expect(shouldRefreshTokenMock).toHaveBeenCalledTimes(1);
    expect(refreshTokenMock).toHaveBeenCalledTimes(1);

    // Unmount before the next interval
    unmount();

    // Advance timers
    await act(async () => {
      vi.advanceTimersByTime(60 * 1000 + 100);
    });

    // Resolve the first refresh promise
    resolveRefresh();

    // refreshToken should not be called again because the interval was cleared
    // But more importantly, if it was called (e.g. interval wasn't cleared), it would throw or do something
    // Let's verify that refreshToken was only called once
    expect(refreshTokenMock).toHaveBeenCalledTimes(1);
  });
});
