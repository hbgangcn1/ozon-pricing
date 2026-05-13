import { describe, it, expect } from 'vitest'
import { getApiErrorMessage } from '@/lib/api-error'

describe('getApiErrorMessage', () => {
  it('returns string detail as-is', () => {
    expect(
      getApiErrorMessage({ response: { data: { detail: 'ids 不能为空' } } }, 'fb')
    ).toBe('ids 不能为空')
  })

  it('extracts first msg from FastAPI 422 array detail', () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              type: 'too_long',
              loc: ['body', 'ids'],
              msg: 'List should have at most 50 items',
              input: [],
              ctx: { max_length: 50 },
            },
          ],
        },
      },
    }
    expect(getApiErrorMessage(error, 'fb')).toBe('List should have at most 50 items')
  })

  it('returns 网络连接失败 for Network Error', () => {
    expect(getApiErrorMessage({ message: 'Network Error' }, 'fb')).toBe('网络连接失败')
  })

  it('returns 网络连接失败 for ECONNREFUSED', () => {
    expect(
      getApiErrorMessage({ message: 'connect ECONNREFUSED 127.0.0.1:8003' }, 'fb')
    ).toBe('网络连接失败')
  })

  it('returns fallback for unknown shape', () => {
    expect(getApiErrorMessage({}, 'fb')).toBe('fb')
  })

  it('returns fallback for null', () => {
    expect(getApiErrorMessage(null, 'fb')).toBe('fb')
  })

  it('returns fallback for undefined', () => {
    expect(getApiErrorMessage(undefined, 'fb')).toBe('fb')
  })

  it('returns fallback for object detail (defensive)', () => {
    expect(
      getApiErrorMessage({ response: { data: { detail: { some: 'object' } } } }, 'fb')
    ).toBe('fb')
  })

  it('returns fallback for empty array detail', () => {
    expect(getApiErrorMessage({ response: { data: { detail: [] } } }, 'fb')).toBe('fb')
  })

  it('uses default fallback "操作失败" when none provided', () => {
    expect(getApiErrorMessage({})).toBe('操作失败')
  })

  it('returns fallback when array first item has non-string msg', () => {
    expect(
      getApiErrorMessage({ response: { data: { detail: [{ msg: 123 }] } } }, 'fb')
    ).toBe('fb')
  })
})
