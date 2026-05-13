import { beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => {
  const mockApiInstance = Object.assign(vi.fn(), {
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    post: vi.fn(),
    get: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    patch: vi.fn(),
  })
  return { mockApiInstance }
})

vi.mock('axios', () => {
  const axiosDefault = Object.assign(vi.fn(), {
    create: vi.fn(() => mocks.mockApiInstance),
    post: vi.fn(),
  })
  return { default: axiosDefault }
})

vi.mock('../stores/authStore', () => ({
  useAuthStore: { getState: vi.fn(() => ({ token: null })) },
}))

vi.mock('sonner', () => ({ toast: { error: vi.fn() } }))

async function loadApi() {
  vi.resetModules()
  return import('../services/api')
}

describe('trialAPI / overflowAPI endpoint contracts', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.mockApiInstance.post.mockResolvedValue({ ok: true })
    mocks.mockApiInstance.get.mockResolvedValue({ ok: true })
  })

  it('trialAPI.claim posts /subscriptions/trial/claim with no body', async () => {
    const { trialAPI } = await loadApi()
    await trialAPI.claim()
    expect(mocks.mockApiInstance.post).toHaveBeenCalledTimes(1)
    expect(mocks.mockApiInstance.post).toHaveBeenCalledWith('/subscriptions/trial/claim', null, {})
  })

  it('trialAPI.getStatus gets /subscriptions/trial/status', async () => {
    const { trialAPI } = await loadApi()
    await trialAPI.getStatus()
    expect(mocks.mockApiInstance.get).toHaveBeenCalledTimes(1)
    expect(mocks.mockApiInstance.get).toHaveBeenCalledWith('/subscriptions/trial/status', expect.any(Object))
  })

  it('overflowAPI.reselect posts /logistics/overflow/reselect with keep_ids body', async () => {
    const { overflowAPI } = await loadApi()
    await overflowAPI.reselect([1, 2, 3])
    expect(mocks.mockApiInstance.post).toHaveBeenCalledTimes(1)
    expect(mocks.mockApiInstance.post).toHaveBeenCalledWith(
      '/logistics/overflow/reselect',
      { keep_ids: [1, 2, 3] },
      {},
    )
  })

  it('overflowAPI.getStatus gets /logistics/overflow/status', async () => {
    const { overflowAPI } = await loadApi()
    await overflowAPI.getStatus()
    expect(mocks.mockApiInstance.get).toHaveBeenCalledTimes(1)
    expect(mocks.mockApiInstance.get).toHaveBeenCalledWith('/logistics/overflow/status', {})
  })
})
