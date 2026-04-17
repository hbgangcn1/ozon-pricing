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

import {
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
    it('api client is configured with withCredentials', () => {
      expect(axios.create).toHaveBeenCalledWith(
        expect.objectContaining({ withCredentials: true })
      )
    })

    it('does not register a request interceptor', () => {
      expect(mockRequestUse).not.toHaveBeenCalled()
    })

    it('response interceptor returns response.data on success', () => {
      const resSuccessInterceptor = mockResponseUse.mock.calls[0][0]
      const mockResponse = { data: { foo: 'bar' }, status: 200 }
      
      const result = resSuccessInterceptor(mockResponse)
      expect(result).toEqual({ foo: 'bar' })
    })

    it('response interceptor clears api_user and redirects to /login on 401 when not on /login page', async () => {
      localStorage.setItem('api_user', 'user')
      window.location.pathname = '/dashboard'
      
      const resErrorInterceptor = mockResponseUse.mock.calls[0][1]
      const mockError = { response: { status: 401 } }
      
      await expect(resErrorInterceptor(mockError)).rejects.toEqual(mockError)
      
      expect(localStorage.getItem('api_user')).toBeNull()
      expect(window.location.href).toBe('/login')
    })

    it('response interceptor does NOT clear storage or redirect on 401 when on /login page', async () => {
      localStorage.setItem('api_user', 'user')
      window.location.pathname = '/login'
      window.location.href = 'http://localhost/login'
      
      const resErrorInterceptor = mockResponseUse.mock.calls[0][1]
      const mockError = { response: { status: 401 } }
      
      await expect(resErrorInterceptor(mockError)).rejects.toEqual(mockError)
      
      expect(localStorage.getItem('api_user')).toBe('user')
      expect(window.location.href).toBe('http://localhost/login')
    })

    it('response interceptor rejects with error on non-401 error', async () => {
      window.location.pathname = '/dashboard'
      
      const resErrorInterceptor = mockResponseUse.mock.calls[0][1]
      const mockError = { response: { status: 500 } }
      
      await expect(resErrorInterceptor(mockError)).rejects.toEqual(mockError)
      
      expect(window.location.href).toBe('')
    })
  })
  
  describe('logoutUser', () => {
    it('removes api_user from localStorage and redirects to /login', () => {
      localStorage.setItem('api_user', 'user')
      
      logoutUser()
      
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
