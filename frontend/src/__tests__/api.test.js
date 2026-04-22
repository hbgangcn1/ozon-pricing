import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'


const mocks = vi.hoisted(() => {
  const mockRequestUse = vi.fn()
  const mockResponseUse = vi.fn()
  const mockAxiosPost = vi.fn()
  const mockLogout = vi.fn()
  const mockSetToken = vi.fn()
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
    mockAxiosPost,
    mockLogout,
    mockSetToken,
    mockGetState,
    mockApiInstance,
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


function createDeferred() {
  let resolve
  let reject
  const promise = new Promise((res, rej) => {
    resolve = res
    reject = rej
  })
  return { promise, resolve, reject }
}


async function loadApiModule() {
  vi.resetModules()
  return import('../services/api')
}


describe('api.js', () => {
  let originalLocation

  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
    mocks.mockGetState.mockReturnValue({
      token: null,
      logout: mocks.mockLogout,
      setToken: mocks.mockSetToken,
    })
    originalLocation = window.location
    delete window.location
    window.location = { href: '', pathname: '/' }
    document.cookie = 'csrf_token=test-csrf-token'
  })

  afterEach(() => {
    window.location = originalLocation
  })

  describe('Interceptors', () => {
    it('api client is configured with withCredentials', async () => {
      const axios = (await import('axios')).default
      await loadApiModule()

      expect(axios.create).toHaveBeenCalledWith(
        expect.objectContaining({ withCredentials: true })
      )
    })

    it('does not register a request interceptor in test mode', async () => {
      await loadApiModule()
      expect(mocks.mockRequestUse).not.toHaveBeenCalled()
    })

    it('response interceptor returns response.data on success', async () => {
      await loadApiModule()
      const resSuccessInterceptor = mocks.mockResponseUse.mock.calls[0][0]

      expect(resSuccessInterceptor({ data: { foo: 'bar' }, status: 200 })).toEqual({ foo: 'bar' })
    })

    it('401 triggers refresh once and retries original request', async () => {
      await loadApiModule()
      const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
      const originalRequest = { url: '/products', headers: {} }
      const retriedResponse = { ok: true }

      mocks.mockAxiosPost.mockResolvedValue({
        data: { access_token: 'new-access-token' },
      })
      mocks.mockApiInstance.mockResolvedValue(retriedResponse)

      const result = await resErrorInterceptor({
        response: { status: 401 },
        config: originalRequest,
      })

      expect(mocks.mockAxiosPost).toHaveBeenCalledTimes(1)
      expect(mocks.mockAxiosPost).toHaveBeenCalledWith(
        '/auth/refresh',
        null,
        expect.objectContaining({
          baseURL: '/api',
          withCredentials: true,
          headers: { 'X-CSRF-Token': 'test-csrf-token' },
        })
      )
      expect(mocks.mockSetToken).toHaveBeenCalledWith('new-access-token')
      expect(originalRequest._retry).toBe(true)
      expect(originalRequest.headers.Authorization).toBe('Bearer new-access-token')
      expect(mocks.mockApiInstance).toHaveBeenCalledWith(originalRequest)
      expect(result).toBe(retriedResponse)
    })

    it('refresh failure without 401 keeps the original request rejection', async () => {
      await loadApiModule()
      const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
      const originalError = {
        response: { status: 401 },
        config: { url: '/products', headers: {} },
      }
      mocks.mockAxiosPost.mockRejectedValue(new Error('refresh failed'))

      await expect(resErrorInterceptor(originalError)).rejects.toBe(originalError)

      expect(mocks.mockLogout).not.toHaveBeenCalled()
      expect(window.location.href).toBe('')
    })

    it('concurrent 401 requests share one refresh promise', async () => {
      await loadApiModule()
      const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
      const deferred = createDeferred()

      mocks.mockAxiosPost.mockReturnValue(deferred.promise)
      mocks.mockApiInstance.mockImplementation(async (request) => ({ url: request.url, ok: true }))

      const firstRequest = { url: '/products', headers: {} }
      const secondRequest = { url: '/orders', headers: {} }
      const firstPromise = resErrorInterceptor({
        response: { status: 401 },
        config: firstRequest,
      })
      const secondPromise = resErrorInterceptor({
        response: { status: 401 },
        config: secondRequest,
      })

      expect(mocks.mockAxiosPost).toHaveBeenCalledTimes(1)

      deferred.resolve({ data: { access_token: 'shared-token' } })
      const [firstResult, secondResult] = await Promise.all([firstPromise, secondPromise])

      expect(mocks.mockAxiosPost).toHaveBeenCalledTimes(1)
      expect(firstRequest.headers.Authorization).toBe('Bearer shared-token')
      expect(secondRequest.headers.Authorization).toBe('Bearer shared-token')
      expect(firstResult).toEqual({ url: '/products', ok: true })
      expect(secondResult).toEqual({ url: '/orders', ok: true })
    })

    it('does not redirect on 401 when already on login page', async () => {
      await loadApiModule()
      const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
      window.location.pathname = '/login'
      window.location.href = 'http://localhost/login'
      mocks.mockAxiosPost.mockRejectedValue(new Error('refresh failed'))

      await expect(
        resErrorInterceptor({
          response: { status: 401 },
          config: { url: '/products', headers: {} },
        })
      ).rejects.toBeTruthy()

      expect(window.location.href).toBe('http://localhost/login')
    })

    it('response interceptor rejects with user message on timeout', async () => {
      await loadApiModule()
      const resErrorInterceptor = mocks.mockResponseUse.mock.calls[0][1]
      const error = { code: 'ECONNABORTED' }

      await expect(resErrorInterceptor(error)).rejects.toBe(error)
      expect(error.userMessage).toBe('请求超时，请检查网络连接')
    })
  })

  describe('logoutUser', () => {
    it('calls store logout and redirects to /login', async () => {
      const { logoutUser } = await loadApiModule()
      localStorage.setItem('api_user', 'user')

      logoutUser()

      expect(mocks.mockLogout).toHaveBeenCalledTimes(1)
      expect(localStorage.getItem('api_user')).toBeNull()
      expect(window.location.href).toBe('/login')
    })
  })

  describe('API Namespaces Exists', () => {
    it('exports correctly structured API namespaces', async () => {
      const {
        authAPI,
        productsAPI,
        logisticsAPI,
        pricingAPI,
        subscriptionsAPI,
        ordersAPI,
        adminAPI,
        settingsAPI,
        statisticsAPI,
      } = await loadApiModule()

      expect(authAPI).toHaveProperty('login')
      expect(authAPI).toHaveProperty('logout')
      expect(authAPI).toHaveProperty('getMe')
      expect(authAPI).toHaveProperty('setSecurityQuestion')
      expect(productsAPI).toHaveProperty('getAll')
      expect(logisticsAPI).toHaveProperty('batchDelete')
      expect(pricingAPI).toHaveProperty('calculate')
      expect(subscriptionsAPI).toHaveProperty('getCurrent')
      expect(ordersAPI).toHaveProperty('getAll')
      expect(adminAPI).toHaveProperty('getUsers')
      expect(settingsAPI).toHaveProperty('getBackupStats')
      expect(statisticsAPI).toHaveProperty('getOverview')
    })

    it('setSecurityQuestion posts question and answer', async () => {
      const { authAPI } = await loadApiModule()
      mocks.mockApiInstance.post.mockResolvedValue({ success: true, message: 'ok' })

      await expect(authAPI.setSecurityQuestion('pet', 'fluffy')).resolves.toEqual({ success: true, message: 'ok' })
      expect(mocks.mockApiInstance.post).toHaveBeenCalledWith('/auth/security-question', { question: 'pet', answer: 'fluffy' })
    })
  })
})
