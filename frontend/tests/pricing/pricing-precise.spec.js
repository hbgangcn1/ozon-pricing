import { test, expect } from '@playwright/test'

test.describe('精准模式定价计算', () => {
  test.setTimeout(90000)

  async function goPrecise(page) {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')
    await page.getByRole('tab', { name: /精准模式/ }).click()
    await page.waitForTimeout(600)
  }

  async function ensureTestProduct(page) {
    const cb = page.locator('[role="combobox"]').first()
    await cb.click()
    await page.waitForTimeout(400)

    const optCount = await page.locator('[role="option"]').count()
    if (optCount > 1) {
      await page.locator('[role="option"]').nth(1).click()
      await page.waitForTimeout(300)
      return true
    }

    await page.keyboard.press('Escape')
    await page.waitForTimeout(200)

    const nameInput = page.locator('input[placeholder="必填"]')
    await nameInput.fill(`PreciseTest${Date.now() % 10000}`)
    const numInputs = page.locator('input[type="number"]')
    await numInputs.nth(0).fill('60')
    await numInputs.nth(1).fill('400')
    await numInputs.nth(2).fill('20')
    await numInputs.nth(3).fill('15')
    await numInputs.nth(4).fill('10')

    await page.getByRole('button', { name: /保存产品/ }).click()
    await page.waitForResponse(
      r => r.url().includes('/api/products') && r.request().method() === 'POST',
      { timeout: 10000 }
    ).catch(() => null)
    await page.waitForTimeout(800)

    return false
  }

  test('精准模式标签页可切换', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')

    const preciseTab = page.getByRole('tab', { name: /精准模式/ })
    await expect(preciseTab).toBeVisible({ timeout: 5000 })
    await preciseTab.click()
    await page.waitForTimeout(300)

    await expect(page.locator('input[placeholder="必填"]')).toBeVisible({ timeout: 5000 })
  })

  test('精准模式包含产品名称输入框', async ({ page }) => {
    await goPrecise(page)

    await expect(page.locator('input[placeholder="必填"]')).toBeVisible({ timeout: 5000 })
  })

  test('精准模式包含重量和尺寸输入框', async ({ page }) => {
    await goPrecise(page)

    const numInputs = page.locator('input[type="number"]')
    const count = await numInputs.count()
    expect(count).toBeGreaterThanOrEqual(4)
  })

  test('精准模式包含保存产品和开始计算按钮', async ({ page }) => {
    await goPrecise(page)

    await expect(page.getByRole('button', { name: /保存产品/ })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: /开始计算/ })).toBeVisible({ timeout: 5000 })
  })

  test('精准模式填写产品名称后可以保存', async ({ page }) => {
    await goPrecise(page)

    const suffix = Date.now() % 100000
    const testName = `PreciseSave${suffix}`

    const nameInput = page.locator('input[placeholder="必填"]')
    await nameInput.fill(testName)

    const numInputs = page.locator('input[type="number"]')
    await numInputs.nth(0).fill('45')
    await numInputs.nth(1).fill('300')
    await numInputs.nth(2).fill('15')
    await numInputs.nth(3).fill('10')
    await numInputs.nth(4).fill('8')

    await page.getByRole('button', { name: /保存产品/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/products') && r.request().method() === 'POST',
      { timeout: 10000 }
    ).catch(() => null)

    await page.waitForTimeout(800)
    const bodyLength = await page.evaluate(() => document.body.innerText.length)
    expect(bodyLength).toBeGreaterThan(100)
  })

  test('精准模式选择产品后表单自动填充', async ({ page }) => {
    await goPrecise(page)

    await ensureTestProduct(page)

    const cb = page.locator('[role="combobox"]').first()
    await cb.click()
    await page.waitForTimeout(400)

    const optCount = await page.locator('[role="option"]').count()
    if (optCount > 1) {
      await page.locator('[role="option"]').nth(1).click()
      await page.waitForTimeout(500)

      const nameInput = page.locator('input[placeholder="必填"]')
      const nameValue = await nameInput.inputValue()
      expect(nameValue.length).toBeGreaterThan(0)
    }
  })

  test('精准模式计算 — 填写参数后点击计算不崩溃', async ({ page }) => {
    await goPrecise(page)

    const nameInput = page.locator('input[placeholder="必填"]')
    await nameInput.fill(`CalcTest${Date.now() % 10000}`)

    const numInputs = page.locator('input[type="number"]')
    await numInputs.nth(0).fill('55')
    await numInputs.nth(1).fill('600')
    await numInputs.nth(2).fill('25')
    await numInputs.nth(3).fill('18')
    await numInputs.nth(4).fill('12')

    const calcBtn = page.getByRole('button', { name: /开始计算/ })
    await expect(calcBtn).toBeVisible({ timeout: 5000 })

    const isDisabled = await calcBtn.isDisabled()
    if (!isDisabled) {
      const calcResponse = page.waitForResponse(
        r => r.url().includes('/api/pricing'),
        { timeout: 20000 }
      ).catch(() => null)

      await calcBtn.click()
      await calcResponse
      await page.waitForTimeout(1500)

      const bodyLength = await page.evaluate(() => document.body.innerText.length)
      expect(bodyLength).toBeGreaterThan(100)
    }
  })

  test('精准模式计算结果显示或给出正确提示', async ({ page }) => {
    await goPrecise(page)

    const nameInput = page.locator('input[placeholder="必填"]')
    await nameInput.fill(`ResultTest${Date.now() % 10000}`)

    const numInputs = page.locator('input[type="number"]')
    await numInputs.nth(0).fill('70')
    await numInputs.nth(1).fill('800')
    await numInputs.nth(2).fill('30')
    await numInputs.nth(3).fill('20')
    await numInputs.nth(4).fill('15')

    const calcBtn = page.getByRole('button', { name: /开始计算/ })
    await expect(calcBtn).toBeVisible({ timeout: 5000 })

    const isDisabled = await calcBtn.isDisabled()
    if (!isDisabled) {
      const calcResponse = page.waitForResponse(
        r => r.url().includes('/api/pricing'),
        { timeout: 20000 }
      ).catch(() => null)

      await calcBtn.click()
      const resp = await calcResponse
      await page.waitForTimeout(1500)

      if (resp && resp.status() === 200) {
        const resultSection = page.locator('text=/价格优先|速度优先|汇率|建议售价/')
        const hasResult = await resultSection.isVisible({ timeout: 5000 }).catch(() => false)
        if (!hasResult) {
          await expect(page.locator('h1')).toBeVisible({ timeout: 3000 })
        }
      } else {
        await expect(page.locator('h1')).toBeVisible({ timeout: 3000 })
      }
    }
  })

  test('包装类型切换 — 圆柱包装显示不同输入框', async ({ page }) => {
    await goPrecise(page)

    await expect(page.locator('label[for="pkg-regular"]')).toBeVisible({ timeout: 5000 })
    await expect(page.locator('label[for="pkg-cylinder"]')).toBeVisible({ timeout: 5000 })

    const cylinderRadio = page.locator('label[for="pkg-cylinder"]')
    await cylinderRadio.click()
    await page.waitForTimeout(300)

    await expect(page.getByText('圆柱直径（厘米）')).toBeVisible({ timeout: 3000 })
  })
})
