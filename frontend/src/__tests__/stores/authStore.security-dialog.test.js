import { beforeEach, describe, expect, it } from 'vitest'
import { useAuthStore } from '../../stores/authStore'

describe('authStore security dialog sync', () => {
  const initialState = useAuthStore.getState()

  beforeEach(() => {
    useAuthStore.setState(initialState, true)
    localStorage.clear()
  })

  it('Scenario A: setAuth with has_security_question=true closes dialog', () => {
    useAuthStore.getState().setAuth({
      user: { id: 1, username: 'admin', role: 'admin', has_security_question: true },
      token: 'x',
    })

    expect(useAuthStore.getState().showSecurityDialog).toBe(false)
  })

  it('Scenario B: setAuth with has_security_question=false opens dialog', () => {
    useAuthStore.getState().setAuth({
      user: { id: 1, username: 'admin', role: 'admin', has_security_question: false },
      token: 'x',
    })

    expect(useAuthStore.getState().showSecurityDialog).toBe(true)
  })

  it('Scenario C: setUser refresh flips dialog closed when /auth/me returns has_security_question=true', () => {
    useAuthStore.getState().setAuth({
      user: { id: 1, username: 'admin', role: 'admin', has_security_question: false },
      token: 'x',
    })
    expect(useAuthStore.getState().showSecurityDialog).toBe(true)

    useAuthStore.getState().setUser({
      id: 1,
      username: 'admin',
      role: 'admin',
      has_security_question: true,
    })

    expect(useAuthStore.getState().showSecurityDialog).toBe(false)
  })
})
