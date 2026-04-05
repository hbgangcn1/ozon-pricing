import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'

const { mockRequestUse, mockResponseUse } = vi.hoisted(() => ({
  mockRequestUse: vi.fn(),
  mockResponseUse: vi.fn()
}))

vi.mock('axios', () => {
  return {
    default: {
      create: vi.fn(() => ({
        interceptors: {
          request: { use: mockRequestUse },
          response: { use: mockResponseUse },
        },
        post: vi.fn(),
        get: vi.fn(),
      })),
    },
  }
})

import apiClient, {
  logoutUser,
  authAPI,
  productsAPI,
  logisticsAPI,
  pricingAPI,
  subscriptionsAPI,
  ordersAPI,
  adminAPI,
  settingsAPI,
  statisticsAPI,
} from '../services/api'

describe('api.js', () => {
  let originalLocation
  
  beforeEach(() => {
    localStorage.clear()
    
    originalLocation = window.location
    delete window.location
    window.location = { href: '', pathname: '/' }
  })
  
  afterEach(() => {
    window.location = originalLocation
  })

  describe('Interceptors', () => {
    it('request interceptor adds Authorization header if token exists', () => {
      localStorage.setItem('api_token', 'test-token-123')
      const reqInterceptor = mockRequestUse.mock.calls[0][0]
      const config = { headers: {} }
      
      const updatedConfig = reqInterceptor(config)
      expect(updatedConfig.headers.Authorization).toBe('Bearer test-token-123')
    })

    it('request interceptor does not add Authorization header if no token', () => {
      const reqInterceptor = mockRequestUse.mock.calls[0][0]
      const config = { headers: {} }
      
      const updatedConfig = reqInterceptor(config)
      expect(updatedConfig.headers.Authorization).toBeUndefined()
    })

    it('response interceptor returns response.data on success', () => {
      const resSuccessInterceptor = mockResponseUse.mock.calls[0][0]
      const mockResponse = { data: { foo: 'bar' }, status: 200 }
      
      const result = resSuccessInterceptor(mockResponse)
      expect(result).toEqual({ foo: 'bar' })
    })

    it('response interceptor clears storage and redirects to /login on 401 when not on /login page', async () => {
      localStorage.setItem('api_token', 'token')
      localStorage.setItem('api_user', 'user')
      window.location.pathname = '/dashboard'
      
      const resErrorInterceptor = mockResponseUse.mock.calls[0][1]
      const mockError = { response: { status: 401 } }
      
      await expect(resErrorInterceptor(mockError)).rejects.toEqual(mockError)
      
      expect(localStorage.getItem('api_token')).toBeNull()
      expect(localStorage.getItem('api_user')).toBeNull()
      expect(window.location.href).toBe('/login')
    })

    it('response interceptor does NOT clear storage or redirect on 401 when on /login page', async () => {
      localStorage.setItem('api_token', 'token')
      localStorage.setItem('api_user', 'user')
      window.location.pathname = '/login'
      window.location.href = 'http://localhost/login'
      
      const resErrorInterceptor = mockResponseUse.mock.calls[0][1]
      const mockError = { response: { status: 401 } }
      
      await expect(resErrorInterceptor(mockError)).rejects.toEqual(mockError)
      
      expect(localStorage.getItem('api_token')).toBe('token')
      expect(localStorage.getItem('api_user')).toBe('user')
      expect(window.location.href).toBe('http://localhost/login')
    })

    it('response interceptor rejects with error on non-401 error', async () => {
      localStorage.setItem('api_token', 'token')
      window.location.pathname = '/dashboard'
      
      const resErrorInterceptor = mockResponseUse.mock.calls[0][1]
      const mockError = { response: { status: 500 } }
      
      await expect(resErrorInterceptor(mockError)).rejects.toEqual(mockError)
      
      expect(localStorage.getItem('api_token')).toBe('token')
      expect(window.location.href).toBe('')
    })
  })
  
  describe('logoutUser', () => {
    it('removes token and user from localStorage and redirects to /login', () => {
      localStorage.setItem('api_token', 'token')
      localStorage.setItem('api_user', 'user')
      
      logoutUser()
      
      expect(localStorage.getItem('api_token')).toBeNull()
      expect(localStorage.getItem('api_user')).toBeNull()
      expect(window.location.href).toBe('/login')
    })
  })

  describe('API Namespaces Exists', () => {
    it('exports correctly structured API namespaces', () => {
      expect(authAPI).toHaveProperty('login')
      expect(authAPI).toHaveProperty('logout')
      expect(authAPI).toHaveProperty('getMe')
      
      expect(productsAPI).toHaveProperty('getAll')
      expect(logisticsAPI).toHaveProperty('batchDelete')
      expect(pricingAPI).toHaveProperty('calculate')
      expect(subscriptionsAPI).toHaveProperty('getCurrent')
      expect(ordersAPI).toHaveProperty('getAll')
      expect(adminAPI).toHaveProperty('getUsers')
      expect(settingsAPI).toHaveProperty('getBackupStats')
      expect(statisticsAPI).toHaveProperty('getOverview')
    })
  })
})
