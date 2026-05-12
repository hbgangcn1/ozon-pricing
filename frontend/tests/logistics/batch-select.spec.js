import { test, expect } from '@playwright/test'
import { API_BASE } from '../fixtures/test-data.js'
import { getAdminToken } from '../helpers/admin-token.js'
import { ADMIN_AUTH_FILE, ADMIN_MARKER_FILE } from '../helpers/auth-paths.js'
import { cleanupPool, seedMyLogistics, seedPool } from '../fixtures/logistics-pool-fixture.js'

test.describe.configure({ mode: 'serial' })

test.describe('物流管理 — 全选与批量删除', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(90000)

  let adminToken

  test.beforeAll(async ({ request }) => {
    adminToken = await getAdminToken(request, { authFile: ADMIN_AUTH_FILE, markerFile: ADMIN_MARKER_FILE })
    seedMyLogistics('admin')
  })

  test.afterAll(async () => {
    const resp = await fetch(`${API_BASE}/logistics?page_size=200`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    if (resp.ok) {
      const data = await resp.json()
      const items = data.items || data || []
      for (const item of items) {
        if (item.name?.startsWith('BatchTest_E2E_Land_')) {
          await fetch(`${API_BASE}/logistics/${item.id}`, {
            method: 'DELETE',
            headers: { Authorization: `Bearer ${adminToken}` },
          })
        }
      }
    }
  })

  async function goLogistics(page) {
    await page.goto('/logistics')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)
  }

  test('全选当前页 checkbox 可见', async ({ page }) => {
    await goLogistics(page)

    const landTab = page.getByRole('tab', { name: '陆运' })
    await expect(landTab).toBeVisible({ timeout: 5000 })

    const selectAllCheckbox = page.getByLabel('全选当前页').first()
    await expect(selectAllCheckbox).toBeVisible({ timeout: 8000 })
  })

  test('点击全选当前页后浮动操作栏出现', async ({ page }) => {
    await goLogistics(page)

    const selectAllCheckbox = page.getByLabel('全选当前页').first()
    await expect(selectAllCheckbox).toBeVisible({ timeout: 8000 })

    await selectAllCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })
    await expect(floatingBar).toContainText('已选')
    await expect(floatingBar).toContainText('项')
  })

  test('浮动栏包含清除和批量删除按钮', async ({ page }) => {
    await goLogistics(page)

    const selectAllCheckbox = page.getByLabel('全选当前页').first()
    await selectAllCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })

    await expect(floatingBar.getByRole('button', { name: /清除/ })).toBeVisible()
    await expect(floatingBar.getByRole('button', { name: /批量删除/ })).toBeVisible()
  })

  test('点击清除后浮动栏消失', async ({ page }) => {
    await goLogistics(page)

    const selectAllCheckbox = page.getByLabel('全选当前页').first()
    await selectAllCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })

    await floatingBar.getByRole('button', { name: /清除/ }).click()
    await page.waitForTimeout(300)

    await expect(floatingBar).not.toBeVisible({ timeout: 5000 })
  })

  test('批量删除流程完整', async ({ page }) => {
    await goLogistics(page)

    const selectAllCheckbox = page.getByLabel('全选当前页').first()
    await selectAllCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })

    await floatingBar.getByRole('button', { name: /批量删除/ }).click()

    const alertDialog = page.locator('[role="alertdialog"]')
    await expect(alertDialog).toBeVisible({ timeout: 5000 })
    await expect(alertDialog).toContainText('确认批量删除')

    await alertDialog.getByRole('button', { name: /取消/ }).click()
    await expect(alertDialog).not.toBeVisible({ timeout: 5000 })
  })

  test('空运 tab 切换正常', async ({ page }) => {
    await goLogistics(page)

    await page.getByRole('tab', { name: '空运' }).click()
    await page.waitForTimeout(300)

    const airPanel = page.getByRole('tabpanel', { name: '空运' })
    await expect(airPanel).toBeVisible({ timeout: 5000 })
  })
})


