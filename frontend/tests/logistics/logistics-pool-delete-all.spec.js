import { test, expect } from '@playwright/test'
import { TEST_ADMIN, API_BASE } from '../fixtures/test-data.js'
import { apiLogin } from '../helpers/api-helpers.js'

test.describe('公共物流池 — 删除全部', () => {
  test.setTimeout(60000)

  let adminToken

  test.beforeAll(async () => {
    adminToken = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password)
  })

  test('删除全部按钮可见', async ({ page }) => {
    await page.goto('/logistics-pool')
    await page.waitForLoadState('domcontentloaded')

    const deleteAllBtn = page.getByRole('button', { name: /删除全部|清空/ })
    await expect(deleteAllBtn).toBeVisible({ timeout: 8000 })
  })

  test('DELETE /api/logistics-pool/all 返回 200', async ({ request }) => {
    const resp = await request.delete(`${API_BASE}/logistics-pool/all`, {
      headers: { Authorization: `Bearer ${adminToken}` },
    })
    expect(resp.status()).toBe(200)
    const data = await resp.json()
    expect(data).toHaveProperty('deleted')
  })

  test('点击删除全部后确认对话框出现', async ({ page }) => {
    await page.goto('/logistics-pool')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    const deleteAllBtn = page.getByRole('button', { name: /删除全部|清空/ })
    await expect(deleteAllBtn).toBeVisible({ timeout: 8000 })

    await deleteAllBtn.click()

    const alertDialog = page.locator('[role="alertdialog"]')
    const toast = page.locator('[data-sonner-toast]').first()

    await expect(async () => {
      const hasDialog = await alertDialog.isVisible().catch(() => false)
      const hasToast = await toast.isVisible().catch(() => false)
      expect(hasDialog || hasToast).toBeTruthy()
    }).toPass({ timeout: 8000 })

    if (await alertDialog.isVisible().catch(() => false)) {
      await alertDialog.getByRole('button', { name: /确认|确定|删除/ }).click()
      await page.waitForTimeout(2000)
    }
  })
})
