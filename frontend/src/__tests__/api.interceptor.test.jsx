import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const mockRequestUse = vi.fn()
  const mockResponseUse = vi.fn()
  const mockAxiosPost = vi.fn()
  const mockLogout = vi.fn()
  const mockSetToken = vi.fn()
  const mockSetSessionKicked = vi.fn()
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
  const mockToastError = vi.fn()
  return {
    mockRequestUse,
    mockResponseUse,
    mockAxiosPost,
    mockLogout,
    mockSetToken,
    mockSetSessionKicked,
    mockGetState,
    mockApiInstance,
    mockToastError,
  }
})

vi.mock('axios', () => {
  const axiosDefault = Object.assign(vi.fn(), {
    create: vi.fn(() => mocks.mockApiInstance),
    post: mocks.mockAxiosPost,
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
    error: mocks.mockToastError,
  },
}))

async function loadApiModule() {
  vi.resetModules()
  return import('../services/api')
}

describe('api interceptor session handling', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mocks.mockGetState.mockReturnValue({
      token: null,
      logout: mocks.mockLogout,
      setToken: mocks.mockSetToken,
      setSessionKicked: mocks.mockSetSessionKicked,
    })
    delete window.location
    window.location = { href: '', pathname: '/pricing', search: '' }
    document.cookie = 'csrf_token=test-csrf-token'
  })

  it.each([
    'kicked_by_new_login',
    'kicked_by_max_concurrent',
    'manual_logout',
    'password_reset',
    null,
  ])('calls setSessionKicked and skips toast for detail reason %s', async (reason) => {
    await loadApiModule()
    const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
    const error = {
      response: {
        status: 401,
        data: {
          detail: {
            error: '会话已失效',
            reason,
          },
        },
      },
      config: { url: '/products', headers: {} },
    }

    await expect(resErrorInterceptor(error)).rejects.toBe(error)

    expect(mocks.mockSetSessionKicked).toHaveBeenCalledWith({ reason })
    expect(mocks.mockToastError).not.toHaveBeenCalled()
    expect(mocks.mockLogout).not.toHaveBeenCalled()
    expect(mocks.mockAxiosPost).not.toHaveBeenCalled()
  })

  it('falls back to legacy logout and toast flow for string detail 401', async () => {
    localStorage.setItem('api_user', 'user')
    localStorage.setItem('api_token', 'token')
    await loadApiModule()
    const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
    mocks.mockAxiosPost.mockRejectedValue({
      response: {
        status: 401,
        data: { detail: '令牌已过期' },
      },
    })

    const error = {
      response: {
        status: 401,
        data: { detail: '令牌已过期' },
      },
      config: { url: '/products', headers: {} },
    }

    await expect(resErrorInterceptor(error)).rejects.toBe(error)

    expect(mocks.mockAxiosPost).toHaveBeenCalledTimes(1)
    expect(mocks.mockLogout).toHaveBeenCalledTimes(1)
    expect(mocks.mockSetSessionKicked).not.toHaveBeenCalled()
    expect(mocks.mockToastError).toHaveBeenCalledWith('令牌已过期')
    expect(window.location.href).toBe('/login')
  })

  it('does NOT refresh, redirect, or toast on 401 when auth401Mode=local', async () => {
    localStorage.setItem('api_user', 'user')
    localStorage.setItem('api_token', 'token')
    await loadApiModule()
    const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]

    const error = {
      response: {
        status: 401,
        data: { detail: '当前密码错误' },
      },
      config: {
        url: '/auth/change-password',
        headers: {},
        auth401Mode: 'local',
      },
    }

    await expect(resErrorInterceptor(error)).rejects.toBe(error)

    expect(mocks.mockAxiosPost).not.toHaveBeenCalled()
    expect(mocks.mockLogout).not.toHaveBeenCalled()
    expect(mocks.mockSetSessionKicked).not.toHaveBeenCalled()
    expect(mocks.mockToastError).not.toHaveBeenCalled()
    expect(window.location.href).toBe('')
  })

  it('still honors session-kicked detail even when auth401Mode=local', async () => {
    await loadApiModule()
    const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]

    const error = {
      response: {
        status: 401,
        data: { detail: { error: '已失效', reason: 'kicked_by_new_login' } },
      },
      config: {
        url: '/auth/change-password',
        headers: {},
        auth401Mode: 'local',
      },
    }

    await expect(resErrorInterceptor(error)).rejects.toBe(error)

    expect(mocks.mockSetSessionKicked).toHaveBeenCalledWith({ reason: 'kicked_by_new_login' })
    expect(mocks.mockAxiosPost).not.toHaveBeenCalled()
    expect(mocks.mockLogout).not.toHaveBeenCalled()
    expect(mocks.mockToastError).not.toHaveBeenCalled()
  })
})
