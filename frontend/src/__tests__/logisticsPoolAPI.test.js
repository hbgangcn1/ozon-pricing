import { describe, it, expect, vi, beforeEach } from 'vitest'

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

      expect(mockDelete).toHaveBeenCalledWith('/logistics-pool/all', {})
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
        '/logistics-pool/42/add-to-my-logistics',
        null,
        {}
      )
    })
  })

  describe('batchAddToMyLogistics', () => {
    it('calls POST /logistics-pool/batch-add-to-my-logistics with ids', async () => {
      mockPost.mockResolvedValue({ added: 2, not_found: [], new_ids: [1, 2] })

      await logisticsPoolAPI.batchAddToMyLogistics([10, 11])

      expect(mockPost).toHaveBeenCalledWith(
        '/logistics-pool/batch-add-to-my-logistics',
        { ids: [10, 11] },
        {}
      )
    })

    it('correctly propagates successful response', async () => {
      const mockResponse = { added: 3, not_found: [99], new_ids: [1, 2, 3] }
      mockPost.mockResolvedValue(mockResponse)

      const result = await logisticsPoolAPI.batchAddToMyLogistics([1, 2, 3, 99])
      expect(result).toEqual(mockResponse)
    })

    it('propagates errors from the API', async () => {
      const mockError = new Error('Bad Request')
      mockError.response = { status: 400, data: { detail: 'ids 不能为空' } }
      mockPost.mockRejectedValue(mockError)

      await expect(logisticsPoolAPI.batchAddToMyLogistics([])).rejects.toThrow('Bad Request')
    })
  })

  describe('batchAddToMyLogistics — batching logic simulation', () => {
    // Simulates the batching logic from LogisticsPoolPage.handleBatchAddToMyLogistics
    const BATCH_SIZE = 200

    async function simulateBatchAdd(allIds) {
      let totalAdded = 0
      let totalNotFound = 0

      for (let i = 0; i < allIds.length; i += BATCH_SIZE) {
        const batch = allIds.slice(i, i + BATCH_SIZE)
        const result = await logisticsPoolAPI.batchAddToMyLogistics(batch)
        const data = result?.data || result
        totalAdded += data?.added || 0
        totalNotFound += data?.not_found?.length || 0
      }
      return { totalAdded, totalNotFound }
    }

    it('sends single batch for <= 200 ids', async () => {
      const ids = Array.from({ length: 150 }, (_, i) => i + 1)
      mockPost.mockResolvedValue({ added: 150, not_found: [], new_ids: ids })

      const result = await simulateBatchAdd(ids)

      expect(mockPost).toHaveBeenCalledTimes(1)
      expect(result.totalAdded).toBe(150)
      expect(result.totalNotFound).toBe(0)
    })

    it('sends exactly 200 ids in single batch', async () => {
      const ids = Array.from({ length: 200 }, (_, i) => i + 1)
      mockPost.mockResolvedValue({ added: 200, not_found: [], new_ids: ids })

      const result = await simulateBatchAdd(ids)

      expect(mockPost).toHaveBeenCalledTimes(1)
      expect(result.totalAdded).toBe(200)
    })

    it('splits 465 ids into 3 batches (200+200+65)', async () => {
      const ids = Array.from({ length: 465 }, (_, i) => i + 1)
      mockPost
        .mockResolvedValueOnce({ added: 200, not_found: [], new_ids: [] })
        .mockResolvedValueOnce({ added: 200, not_found: [], new_ids: [] })
        .mockResolvedValueOnce({ added: 65, not_found: [], new_ids: [] })

      const result = await simulateBatchAdd(ids)

      expect(mockPost).toHaveBeenCalledTimes(3)
      const firstBatchIds = mockPost.mock.calls[0][1].ids
      const secondBatchIds = mockPost.mock.calls[1][1].ids
      const thirdBatchIds = mockPost.mock.calls[2][1].ids
      expect(firstBatchIds.length).toBe(200)
      expect(secondBatchIds.length).toBe(200)
      expect(thirdBatchIds.length).toBe(65)
      expect(result.totalAdded).toBe(465)
      expect(result.totalNotFound).toBe(0)
    })

    it('accumulates not_found across batches', async () => {
      const ids = Array.from({ length: 400 }, (_, i) => i + 1)
      mockPost
        .mockResolvedValueOnce({ added: 198, not_found: [1, 2], new_ids: [] })
        .mockResolvedValueOnce({ added: 195, not_found: [201, 202, 203, 204, 205], new_ids: [] })

      const result = await simulateBatchAdd(ids)

      expect(mockPost).toHaveBeenCalledTimes(2)
      expect(result.totalAdded).toBe(393)
      expect(result.totalNotFound).toBe(7)
    })

    it('stops on first batch failure', async () => {
      const ids = Array.from({ length: 400 }, (_, i) => i + 1)
      mockPost
        .mockResolvedValueOnce({ added: 200, not_found: [], new_ids: [] })
        .mockRejectedValueOnce(new Error('Server Error'))

      await expect(simulateBatchAdd(ids)).rejects.toThrow('Server Error')
      expect(mockPost).toHaveBeenCalledTimes(2)
    })
  })
})