test.describe('公共物流池 — 批量选择与添加', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(90000)

  let adminToken

  test.beforeAll(async ({ request }) => {
    adminToken = await getAdminToken(request, { authFile: ADMIN_AUTH_FILE, markerFile: ADMIN_MARKER_FILE })
  })

  // Re-seed before EVERY test in this group: another parallel spec
  // (logistics-pool-delete-all.spec.js) calls DELETE /api/logistics-pool/all
  // which wipes shared seed data. Per-test seed prevents the race.
  test.beforeEach(async () => {
    seedPool()
  })

  test.afterAll(async () => {
    cleanupPool()
  })

  async function goPool(page) {
    for (let attempt = 0; attempt < 3; attempt++) {
      await page.goto('/logistics-pool')
      await page.waitForLoadState('networkidle')
      await page.waitForTimeout(500)

      const rowCount = await page.locator('[data-row]').count().catch(() => 0)
      if (rowCount > 0) return

      seedPool()
      await page.waitForTimeout(500)
    }

    throw new Error('goPool: pool stayed empty after 3 reseed attempts')
  }

  test('公共物流池页面加载成功', async ({ page }) => {
    await goPool(page)
    await expect(page.getByRole('heading', { name: '公共物流池' })).toBeVisible({ timeout: 8000 })
  })

  test('表头全选 checkbox 可见', async ({ page }) => {
    await goPool(page)

    const headerCheckbox = page.getByLabel('全选')
    await expect(headerCheckbox).toBeVisible({ timeout: 8000 })
  })

  test('点击表头全选后选中所有行', async ({ page }) => {
    await goPool(page)

    const headerCheckbox = page.getByLabel('全选')
    await expect(headerCheckbox).toBeVisible({ timeout: 8000 })

    await headerCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })
    await expect(floatingBar).toContainText('已选')
  })

  test('浮动栏包含全部添加和取消按钮', async ({ page }) => {
    await goPool(page)

    const headerCheckbox = page.getByLabel('全选')
    await headerCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })

    await expect(
      floatingBar.getByRole('button', { name: /全部添加到我的物流/ })
    ).toBeVisible()
    await expect(
      floatingBar.getByRole('button', { name: /取消/ })
    ).toBeVisible()
  })

  test('点击取消后浮动栏消失', async ({ page }) => {
    await goPool(page)

    const headerCheckbox = page.getByLabel('全选')
    await headerCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })

    await floatingBar.getByRole('button', { name: /取消/ }).click()
    await page.waitForTimeout(300)

    await expect(floatingBar).not.toBeVisible({ timeout: 5000 })
  })

  test('单个 checkbox 可选中和取消', async ({ page }) => {
    await goPool(page)

    const rows = page.locator('[data-row]')
    await expect(rows.first()).toBeVisible({ timeout: 8000 })

    const firstCheckbox = rows.first().locator('button[role="checkbox"]')
    await firstCheckbox.click()
    await page.waitForTimeout(300)

    const floatingBar = page.locator('.fixed.bottom-6')
    await expect(floatingBar).toBeVisible({ timeout: 5000 })
    await expect(floatingBar).toContainText('已选 1 项')

    await firstCheckbox.click()
    await page.waitForTimeout(300)

    await expect(floatingBar).not.toBeVisible({ timeout: 5000 })
  })

  test('选中行有高亮样式', async ({ page }) => {
    await goPool(page)

    const rows = page.locator('[data-row]')
    await expect(rows.first()).toBeVisible({ timeout: 8000 })

    const firstRow = rows.first()
    const firstCheckbox = firstRow.locator('button[role="checkbox"]')

    await expect(firstRow).not.toHaveClass(/bg-primary/)

    await firstCheckbox.click()
    await page.waitForTimeout(300)

    await expect(firstRow).toHaveClass(/bg-primary/)

    await firstCheckbox.click()
  })

  test('POST /api/logistics-pool/batch-add-to-my-logistics 返回 200', async ({ request }) => {
    const listResp = await request.get(`${API_BASE}/logistics-pool?limit=1`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    expect(listResp.status()).toBe(200)
    const listData = await listResp.json()
    const items = listData.items || listData || []
    expect(items.length).toBeGreaterThan(0)

    const ids = [items[0].id]

    const resp = await request.post(
      `${API_BASE}/logistics-pool/batch-add-to-my-logistics`,
      {
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${adminToken}`,
        },
        data: { ids },
      }
    )
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('added')
  })
})
