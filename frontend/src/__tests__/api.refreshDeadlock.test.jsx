import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const mockRequestUse = vi.fn()
  const mockResponseUse = vi.fn()
  const mockShouldRefreshToken = vi.fn()
  const mockRefreshToken = vi.fn()
  const mockGetState = vi.fn()
  const mockApiInstance = Object.assign(vi.fn(), {
    interceptors: {
      request: { use: mockRequestUse },
      response: { use: mockResponseUse },
    },
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  })
  return {
    mockRequestUse,
    mockResponseUse,
    mockShouldRefreshToken,
    mockRefreshToken,
    mockGetState,
    mockApiInstance,
  }
})

vi.mock('axios', () => {
  const axiosDefault = Object.assign(vi.fn(), {
    create: vi.fn(() => mocks.mockApiInstance),
    post: vi.fn(),
  })
  return { default: axiosDefault }
})

vi.mock('../stores/authStore', () => ({
  useAuthStore: { getState: mocks.mockGetState },
}))

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))

async function loadApiModuleWithMode(mode) {
  vi.resetModules()
  vi.stubEnv('MODE', mode)
  return import('../services/api')
}

describe('api request interceptor — refresh self-deadlock prevention', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.mockGetState.mockReturnValue({
      token: 'expired-token',
      shouldRefreshToken: mocks.mockShouldRefreshToken,
      refreshToken: mocks.mockRefreshToken,
    })
    mocks.mockShouldRefreshToken.mockReturnValue(true)
    document.cookie = 'csrf_token=test-csrf'
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  it('does NOT call refreshToken when the outgoing request is /auth/refresh-access', async () => {
    await loadApiModuleWithMode('development')
    const reqInterceptor = mocks.mockRequestUse.mock.calls[0][0]

    const config = await reqInterceptor({
      url: '/auth/refresh-access',
      headers: {},
    })

    expect(mocks.mockShouldRefreshToken).not.toHaveBeenCalled()
    expect(mocks.mockRefreshToken).not.toHaveBeenCalled()
    expect(config.headers.Authorization).toBe('Bearer expired-token')
  })

  it('does NOT call refreshToken when the outgoing request is /auth/refresh', async () => {
    await loadApiModuleWithMode('development')
    const reqInterceptor = mocks.mockRequestUse.mock.calls[0][0]

    await reqInterceptor({ url: '/auth/refresh', headers: {} })

    expect(mocks.mockRefreshToken).not.toHaveBeenCalled()
  })

  it('DOES call refreshToken on regular endpoints when token is near expiry', async () => {
    mocks.mockRefreshToken.mockResolvedValue('new-token')
    await loadApiModuleWithMode('development')
    const reqInterceptor = mocks.mockRequestUse.mock.calls[0][0]

    await reqInterceptor({ url: '/auth/me', headers: {} })

    expect(mocks.mockShouldRefreshToken).toHaveBeenCalled()
    expect(mocks.mockRefreshToken).toHaveBeenCalledTimes(1)
  })
})
