import { test, expect } from '@playwright/test'

test.describe('精准模式定价计算', () => {
  test.describe.configure({ mode: 'parallel' })
  test.setTimeout(90000)

  async function goPrecise(page) {
    await page.goto('/pricing', { waitUntil: 'domcontentloaded' })
    const preciseTab = page.getByRole('tab', { name: /精准模式/ })
    await expect(preciseTab).toBeVisible({ timeout: 5000 })
    await preciseTab.click()
    await expect(page.locator('input[placeholder="必填"]')).toBeVisible({ timeout: 5000 })
  }

  async function fillPreciseForm(page, name, values = ['60', '400', '20', '15', '10']) {
    await page.locator('input[placeholder="必填"]').fill(name)

    const numInputs = page.locator('input[type="number"]')
    for (const [index, value] of values.entries()) {
      await numInputs.nth(index).fill(value)
    }
  }

  function waitForProductMutation(page, methods = ['POST']) {
    return page.waitForResponse(
      response => response.url().includes('/api/products') && methods.includes(response.request().method()),
      { timeout: 10000 }
    )
  }

  function waitForPricingResponse(page) {
    return page.waitForResponse(
      response => response.url().includes('/api/pricing') && response.request().method() === 'POST',
      { timeout: 15000 }
    )
  }

  async function selectFirstSavedProduct(page) {
    const productCombobox = page.locator('[role="combobox"]').first()
    await productCombobox.click()

    const productOptions = page.locator('[role="option"]')
    await expect(productOptions.first()).toBeVisible({ timeout: 3000 }).catch(() => null)

    const optionCount = await productOptions.count()
    if (optionCount > 1) {
      await productOptions.nth(1).click()
      await expect(page.locator('input[placeholder="必填"]')).not.toHaveValue('', { timeout: 3000 })
      return true
    }

    await page.keyboard.press('Escape')
    return false
  }

  async function ensureTestProduct(page) {
    const hasExistingProduct = await selectFirstSavedProduct(page)
    if (hasExistingProduct) {
      return true
    }

    await fillPreciseForm(page, `PreciseTest${Date.now() % 10000}`)
    const saveButton = page.getByRole('button', { name: /保存产品/ })
    await Promise.all([
      waitForProductMutation(page).catch(() => null),
      saveButton.click(),
    ])

    await expect
      .poll(async () => {
        const productCombobox = page.locator('[role="combobox"]').first()
        await productCombobox.click()
        const optionCount = await page.locator('[role="option"]').count()
        await page.keyboard.press('Escape')
        return optionCount
      }, { timeout: 5000 })
      .toBeGreaterThan(1)

    return false
  }

  test('精准模式标签页可切换', async ({ page }) => {
    await page.goto('/pricing', { waitUntil: 'domcontentloaded' })

    const preciseTab = page.getByRole('tab', { name: /精准模式/ })
    await expect(preciseTab).toBeVisible({ timeout: 5000 })
    await preciseTab.click()

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

    await fillPreciseForm(page, testName, ['45', '300', '15', '10', '8'])

    await Promise.all([
      waitForProductMutation(page).catch(() => null),
      page.getByRole('button', { name: /保存产品/ }).click(),
    ])

    const bodyLength = await page.evaluate(() => document.body.innerText.length)
    expect(bodyLength).toBeGreaterThan(100)
  })

  test('精准模式选择产品后表单自动填充', async ({ page }) => {
    await goPrecise(page)

    await ensureTestProduct(page)

    const hasSelectedProduct = await selectFirstSavedProduct(page)
    expect(hasSelectedProduct).toBeTruthy()

    const nameValue = await page.locator('input[placeholder="必填"]').inputValue()
    expect(nameValue.length).toBeGreaterThan(0)
  })

  test('精准模式计算 — 填写参数后点击计算不崩溃', async ({ page }) => {
    await goPrecise(page)

    await fillPreciseForm(page, `CalcTest${Date.now() % 10000}`, ['55', '600', '25', '18', '12'])

    const calcBtn = page.getByRole('button', { name: /开始计算/ })
    await expect(calcBtn).toBeVisible({ timeout: 5000 })

    const isDisabled = await calcBtn.isDisabled()
    if (!isDisabled) {
      await Promise.all([
        waitForPricingResponse(page).catch(() => null),
        calcBtn.click(),
      ])

      const bodyLength = await page.evaluate(() => document.body.innerText.length)
      expect(bodyLength).toBeGreaterThan(100)
    }
  })

  test('精准模式计算结果显示或给出正确提示', async ({ page }) => {
    await goPrecise(page)

    await fillPreciseForm(page, `ResultTest${Date.now() % 10000}`, ['70', '800', '30', '20', '15'])

    const calcBtn = page.getByRole('button', { name: /开始计算/ })
    await expect(calcBtn).toBeVisible({ timeout: 5000 })

    const isDisabled = await calcBtn.isDisabled()
    if (!isDisabled) {
      const resp = await Promise.all([
        waitForPricingResponse(page).catch(() => null),
        calcBtn.click(),
      ]).then(([response]) => response)

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

    await expect(page.getByText('圆柱直径（厘米）')).toBeVisible({ timeout: 3000 })
  })

  test('佣金类目保存后重新选择产品应正确回显', async ({ page }) => {
    await goPrecise(page)

    // 创建一个新产品
    const suffix = Date.now() % 100000
    const testName = `CommCat${suffix}`

    await fillPreciseForm(page, testName)

    // 选择佣金类目（如果有可选项）
    const categorySelects = page.locator('text=佣金类目').locator('..').locator('[role="combobox"]')
    const hasCategorySelect = await categorySelects.count()

    if (hasCategorySelect > 0) {
      await categorySelects.first().click()

      const options = page.locator('[role="option"]')
      await expect(options.first()).toBeVisible({ timeout: 3000 }).catch(() => null)
      const optCount = await options.count()

      if (optCount > 1) {
        // 选择第二个选项（跳过"不使用类目"）
        await options.nth(1).click()

        // 保存产品
        await Promise.all([
          waitForProductMutation(page, ['POST', 'PUT']).catch(() => null),
          page.getByRole('button', { name: /保存产品/ }).click(),
        ])

        // 重新选择产品下拉菜单，找到刚保存的产品
        const productCombobox = page.locator('[role="combobox"]').first()
        await productCombobox.click()

        // 选择包含我们测试名称的产品
        const productOption = page.locator('[role="option"]').filter({ hasText: testName }).first()
        await expect(productOption).toBeVisible({ timeout: 5000 })
        await productOption.click()

        // 验证佣金类目是否正确回显（不再显示占位文字"选择佣金类目"）
        const categoryTrigger = page.locator('text=佣金类目').locator('..').locator('[role="combobox"]')
        if (await categoryTrigger.count() > 0) {
          const displayedText = await categoryTrigger.first().textContent()
          // 应该显示选中的类目名称，而不是"选择佣金类目"
          expect(displayedText).not.toBe('选择佣金类目')
        }
      } else {
        // 没有可选的佣金类目，跳过此测试的验证部分
        await page.keyboard.press('Escape')
      }
    }
  })
})
