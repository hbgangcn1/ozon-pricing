import { test, expect } from '@playwright/test'
import { TEST_ADMIN, TEST_USER as TEST_USER_DATA } from '../fixtures/test-data.js'

const ADMIN_USER = TEST_ADMIN.username
const ADMIN_PASS = TEST_ADMIN.password
const TEST_USER = TEST_USER_DATA.username
const TEST_PASS = TEST_USER_DATA.password

const NO_AUTH_STATE = { storageState: { cookies: [], origins: [] } }

async function getToken(request, username, password) {
  const resp = await request.post('/api/auth/login', {
    data: { username, password },
  })
  if (!resp.ok()) return null
  const data = await resp.json()
  return data.access_token
}

test.describe('Orders API - 订单接口', () => {
  test.describe('无认证检查', () => {
    test.use(NO_AUTH_STATE)

    test('GET /api/orders - 无认证返回 401', async ({ request }) => {
      const resp = await request.get('/api/orders')
      expect(resp.status()).toBe(401)
    })
  })

  test('GET /api/orders - 无效 token 返回 401', async ({ request }) => {
    const resp = await request.get('/api/orders', {
      headers: { Authorization: 'Bearer invalid.token.xyz' },
    })
    expect(resp.status()).toBe(401)
  })

  test('GET /api/orders - admin 有 token 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    expect(token).not.toBeNull()

    const resp = await request.get('/api/orders', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('orders')
    expect(data).toHaveProperty('total')
    expect(Array.isArray(data.orders)).toBeTruthy()
  })

  test('GET /api/orders - 返回列表（可为空数组）', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/orders', {
      headers: { Authorization: `Bearer ${token}` },
    })
    const data = await resp.json()
    expect(Array.isArray(data.orders)).toBeTruthy()
  })

  test('GET /api/orders - 订单有正确结构（如果有数据）', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/orders', {
      headers: { Authorization: `Bearer ${token}` },
    })
    const data = await resp.json()
    if (data.orders && data.orders.length > 0) {
      const order = data.orders[0]
      expect(order).toHaveProperty('id')
      expect(order).toHaveProperty('order_id')
      expect(order).toHaveProperty('order_type')
      expect(order).toHaveProperty('plan_name')
      expect(order).toHaveProperty('amount')
      expect(order).toHaveProperty('status')
      expect(order).toHaveProperty('created_at')
    }
  })

  test('GET /api/orders - 测试用户登录后获取订单', async ({ request }) => {
    const token = await getToken(request, TEST_USER, TEST_PASS)
    if (!token) {
      test.skip()
      return
    }
    const resp = await request.get('/api/orders', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data.orders)).toBeTruthy()
  })
})
