import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '../stores/authStore';

describe('authStore setAuth race condition', () => {
  beforeEach(() => {
    localStorage.clear();
    sessionStorage.clear();
    useAuthStore.setState({
      user: null,
      token: null,
      isAuthenticated: false,
    });
  });

  it('handles concurrent setAuth calls correctly', () => {
    const store = useAuthStore.getState();
    
    store.setAuth({ id: 1, username: 'user1' }, 'token1');
    store.setAuth({ id: 2, username: 'user2' }, 'token2');
    store.setAuth({ id: 3, username: 'user3' }, 'token3');
    
    const state = useAuthStore.getState();
    expect(state.user.id).toBe(3);
    expect(state.user.username).toBe('user3');
    // In test mode, token is explicitly null and not saved to session storage
    expect(state.token).toBeNull();
    expect(sessionStorage.getItem('api_token')).toBeNull();
    
    const storedUser = JSON.parse(localStorage.getItem('api_user'));
    expect(storedUser.id).toBe(3);
    expect(storedUser.username).toBe('user3');
  });
});
