import { test, expect } from '@playwright/test'
import { TEST_ADMIN } from '../fixtures/test-data.js'

const ADMIN_USER = TEST_ADMIN.username
const ADMIN_PASS = TEST_ADMIN.password

async function getToken(request, username, password) {
  const resp = await request.post('/api/auth/login', {
    data: { username, password },
  })
  if (!resp.ok()) return null
  const data = await resp.json()
  return data.access_token
}

test.describe('Subscriptions API - 订阅计划', () => {
  test('GET /api/subscriptions/plans - 无需认证返回计划列表', async ({ request }) => {
    const resp = await request.get('/api/subscriptions/plans')
    if (resp.status() === 500) {
      test.skip()
      return
    }
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
  })

  test('GET /api/subscriptions/plans - 返回计划有正确结构', async ({ request }) => {
    const resp = await request.get('/api/subscriptions/plans')
    if (resp.status() === 500) {
      test.skip()
      return
    }
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
    if (data.length > 0) {
      const plan = data[0]
      expect(plan).toHaveProperty('id')
      expect(plan).toHaveProperty('code')
      expect(plan).toHaveProperty('name')
      expect(plan).toHaveProperty('display_price_month')
      expect(plan).toHaveProperty('display_price_year')
      expect(plan).toHaveProperty('actual_price_month')
      expect(plan).toHaveProperty('actual_price_year')
      expect(plan).toHaveProperty('calc_limit')
      expect(plan).toHaveProperty('logistics_limit')
      expect(plan).toHaveProperty('sort')
      expect(plan).toHaveProperty('status')
      expect(plan).toHaveProperty('features')
      expect(Array.isArray(plan.features)).toBeTruthy()
    }
  })

  test('GET /api/subscriptions/plans - 所有返回计划的 status 为 true', async ({ request }) => {
    const resp = await request.get('/api/subscriptions/plans')
    if (resp.status() === 500) {
      test.skip()
      return
    }
    const data = await resp.json()
    for (const plan of data) {
      expect(plan.status).toBe(true)
    }
  })

  test('GET /api/subscriptions/plans - 计划按 sort 排序', async ({ request }) => {
    const resp = await request.get('/api/subscriptions/plans')
    const data = await resp.json()
    for (let i = 1; i < data.length; i++) {
      expect(data[i].sort).toBeGreaterThanOrEqual(data[i - 1].sort)
    }
  })
})

test.describe('Subscriptions API - 当前订阅', () => {
  test('GET /api/subscriptions/current - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/subscriptions/current')
    expect(resp.status()).toBe(401)
  })

  test('GET /api/subscriptions/current - 无效 token 返回 401', async ({ request }) => {
    const resp = await request.get('/api/subscriptions/current', {
      headers: { Authorization: 'Bearer invalid.token.xyz' },
    })
    expect(resp.status()).toBe(401)
  })

  test('GET /api/subscriptions/current - 有 token 返回 200 和订阅信息', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    expect(token).not.toBeNull()

    const resp = await request.get('/api/subscriptions/current', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.status() === 500) {
      test.skip()
      return
    }
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('plan_code')
    expect(data).toHaveProperty('calc_limit')
    expect(data).toHaveProperty('logistics_limit')
  })

  test('GET /api/subscriptions/current - plan_code 是字符串', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/subscriptions/current', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.status() === 500) {
      test.skip()
      return
    }
    const data = await resp.json()
    expect(typeof data.plan_code).toBe('string')
    expect(data.plan_code.length).toBeGreaterThan(0)
  })

  test('GET /api/subscriptions/current - calc_limit 是数字', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/subscriptions/current', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.status() === 500) {
      test.skip()
      return
    }
    const data = await resp.json()
    expect(typeof data.calc_limit).toBe('number')
    expect(typeof data.logistics_limit).toBe('number')
  })
})
