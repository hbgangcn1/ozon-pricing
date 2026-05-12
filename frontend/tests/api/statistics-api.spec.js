import { test, expect } from '@playwright/test'
import { TEST_ADMIN, TEST_USER as TEST_USER_DATA } from '../fixtures/test-data.js'

const ADMIN_USER = TEST_ADMIN.username
const ADMIN_PASS = TEST_ADMIN.password
const TEST_USER = TEST_USER_DATA.username
const TEST_PASS = TEST_USER_DATA.password

// Playwright `request` fixture inherits BrowserContext storageState (admin.json
// httpOnly access_token cookie). Backend api/dependencies.py:_extract_token
// prefers cookie over Authorization header and triggers cookie CSRF validation.
// Tests verifying "no auth -> 401" must opt-out of storageState.
const NO_AUTH_STATE = { storageState: { cookies: [], origins: [] } }

async function getToken(request, username, password) {
  const resp = await request.post('/api/auth/login', {
    data: { username, password },
  })
  if (!resp.ok()) return null
  const data = await resp.json()
  return data.access_token
}

test.describe('Statistics API - 概览', () => {
  test('GET /api/statistics/overview - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/overview', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('total_users')
    expect(data).toHaveProperty('active_users')
    expect(data).toHaveProperty('new_users_today')
    expect(data).toHaveProperty('total_orders')
    expect(data).toHaveProperty('total_revenue')
    expect(data).toHaveProperty('pro_users')
    expect(data).toHaveProperty('eff_users')
    expect(data).toHaveProperty('free_users')
  })

  test('GET /api/statistics/overview - 非 admin 返回 403', async ({ request }) => {
    const token = await getToken(request, TEST_USER, TEST_PASS)
    if (!token) {
      test.skip()
      return
    }
    const resp = await request.get('/api/statistics/overview', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(403)
  })
})

test.describe('Statistics API - 留存率', () => {
  test('GET /api/statistics/retention - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/retention', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
    if (data.length > 0) {
      expect(data[0]).toHaveProperty('month')
      expect(data[0]).toHaveProperty('retention')
    }
  })
})

test.describe('Statistics API - 收入', () => {
  test('GET /api/statistics/revenue - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/revenue?months=12', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
    if (data.length > 0) {
      expect(data[0]).toHaveProperty('month')
      expect(data[0]).toHaveProperty('revenue')
    }
  })

  test('GET /api/statistics/revenue - months 参数生效', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/revenue?months=3', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
  })
})

test.describe('Statistics API - 登录日志', () => {
  test('GET /api/statistics/login-logs - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/login-logs?page=1&page_size=20', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('items')
    expect(data).toHaveProperty('total')
    expect(Array.isArray(data.items)).toBeTruthy()
    if (data.items.length > 0) {
      const log = data.items[0]
      expect(log).toHaveProperty('id')
      expect(log).toHaveProperty('username')
      expect(log).toHaveProperty('action')
      expect(log).toHaveProperty('ip')
      expect(log).toHaveProperty('time')
      expect(log).toHaveProperty('status')
    }
  })

  test('GET /api/statistics/login-logs - 非 admin 返回 403', async ({ request }) => {
    const token = await getToken(request, TEST_USER, TEST_PASS)
    if (!token) {
      test.skip()
      return
    }
    const resp = await request.get('/api/statistics/login-logs', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(403)
  })
})

test.describe('Statistics API - 管理员日志', () => {
  test('GET /api/statistics/admin-logs - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/admin-logs?page=1&page_size=20', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('items')
    expect(data).toHaveProperty('total')
    expect(Array.isArray(data.items)).toBeTruthy()
    if (data.items.length > 0) {
      const log = data.items[0]
      expect(log).toHaveProperty('id')
      expect(log).toHaveProperty('admin')
      expect(log).toHaveProperty('action')
      expect(log).toHaveProperty('time')
    }
  })
})

test.describe('Statistics API - 活跃用户', () => {
  test('GET /api/statistics/active-users - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/active-users', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('daily')
    expect(data).toHaveProperty('weekly')
    expect(data).toHaveProperty('trend_daily')
    expect(data).toHaveProperty('trend_weekly')
  })
})

test.describe('Statistics API - 无认证检查 (no storageState)', () => {
  test.use(NO_AUTH_STATE)

  test('GET /api/statistics/overview - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/statistics/overview')
    expect(resp.status()).toBe(401)
  })
})
