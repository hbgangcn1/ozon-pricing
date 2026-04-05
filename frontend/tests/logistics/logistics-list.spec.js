import { test, expect } from '@playwright/test'

test.describe('物流规则列表', () => {
  test.setTimeout(30000)

  test('物流页面加载成功', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.locator('h1')).toContainText('物流', { timeout: 5000 })
  })

  test('添加物流规则按钮存在', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('button', { name: /添加物流规则/ })).toBeVisible({ timeout: 5000 })
  })

  test('陆运和空运标签页存在', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('tab', { name: '陆运' })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('tab', { name: '空运' })).toBeVisible({ timeout: 5000 })
  })

  test('可切换陆运和空运标签页', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('tab', { name: '陆运' }).click()
    await page.waitForTimeout(300)
    const landTab = page.getByRole('tab', { name: '陆运' })
    await expect(landTab).toBeVisible({ timeout: 3000 })

    await page.getByRole('tab', { name: '空运' }).click()
    await page.waitForTimeout(300)
    const airTab = page.getByRole('tab', { name: '空运' })
    await expect(airTab).toBeVisible({ timeout: 3000 })
  })

  test('物流规则列表区域存在', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(800)

    const tabContent = page.locator('[role="tabpanel"]').first()
    await expect(tabContent).toBeVisible({ timeout: 5000 })
  })

  test('添加对话框可以打开和关闭', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: /添加物流规则/ }).click()

    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    await dialog.getByRole('button', { name: /取消/ }).click()
    await expect(dialog).not.toBeVisible({ timeout: 5000 })
  })

  test('添加对话框包含名称输入框', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: /添加物流规则/ }).click()

    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    await expect(dialog.locator('input[placeholder="请输入名称"]')).toBeVisible({ timeout: 5000 })
  })

  test('添加对话框包含物流类型选择', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: /添加物流规则/ }).click()

    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    await expect(dialog.getByText('陆运')).toBeVisible({ timeout: 5000 })
    await expect(dialog.getByText('空运')).toBeVisible({ timeout: 5000 })
  })

  test('添加对话框包含基本费用输入', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('button', { name: /添加物流规则/ }).click()

    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    const numInputs = dialog.locator('input[type="number"]')
    const count = await numInputs.count()
    expect(count).toBeGreaterThan(0)
  })

  test('页面不崩溃且body有内容', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(1000)

    const bodyLength = await page.evaluate(() => document.body.innerText.length)
    expect(bodyLength).toBeGreaterThan(100)
  })
})
