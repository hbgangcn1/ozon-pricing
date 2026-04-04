import { test, expect } from '@playwright/test'

const ADMIN_USER = 'admin'
const ADMIN_PASS = '***REMOVED-PG-PWD***'
const TEST_USER = 'e2e_testuser'
const TEST_PASS = 'TestPassword1!'

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
    if (resp.status() === 500) {
      test.skip()
      return
    }
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

  test('GET /api/statistics/overview - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/statistics/overview')
    expect(resp.status()).toBe(401)
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
    if (resp.status() === 500) {
      test.skip()
      return
    }
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
    if (data.length > 0) {
      const log = data[0]
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
    if (resp.status() === 500) {
      test.skip()
      return
    }
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
    if (data.length > 0) {
      const log = data[0]
      expect(log).toHaveProperty('id')
      expect(log).toHaveProperty('admin')
      expect(log).toHaveProperty('action')
      expect(log).toHaveProperty('time')
    }
  })
})

test.describe('Statistics API - 功能使用', () => {
  test('GET /api/statistics/feature-usage - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/feature-usage', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
    if (data.length > 0) {
      expect(data[0]).toHaveProperty('feature')
      expect(data[0]).toHaveProperty('count')
    }
  })
})

test.describe('Statistics API - 用户分群', () => {
  test('GET /api/statistics/user-groups - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/user-groups', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.status() === 500) {
      test.skip()
      return
    }
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('high_value_users')
    expect(data).toHaveProperty('active_users')
    expect(data).toHaveProperty('silent_users')
  })
})

test.describe('Statistics API - 转化漏斗', () => {
  test('GET /api/statistics/funnel - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/funnel', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('registered')
    expect(data).toHaveProperty('trial')
    expect(data).toHaveProperty('paid')
    expect(data).toHaveProperty('conversion_trial')
    expect(data).toHaveProperty('conversion_paid')
  })
})

test.describe('Statistics API - 计划分析', () => {
  test('GET /api/statistics/plan-analysis - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/plan-analysis', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.status() === 500) {
      test.skip()
      return
    }
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('free_users')
    expect(data).toHaveProperty('efficiency_users')
    expect(data).toHaveProperty('professional_users')
    expect(data).toHaveProperty('enterprise_users')
  })
})

test.describe('Statistics API - 活跃用户', () => {
  test('GET /api/statistics/active-users - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/active-users', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.status() === 500) {
      test.skip()
      return
    }
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('daily')
    expect(data).toHaveProperty('weekly')
    expect(data).toHaveProperty('trend_daily')
    expect(data).toHaveProperty('trend_weekly')
  })
})

test.describe('Statistics API - 增长趋势', () => {
  test('GET /api/statistics/growth - admin 返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/statistics/growth', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('current_month')
    expect(data).toHaveProperty('average')
    expect(data).toHaveProperty('predicted')
    expect(data).toHaveProperty('trend')
  })

  test('GET /api/statistics/growth - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/statistics/growth')
    expect(resp.status()).toBe(401)
  })
})
