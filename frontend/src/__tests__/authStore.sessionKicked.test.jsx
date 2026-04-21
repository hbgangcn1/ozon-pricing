import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useAuthStore } from '../stores/authStore'

describe('authStore sessionKicked', () => {
  const initialState = useAuthStore.getState()

  beforeEach(() => {
    useAuthStore.setState(initialState, true)
    localStorage.clear()
    vi.clearAllMocks()
  })

  it('setSessionKicked opens dialog with reason', () => {
    useAuthStore.getState().setSessionKicked({ reason: 'password_reset' })

    expect(useAuthStore.getState().sessionKicked).toEqual({
      open: true,
      reason: 'password_reset',
    })
  })

  it('clearSessionKicked resets dialog state and clears auth data', () => {
    useAuthStore.setState({
      user: { id: 1, username: 'demo' },
      token: 'token',
      isAuthenticated: true,
      sessionKicked: { open: true, reason: 'kicked_by_new_login' },
    })
    localStorage.setItem('api_user', JSON.stringify({ id: 1, username: 'demo' }))
    localStorage.setItem('api_token', 'token')

    useAuthStore.getState().clearSessionKicked()

    const state = useAuthStore.getState()
    expect(state.user).toBeNull()
    expect(state.token).toBeNull()
    expect(state.isAuthenticated).toBe(false)
    expect(state.sessionKicked).toEqual({ open: false, reason: null })
    expect(localStorage.getItem('api_user')).toBeNull()
    expect(localStorage.getItem('api_token')).toBeNull()
  })
})
