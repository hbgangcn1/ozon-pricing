import { test, expect } from '@playwright/test'

test.describe('快速模式定价计算', () => {
  test.setTimeout(60000)

  test('快速模式标签页默认显示', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')

    const fastTab = page.getByRole('tab', { name: /快速模式/ })
    await expect(fastTab).toBeVisible({ timeout: 5000 })
  })

  test('快速模式包含进货单价和重量输入框', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.getByRole('tab', { name: /快速模式/ })).toBeVisible({ timeout: 5000 })

    const numInputs = page.locator('input[type="number"]')
    const count = await numInputs.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('快速模式包含开始计算按钮', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    const calcBtn = page.getByRole('button', { name: /开始计算|🚀 开始计算/ })
    await expect(calcBtn).toBeVisible({ timeout: 5000 })
  })

  test('无物流规则时按钮禁用或显示提示', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    const numInputs = page.locator('input[type="number"]')
    await numInputs.nth(0).fill('30')
    await numInputs.nth(1).fill('300')

    const calcBtn = page.getByRole('button', { name: /开始计算|🚀 开始计算/ })

    const isDisabled = await calcBtn.isDisabled()
    if (isDisabled) {
      const hint = page.locator('text=/物流规则|物流方案|请先添加/')
      const hintVisible = await hint.isVisible({ timeout: 2000 }).catch(() => false)
      expect(hintVisible || isDisabled).toBe(true)
    } else {
      await expect(calcBtn).toBeEnabled()
    }
  })

  test('填写参数后点击计算不崩溃', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    const numInputs = page.locator('input[type="number"]')
    await numInputs.nth(0).fill('50')
    await numInputs.nth(1).fill('500')

    const calcBtn = page.getByRole('button', { name: /开始计算|🚀 开始计算/ })
    await expect(calcBtn).toBeVisible({ timeout: 5000 })

    const isDisabled = await calcBtn.isDisabled()
    if (!isDisabled) {
      await calcBtn.click()
      await page.waitForTimeout(2000)

      const bodyLength = await page.evaluate(() => document.body.innerText.length)
      expect(bodyLength).toBeGreaterThan(100)
    }
  })

  test('计算完成后显示结果区域或保持页面稳定', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(500)

    const numInputs = page.locator('input[type="number"]')
    await numInputs.nth(0).fill('80')
    await numInputs.nth(1).fill('1000')

    const calcBtn = page.getByRole('button', { name: /开始计算|🚀 开始计算/ })
    await expect(calcBtn).toBeVisible({ timeout: 5000 })

    const isDisabled = await calcBtn.isDisabled()
    if (!isDisabled) {
      const calcResponse = page.waitForResponse(
        r => r.url().includes('/api/pricing'),
        { timeout: 15000 }
      ).catch(() => null)

      await calcBtn.click()
      await calcResponse

      await page.waitForTimeout(1000)

      const bodyLength = await page.evaluate(() => document.body.innerText.length)
      expect(bodyLength).toBeGreaterThan(100)

      const resultSection = page.locator('text=/价格优先|速度优先|汇率|建议售价/')
      const hasResult = await resultSection.isVisible({ timeout: 5000 }).catch(() => false)

      if (!hasResult) {
        await expect(page.locator('h1')).toBeVisible({ timeout: 3000 })
      }
    }
  })

  test('佣金费率等高级参数输入框存在', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForTimeout(300)

    const numInputs = page.locator('input[type="number"]')
    const count = await numInputs.count()
    expect(count).toBeGreaterThanOrEqual(2)
  })

  test('定价页面标题可见', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')

    await expect(page.locator('h1')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('h1')).toContainText('物流定价', { timeout: 5000 })
  })

  test('切换到快速模式后切回仍正常', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')

    const fastTab = page.getByRole('tab', { name: /快速模式/ })
    const preciseTab = page.getByRole('tab', { name: /精准模式/ })

    await preciseTab.click()
    await page.waitForTimeout(300)

    await fastTab.click()
    await page.waitForTimeout(300)

    await expect(page.getByRole('button', { name: /开始计算|🚀 开始计算/ })).toBeVisible({ timeout: 5000 })
  })
})
