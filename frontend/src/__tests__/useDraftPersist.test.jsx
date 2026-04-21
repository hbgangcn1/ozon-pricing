import { act, renderHook } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useDraftPersist } from '../hooks/useDraftPersist'

function createSessionStorageMock() {
  let store = {}

  return {
    getItem: vi.fn((key) => (key in store ? store[key] : null)),
    setItem: vi.fn((key, value) => {
      store[key] = String(value)
    }),
    removeItem: vi.fn((key) => {
      delete store[key]
    }),
    clear: vi.fn(() => {
      store = {}
    }),
    dump: () => ({ ...store }),
  }
}

describe('useDraftPersist', () => {
  let sessionStorageMock

  beforeEach(() => {
    vi.useRealTimers()
    vi.clearAllMocks()
    sessionStorageMock = createSessionStorageMock()
    Object.defineProperty(window, 'sessionStorage', {
      value: sessionStorageMock,
      configurable: true,
      writable: true,
    })
  })

  it('debounces draft persistence', () => {
    vi.useFakeTimers()
    const { rerender } = renderHook(
      ({ value }) => useDraftPersist('pricing-fast', value),
      { initialProps: { value: { unit_price: '', weight_g: '' } } },
    )

    rerender({ value: { unit_price: '10', weight_g: '' } })

    act(() => {
      vi.advanceTimersByTime(349)
    })
    expect(sessionStorageMock.setItem).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1)
    })

    expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
      'draft:pricing-fast',
      JSON.stringify({ unit_price: '10', weight_g: '' }),
    )
  })

  it('does not persist the initial pristine value', () => {
    vi.useFakeTimers()
    renderHook(() => useDraftPersist('pricing-fast', { unit_price: '', weight_g: '' }))

    act(() => {
      vi.advanceTimersByTime(400)
    })

    expect(sessionStorageMock.setItem).not.toHaveBeenCalled()
    expect(sessionStorageMock.removeItem).not.toHaveBeenCalled()
  })

  it('excludes sensitive fields before saving', () => {
    vi.useFakeTimers()
    const { rerender } = renderHook(
      ({ value }) => useDraftPersist('register', value, {
        excludeFields: ['password', 'confirmPassword', 'security_answer'],
      }),
      {
        initialProps: {
          value: {
            username: '',
            password: '',
            confirmPassword: '',
            security_answer: '',
          },
        },
      },
    )

    rerender({
      value: {
        username: 'alice',
        password: 'Secret123!',
        confirmPassword: 'Secret123!',
        security_answer: 'private',
      },
    })

    act(() => {
      vi.advanceTimersByTime(350)
    })

    expect(sessionStorageMock.setItem).toHaveBeenCalledWith(
      'draft:register',
      JSON.stringify({ username: 'alice' }),
    )
  })

  it('swallows QuotaExceededError and warns once', () => {
    vi.useFakeTimers()
    const consoleWarn = vi.spyOn(console, 'warn').mockImplementation(() => {})
    sessionStorageMock.setItem.mockImplementation(() => {
      const error = new Error('quota')
      error.name = 'QuotaExceededError'
      throw error
    })

    const { rerender } = renderHook(
      ({ value }) => useDraftPersist('pricing-fast', value),
      { initialProps: { value: { unit_price: '', weight_g: '' } } },
    )

    expect(() => {
      rerender({ value: { unit_price: '15', weight_g: '300' } })
      act(() => {
        vi.advanceTimersByTime(350)
      })
    }).not.toThrow()

    expect(consoleWarn).toHaveBeenCalledWith(
      'Draft persistence skipped for draft:pricing-fast: quota exceeded',
    )
  })

  it('is a complete no-op when disabled', () => {
    vi.useFakeTimers()
    const { result, rerender } = renderHook(
      ({ value }) => useDraftPersist('register', value, { enabled: false }),
      { initialProps: { value: { username: '' } } },
    )

    rerender({ value: { username: 'disabled-user' } })
    act(() => {
      vi.advanceTimersByTime(400)
    })

    expect(result.current.hasDraft()).toBe(false)
    expect(result.current.loadDraft()).toBeNull()
    act(() => {
      result.current.clearDraft()
    })
    expect(sessionStorageMock.getItem).not.toHaveBeenCalled()
    expect(sessionStorageMock.setItem).not.toHaveBeenCalled()
    expect(sessionStorageMock.removeItem).not.toHaveBeenCalled()
  })

  it('supports loadDraft, clearDraft and hasDraft', () => {
    sessionStorageMock.setItem(
      'draft:logistics-page',
      JSON.stringify({ form: { name: '测试物流' }, dialogOpen: true }),
    )

    const { result } = renderHook(() => useDraftPersist('logistics-page', { form: { name: '' } }))

    expect(result.current.hasDraft()).toBe(true)
    expect(result.current.loadDraft()).toEqual({
      form: { name: '测试物流' },
      dialogOpen: true,
    })

    act(() => {
      result.current.clearDraft()
    })

    expect(result.current.hasDraft()).toBe(false)
    expect(sessionStorageMock.removeItem).toHaveBeenCalledWith('draft:logistics-page')
  })
})
