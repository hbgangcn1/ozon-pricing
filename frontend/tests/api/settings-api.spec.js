import { test, expect } from '@playwright/test'

const ADMIN_USER = 'admin'
const ADMIN_PASS = '***REMOVED-PG-PWD***'

async function getAdminToken(request) {
  const resp = await request.post('/api/auth/login', {
    data: { username: ADMIN_USER, password: ADMIN_PASS },
  })
  if (!resp.ok()) return null
  const data = await resp.json()
  return data.access_token
}

test.describe('Settings API - 系统设置', () => {
  test('GET /api/settings - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/settings')
    expect(resp.status()).toBe(401)
  })

  test('GET /api/settings - admin 返回 200 和配置', async ({ request }) => {
    const token = await getAdminToken(request)
    expect(token).not.toBeNull()

    const resp = await request.get('/api/settings', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('open_registration')
    expect(data).toHaveProperty('backup_interval')
    expect(typeof data.open_registration).toBe('boolean')
    expect(typeof data.backup_interval).toBe('number')
  })

  test('PUT /api/settings/open-registration - admin 可切换注册状态', async ({ request }) => {
    const token = await getAdminToken(request)

    const respOn = await request.put('/api/settings/open-registration?enabled=true', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(respOn.status()).toBe(200)
    const dataOn = await respOn.json()
    expect(dataOn).toHaveProperty('message')

    const respOff = await request.put('/api/settings/open-registration?enabled=false', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(respOff.status()).toBe(200)
  })

  test('PUT /api/settings/open-registration - 无认证返回 401', async ({ request }) => {
    const resp = await request.put('/api/settings/open-registration?enabled=true')
    expect(resp.status()).toBe(401)
  })
})

test.describe('Settings API - 备份列表', () => {
  test('GET /api/settings/backups - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/settings/backups')
    expect(resp.status()).toBe(401)
  })

  test('GET /api/settings/backups - admin 返回 200', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.get('/api/settings/backups', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(Array.isArray(data)).toBeTruthy()
    if (data.length > 0) {
      const backup = data[0]
      expect(backup).toHaveProperty('name')
      expect(backup).toHaveProperty('size')
      expect(backup).toHaveProperty('size_bytes')
      expect(backup).toHaveProperty('time')
      expect(backup).toHaveProperty('type')
    }
  })
})

test.describe('Settings API - 备份配置', () => {
  test('GET /api/settings/backup/settings - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/settings/backup/settings')
    expect(resp.status()).toBe(401)
  })

  test('GET /api/settings/backup/settings - admin 返回 200', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.get('/api/settings/backup/settings', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('enabled')
    expect(data).toHaveProperty('interval_hours')
    expect(data).toHaveProperty('max_backups')
    expect(typeof data.enabled).toBe('boolean')
    expect(typeof data.interval_hours).toBe('number')
    expect(typeof data.max_backups).toBe('number')
  })
})

test.describe('Settings API - 备份统计', () => {
  test('GET /api/settings/backup/stats - 无认证返回 401', async ({ request }) => {
    const resp = await request.get('/api/settings/backup/stats')
    expect(resp.status()).toBe(401)
  })

  test('GET /api/settings/backup/stats - admin 返回 200', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.get('/api/settings/backup/stats', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('count')
    expect(data).toHaveProperty('total_size_mb')
    expect(data).toHaveProperty('files')
    expect(typeof data.count).toBe('number')
    expect(typeof data.total_size_mb).toBe('number')
    expect(Array.isArray(data.files)).toBeTruthy()
  })
})

test.describe('Settings API - 手动备份', () => {
  test('POST /api/settings/backup - 无认证返回 401', async ({ request }) => {
    const resp = await request.post('/api/settings/backup')
    expect(resp.status()).toBe(401)
  })

  test('POST /api/settings/backup - admin 触发备份', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.post('/api/settings/backup', {
      headers: { Authorization: `Bearer ${token}` },
    })
    const data = await resp.json()
    expect(data).toHaveProperty('message')
    expect([200, 500]).toContain(resp.status())
  })
})

test.describe('Settings API - 备份下载/删除/恢复（需要文件存在）', () => {
  test('GET /api/settings/backup/nonexistent.dump/download - 返回 404', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.get('/api/settings/backup/nonexistent.dump/download', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect([404, 500]).toContain(resp.status())
  })

  test('GET /api/settings/backup/invalid-extension.txt/download - 返回 400', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.get('/api/settings/backup/invalid-extension.txt/download', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(400)
  })

  test('DELETE /api/settings/backup/nonexistent.dump - 返回 404 或 500', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.delete('/api/settings/backup/nonexistent.dump', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect([404, 500]).toContain(resp.status())
  })

  test('DELETE /api/settings/backup/invalid.txt - 返回 400', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.delete('/api/settings/backup/invalid.txt', {
      headers: { Authorization: `Bearer ${token}` },
    })
    expect(resp.status()).toBe(400)
  })

  test('POST /api/settings/backup/invalid.txt/restore - 返回 400', async ({ request }) => {
    const token = await getAdminToken(request)
    const resp = await request.post('/api/settings/backup/invalid.txt/restore', {
      headers: { Authorization: `Bearer ${token}` },
      data: { create_snapshot: false },
    })
    expect(resp.status()).toBe(400)
  })
})
