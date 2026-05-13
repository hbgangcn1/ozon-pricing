import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '../stores/authStore';

describe('authStore safeJsonParse', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true
    });
  });

  it('handles invalid JSON in localStorage gracefully without throwing', () => {
    localStorage.setItem('api_user', '{invalid');
    sessionStorage.setItem('api_token', 'some_token');
    
    expect(() => {
      useAuthStore.getState().initAuth();
    }).not.toThrow();
    
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isLoading).toBe(false);
    expect(localStorage.getItem('api_user')).toBeNull();
  });
});
