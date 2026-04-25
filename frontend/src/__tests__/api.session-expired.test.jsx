import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const mockRequestUse = vi.fn()
  const mockResponseUse = vi.fn()
  const mockLogout = vi.fn()
  const mockSetToken = vi.fn()
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
    mockLogout,
    mockSetToken,
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
  useAuthStore: {
    getState: mocks.mockGetState,
  },
}))

vi.mock('sonner', () => ({
  toast: {
    error: vi.fn(),
  },
}))

async function loadApiModule() {
  vi.resetModules()
  return import('../services/api')
}

describe('api session expired flow', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mocks.mockGetState.mockReturnValue({
      token: null,
      logout: mocks.mockLogout,
      setToken: mocks.mockSetToken,
      refreshToken: mocks.mockRefreshToken,
    })
    delete window.location
    window.location = {
      href: '',
      pathname: '/pricing',
      search: '?tab=precise',
    }
    document.cookie = 'csrf_token=test-csrf-token'
  })

  it('redirects to login with encoded returnTo and toast on refresh 401', async () => {
    const { toast } = await import('sonner')
    await loadApiModule()
    const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
    localStorage.setItem('api_user', 'user')
    localStorage.setItem('api_token', 'token')
    mocks.mockRefreshToken.mockRejectedValue({ response: { status: 401 } })

    const originalError = {
      response: { status: 401 },
      config: { url: '/products', headers: {} },
    }

    await expect(resErrorInterceptor(originalError)).rejects.toBe(originalError)

    expect(mocks.mockLogout).toHaveBeenCalledTimes(1)
    expect(toast.error).toHaveBeenCalledWith('会话已过期，您的填写内容已保存。请重新登录。')
    expect(window.location.href).toBe('/login?returnTo=%2Fpricing%3Ftab%3Dprecise&reason=expired')
  })

  it('does not use session expired redirect for non-401 refresh failures', async () => {
    const { toast } = await import('sonner')
    await loadApiModule()
    const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
    mocks.mockRefreshToken.mockRejectedValue(new Error('network down'))

    const originalError = {
      response: { status: 401 },
      config: { url: '/products', headers: {} },
    }

    await expect(resErrorInterceptor(originalError)).rejects.toBe(originalError)

    expect(mocks.mockLogout).not.toHaveBeenCalled()
    expect(toast.error).not.toHaveBeenCalled()
    expect(window.location.href).toBe('')
  })
})
