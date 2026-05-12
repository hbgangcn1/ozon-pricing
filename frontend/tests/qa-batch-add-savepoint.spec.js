/* eslint-env node */
/**
 * Manual QA evidence for OpenSpec change `fix-logistics-pool-batch-add-savepoint`.
 */
import { test, expect } from '@playwright/test'
import { seedPool } from './fixtures/logistics-pool-fixture.js'

test.beforeEach(async () => {
  seedPool()
})

test('QA: admin batch-add all logistics-pool items shows success toast (no 500)', async ({ page }) => {
  const consoleErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  const failed5xx = []
  page.on('response', (resp) => {
    if (resp.status() >= 500) failed5xx.push(`${resp.status()} ${resp.url()}`)
  })

  await page.goto('/logistics-pool')
  await expect(page).toHaveURL(/\/logistics-pool/)

  const kickedDialog = page.getByRole('alertdialog', { name: /账号在其他设备登录/ })
  if (await kickedDialog.isVisible().catch(() => false)) {
    throw new Error('Kicked dialog present; admin storageState invalidated. Re-run admin setup with no concurrent logins.')
  }

  await expect(page.getByRole('heading', { name: '公共物流池', level: 1 })).toBeVisible({ timeout: 20000 })
  await page.waitForLoadState('networkidle')
  const selectAll = page.getByRole('checkbox', { name: '全选' })
  await expect(selectAll).toBeVisible({ timeout: 15000 })
  await expect(page.locator('text=暂无物流数据')).toHaveCount(0)
  await page.screenshot({ path: 'test-results/qa-savepoint-01-pool-loaded.png', fullPage: true })

  await selectAll.click()
  const batchBtn = page.getByRole('button', { name: /全部添加到我的物流/ })
  await expect(batchBtn).toBeVisible({ timeout: 5000 })
  await page.screenshot({ path: 'test-results/qa-savepoint-02-all-selected.png', fullPage: true })

  await expect(batchBtn).toBeEnabled()
  await batchBtn.click()

  const successToast = page.locator('text=/已(成功)?添加.*我的物流|已添加 \\d+ 条/')
  await expect(successToast.first()).toBeVisible({ timeout: 20000 })
  await page.screenshot({ path: 'test-results/qa-savepoint-03-success-toast.png', fullPage: true })

  await expect(page.locator('text=Internal server error')).toHaveCount(0)
  await expect(page.locator('text=批量添加失败')).toHaveCount(0)

  expect(failed5xx, `Got 5xx responses: ${failed5xx.join('; ')}`).toEqual([])
  const realErrors = consoleErrors.filter(e =>
    !/DevTools|Download the React DevTools|favicon|Failed to load resource.*404/.test(e)
  )
  expect(realErrors, `Console errors: ${realErrors.join('; ')}`).toEqual([])
})
