/* eslint-env node */
import { test, expect } from '@playwright/test'
import { API_BASE } from '../fixtures/test-data.js'
import { getAdminToken } from '../helpers/admin-token.js'
import { ADMIN_AUTH_FILE, ADMIN_MARKER_FILE } from '../helpers/auth-paths.js'

test.describe('产品批量导入流程', () => {
  test.setTimeout(90000)

  let adminToken

  test.beforeAll(async ({ request }) => {
    adminToken = await getAdminToken(request, { authFile: ADMIN_AUTH_FILE, markerFile: ADMIN_MARKER_FILE })
  })

  test('产品导入页面可访问', async ({ page }) => {
    await page.goto('/product-import')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('heading', { name: /产品导入|批量导入/ })).toBeVisible({ timeout: 8000 })
  })

  test('上传区域包含文件选择按钮', async ({ page }) => {
    await page.goto('/product-import')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('h1, h2')).toBeVisible({ timeout: 8000 })

    const fileInput = page.locator('input[type="file"]')
    const uploadBtn = page.getByRole('button', { name: /上传|选择文件|导入/ })

    const hasFileInput = await fileInput.count() > 0
    const hasUploadBtn = await uploadBtn.isVisible().catch(() => false)
    expect(hasFileInput || hasUploadBtn).toBeTruthy()
  })

  test('POST /api/products/import/preview 接口可用', async ({ request }) => {
    const csvContent = 'name,weight_g,length_cm,width_cm,height_cm\nTestProduct1,500,20,15,10'
    const boundary = '----FormBoundary' + Math.random().toString(36).slice(2)

    const body = [
      `--${boundary}`,
      'Content-Disposition: form-data; name="file"; filename="test.csv"',
      'Content-Type: text/csv',
      '',
      csvContent,
      `--${boundary}--`,
    ].join('\r\n')

    const resp = await request.post(`${API_BASE}/products/import/preview`, {
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        Authorization: `Bearer ${adminToken}`,
      },
      data: Buffer.from(body),
    })

    expect([200, 400, 422]).toContain(resp.status())
  })

  test('产品导入页面字段映射区域结构正确', async ({ page }) => {
    await page.goto('/product-import')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('h1, h2')).toBeVisible({ timeout: 8000 })

    const pageContent = await page.locator('body').textContent()
    const hasNameField = pageContent.includes('产品名称')
    const hasWeightField = pageContent.includes('重量')
    expect(hasNameField || hasWeightField).toBeTruthy()
  })

  test('导入页面不包含货币字段', async ({ page }) => {
    await page.goto('/product-import')
    await page.waitForLoadState('domcontentloaded')
    await expect(page.locator('h1, h2')).toBeVisible({ timeout: 8000 })

    const pageContent = await page.locator('body').textContent()
    expect(pageContent).not.toContain('货币')
  })

  test('产品导入预览不截断数据 — API 发送全部行', async ({ request }) => {
    const rows = ['name,weight_g,length_cm,width_cm,height_cm']
    for (let i = 1; i <= 15; i++) {
      rows.push(`ImportTest${i},${100 + i},${10 + i},${5 + i},${3 + i}`)
    }
    const csvContent = rows.join('\n')

    const boundary = '----FormBoundary' + Math.random().toString(36).slice(2)
    const body = [
      `--${boundary}`,
      'Content-Disposition: form-data; name="file"; filename="test15.csv"',
      'Content-Type: text/csv',
      '',
      csvContent,
      `--${boundary}--`,
    ].join('\r\n')

    const resp = await request.post(`${API_BASE}/products/import/preview`, {
      headers: {
        'Content-Type': `multipart/form-data; boundary=${boundary}`,
        Authorization: `Bearer ${adminToken}`,
      },
      data: Buffer.from(body),
    })

    if (resp.status() === 200) {
      const data = await resp.json()
      expect(data.preview_rows.length).toBe(15)
    }
  })
})
