import { test, expect } from '@playwright/test'
import { TEST_ADMIN, TEST_USER as TEST_USER_DATA } from '../fixtures/test-data.js'

const ADMIN_USER = TEST_ADMIN.username
const ADMIN_PASS = TEST_ADMIN.password
const TEST_USER = TEST_USER_DATA.username
const TEST_PASS = TEST_USER_DATA.password

/**
 * 通过 API 登录获取 token
 */
async function getToken(request, username, password) {
  const resp = await request.post('/api/auth/login', {
    data: { username, password },
  })
  if (!resp.ok()) return null
  const data = await resp.json()
  return data.access_token
}

/**
 * 构造带 Authorization header 的请求头
 */
function authHeaders(token) {
  return { Authorization: `Bearer ${token}` }
}

test.describe('Auth API - 登录', () => {
  test('POST /api/auth/login - 正确凭据返回 200 和 token', async ({ request }) => {
    const resp = await request.post('/api/auth/login', {
      data: { username: ADMIN_USER, password: ADMIN_PASS },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('access_token')
    expect(typeof data.access_token).toBe('string')
    expect(data.access_token.length).toBeGreaterThan(10)
    expect(data).toHaveProperty('user')
    expect(data.user).toHaveProperty('id')
    expect(data.user).toHaveProperty('username')
    expect(data.user).toHaveProperty('role')
    expect(data.user.username).toBe(ADMIN_USER)
  })

  test('POST /api/auth/login - 错误密码返回 401', async ({ request }) => {
    const resp = await request.post('/api/auth/login', {
      data: { username: ADMIN_USER, password: 'WrongPassword123!' },
    })
    expect(resp.status()).toBe(401)
    const data = await resp.json()
    expect(data).toHaveProperty('detail')
  })

  test('POST /api/auth/login - 不存在用户返回 401', async ({ request }) => {
    const resp = await request.post('/api/auth/login', {
      data: { username: 'nonexistent_user_xyz', password: 'SomePassword123!' },
    })
    expect(resp.status()).toBe(401)
  })

  test('POST /api/auth/login - 缺少字段返回 422', async ({ request }) => {
    const resp = await request.post('/api/auth/login', {
      data: { username: ADMIN_USER },
    })
    expect(resp.status()).toBe(422)
  })

  test('POST /api/auth/login - 测试用户登录', async ({ request }) => {
    const resp = await request.post('/api/auth/login', {
      data: { username: TEST_USER, password: TEST_PASS },
    })
    // 测试用户可能存在也可能不存在，只要是已知状态即可
    expect([200, 401]).toContain(resp.status())
    if (resp.status() === 200) {
      const data = await resp.json()
      expect(data).toHaveProperty('access_token')
    }
  })
})

test.describe('Auth API - 当前用户信息', () => {
  test('GET /api/auth/me - 有效 token 返回 200 和用户信息', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    expect(token).not.toBeNull()

    const resp = await request.get('/api/auth/me', {
      headers: authHeaders(token),
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('id')
    expect(data).toHaveProperty('username')
    expect(data).toHaveProperty('role')
    expect(data).toHaveProperty('user_type')
    expect(data).toHaveProperty('remaining_calculations')
    expect(data.username).toBe(ADMIN_USER)
    expect(data.role).toBe('admin')
  })

  test('GET /api/auth/me - 无 token 返回 401', async ({ request }) => {
    const resp = await request.get('/api/auth/me')
    expect(resp.status()).toBe(401)
  })

  test('GET /api/auth/me - 无效 token 返回 401', async ({ request }) => {
    const resp = await request.get('/api/auth/me', {
      headers: { Authorization: 'Bearer invalid.token.here' },
    })
    expect(resp.status()).toBe(401)
  })

  test('GET /api/auth/me - user_type 是字符串', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.get('/api/auth/me', {
      headers: authHeaders(token),
    })
    const data = await resp.json()
    expect(typeof data.user_type).toBe('string')
  })
})

test.describe('Auth API - 登出', () => {
  test('POST /api/auth/logout - 返回 200', async ({ request }) => {
    const resp = await request.post('/api/auth/logout')
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('message')
  })

  test('POST /api/auth/logout - 有 token 也返回 200', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.post('/api/auth/logout', {
      headers: authHeaders(token),
    })
    expect(resp.status()).toBe(200)
  })
})

test.describe('Auth API - 注册', () => {
  const createdUserIds = [];

  test.afterAll(async ({ request }) => {
    if (createdUserIds.length === 0) return;
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS);
    if (!token) return;
    for (const uid of createdUserIds) {
      try {
        await request.delete(`/api/admin/users/${uid}`, {
          headers: authHeaders(token),
        });
      } catch { }
    }
  });

  test('POST /api/auth/register - 注册关闭时返回 403', async ({ request }) => {
    const adminToken = await getToken(request, ADMIN_USER, ADMIN_PASS)
    await request.put('/api/settings/open-registration?enabled=false', {
      headers: authHeaders(adminToken),
    })

    // get_db auto-commit 在 response 发送后才执行，需等待设置真正持久化
    // 轮询注册接口本身，直到返回403
    let lastStatus = 0
    for (let i = 0; i < 20; i++) {
      await new Promise(r => setTimeout(r, 300))
      const probe = await request.post('/api/auth/register', {
        data: {
          username: `probe_closed_${Date.now()}`,
          password: 'ValidPassword123!',
          security_question: 'probe',
          security_answer: 'probe',
        },
      })
      lastStatus = probe.status()
      if (lastStatus === 403) break
    }
    expect(lastStatus).toBe(403)
  })

  test('POST /api/auth/register - 注册开放时弱密码返回 400', async ({ request }) => {
    // 开启注册
    const adminToken = await getToken(request, ADMIN_USER, ADMIN_PASS)
    await request.put('/api/settings/open-registration?enabled=true', {
      headers: authHeaders(adminToken),
    })

    const resp = await request.post('/api/auth/register', {
      data: {
        username: 'newuser_weakpwd',
        password: 'Weakpwd1!',
        security_question: 'pet',
        security_answer: 'dog',
      },
    })
    expect(resp.status()).toBe(400)
  })

  test('POST /api/auth/register - 注册开放时无效用户名返回 400', async ({ request }) => {
    const adminToken = await getToken(request, ADMIN_USER, ADMIN_PASS)
    await request.put('/api/settings/open-registration?enabled=true', {
      headers: authHeaders(adminToken),
    })

    const resp = await request.post('/api/auth/register', {
      data: {
        username: 'ab@invalid', // 含非法字符
        password: 'ValidPassword123!X',
        security_question: 'pet',
        security_answer: 'dog',
      },
    })
    expect(resp.status()).toBe(400)
  })

  test('POST /api/auth/register - 注册开放时成功注册并关闭注册', async ({ request }) => {
    const adminToken = await getToken(request, ADMIN_USER, ADMIN_PASS)
    await request.put('/api/settings/open-registration?enabled=true', {
      headers: authHeaders(adminToken),
    })

    const uniqueUser = `e2e_api_${Date.now()}`
    const resp = await request.post('/api/auth/register', {
      data: {
        username: uniqueUser,
        password: 'ValidPassword123!X',
        security_question: 'pet name',
        security_answer: 'Buddy',
      },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('access_token')
    expect(data).toHaveProperty('user')
    expect(data.user.username).toBe(uniqueUser)
    expect(data.user.role).toBe('user')
    if (data.user.id) createdUserIds.push(data.user.id)

    await request.put('/api/settings/open-registration?enabled=false', {
      headers: authHeaders(adminToken),
    })
  })
})

test.describe('Auth API - 修改密码', () => {
  test('POST /api/auth/change-password - 无 token 返回 401', async ({ request }) => {
    const resp = await request.post('/api/auth/change-password', {
      data: {
        current_password: 'OldPassword123!',
        new_password: 'NewPassword456@X',
      },
    })
    expect(resp.status()).toBe(401)
  })

  test('POST /api/auth/change-password - 错误的当前密码返回 401', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.post('/api/auth/change-password', {
      headers: authHeaders(token),
      data: {
        current_password: 'WrongCurrentPass123!',
        new_password: 'NewValidPassword456@X',
      },
    })
    expect(resp.status()).toBe(401)
  })

  test('POST /api/auth/change-password - 新密码不符合强度要求返回 400', async ({ request }) => {
    const token = await getToken(request, ADMIN_USER, ADMIN_PASS)
    const resp = await request.post('/api/auth/change-password', {
      headers: authHeaders(token),
      data: {
        current_password: ADMIN_PASS,
        new_password: 'weakpass',
      },
    })
    expect(resp.status()).toBe(400)
    const data = await resp.json()
    expect(data).toHaveProperty('detail')
  })
})
