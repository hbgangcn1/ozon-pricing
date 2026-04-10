import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

const { mockRequestUse, mockResponseUse } = vi.hoisted(() => ({
  mockRequestUse: vi.fn(),
  mockResponseUse: vi.fn(),
}))

const mockDelete = vi.hoisted(() => vi.fn())
const mockGet = vi.hoisted(() => vi.fn())
const mockPost = vi.hoisted(() => vi.fn())

vi.mock('axios', () => {
  return {
    default: {
      create: vi.fn(() => ({
        interceptors: {
          request: { use: mockRequestUse },
          response: { use: mockResponseUse },
        },
        get: mockGet,
        post: mockPost,
        put: vi.fn(),
        patch: vi.fn(),
        delete: mockDelete,
      })),
    },
  }
})

import { logisticsPoolAPI } from '../services/api'

describe('logisticsPoolAPI', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('deleteAll', () => {
    it('calls DELETE /logistics-pool/all', async () => {
      mockDelete.mockResolvedValue({ data: { message: '已清空公共物流池' } })

      await logisticsPoolAPI.deleteAll()

      expect(mockDelete).toHaveBeenCalledWith('/logistics-pool/all')
    })

    it('correctly propagates successful response', async () => {
      const mockResponse = { message: '已清空公共物流池' }
      mockDelete.mockResolvedValue(mockResponse)

      const result = await logisticsPoolAPI.deleteAll()
      expect(result).toEqual(mockResponse)
    })

    it('propagates errors from the API', async () => {
      const mockError = new Error('Network Error')
      mockError.response = { status: 500, data: { detail: '服务器错误' } }
      mockDelete.mockRejectedValue(mockError)

      await expect(logisticsPoolAPI.deleteAll()).rejects.toThrow('Network Error')
    })
  })

  describe('getAll', () => {
    it('calls GET /logistics-pool with params', async () => {
      mockGet.mockResolvedValue({ items: [], total: 0 })

      await logisticsPoolAPI.getAll({ page: 1, page_size: 20 })

      expect(mockGet).toHaveBeenCalledWith('/logistics-pool', {
        params: { page: 1, page_size: 20 },
      })
    })

    it('works without params', async () => {
      mockGet.mockResolvedValue({ items: [], total: 0 })

      await logisticsPoolAPI.getAll()

      expect(mockGet).toHaveBeenCalledWith('/logistics-pool', {
        params: undefined,
      })
    })
  })

  describe('importXlsx', () => {
    it('calls POST /logistics-pool/import with FormData', async () => {
      const formData = new FormData()
      formData.append('file', new Blob(['test']), 'test.xlsx')
      mockPost.mockResolvedValue({ imported: 5 })

      await logisticsPoolAPI.importXlsx(formData)

      expect(mockPost).toHaveBeenCalledWith(
        '/logistics-pool/import',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      )
    })
  })

  describe('addToMyLogistics', () => {
    it('calls POST /logistics-pool/{id}/add-to-my-logistics', async () => {
      mockPost.mockResolvedValue({ message: '已添加' })

      await logisticsPoolAPI.addToMyLogistics(42)

      expect(mockPost).toHaveBeenCalledWith(
        '/logistics-pool/42/add-to-my-logistics'
      )
    })
  })
})
