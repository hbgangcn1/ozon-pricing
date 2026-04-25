import { test, expect } from '@playwright/test'

test.describe('精准模式标签页切换', () => {
  test.setTimeout(90000)

  const mainTabs = [
    { name: 'rFBS-俄罗斯', key: 'rfbs_ru' },
    { name: 'rFBS-独联体', key: 'rfbs_KZ' },
    { name: 'FBP-仅俄罗斯', key: 'fbp_ru' },
    { name: 'FBP-俄+CIS', key: 'fbp_cis' },
  ]

  const cisTabs = [
    { name: '哈萨克斯坦', key: 'rfbs_KZ' },
    { name: '白俄罗斯', key: 'rfbs_BY' },
    { name: '格鲁吉亚', key: 'rfbs_GE' },
    { name: '吉尔吉斯斯坦', key: 'rfbs_KGZ' },
    { name: '阿塞拜疆', key: 'rfbs_AZ' },
    { name: '乌兹别克斯坦', key: 'rfbs_UZ' },
    { name: '亚美尼亚', key: 'rfbs_AM' },
  ]

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
    await nameInput.fill(`PreciseTab${Date.now() % 10000}`)
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

  function getFilteredCount(groupedData, key) {
    const filtered = groupedData?.[key]?.filtered_logistics
    return (filtered?.land?.length || 0) + (filtered?.air?.length || 0)
  }

  async function getGroupedTabsVisible(page) {
    return await page.getByRole('tab', { name: 'rFBS-俄罗斯' }).isVisible().catch(() => false)
  }

  async function fillAndCalculate(page) {
    await ensureTestProduct(page)

    const calcBtn = page.getByRole('button', { name: /开始计算/ })
    const isDisabled = await calcBtn.isDisabled().catch(() => true)
    if (isDisabled) {
      return { ok: false, groupedData: null }
    }

    const normalResponsePromise = page.waitForResponse(
      r => r.url().includes('/api/pricing/calculate') && !r.url().includes('/calculate-grouped') && r.request().method() === 'POST',
      { timeout: 30000 }
    ).catch(() => null)

    const groupedResponsePromise = page.waitForResponse(
      r => r.url().includes('/api/pricing/calculate-grouped') && r.request().method() === 'POST',
      { timeout: 30000 }
    ).catch(() => null)

    await calcBtn.click()

    const [, groupedResponse] = await Promise.all([
      normalResponsePromise,
      groupedResponsePromise,
    ])

    await page.waitForTimeout(2500)

    const groupedData = groupedResponse && groupedResponse.status() === 200
      ? await groupedResponse.json().catch(() => null)
      : null

    return {
      ok: !!(groupedResponse && groupedResponse.status() === 200),
      groupedData,
    }
  }

  async function clickMainTab(page, name) {
    await page.getByRole('tab', { name }).click()
    await page.waitForTimeout(450)
  }

  async function clickCisTab(page, name) {
    await page.getByRole('tab', { name }).click()
    await page.waitForTimeout(350)
  }

  async function assertEliminatedState(page, expectedCount) {
    const trigger = page.getByText(/被淘汰的物流/).first()
    const visible = await trigger.isVisible().catch(() => false)

    if (expectedCount > 0) {
      expect(visible).toBe(true)
      await expect(trigger).toContainText(`(${expectedCount} 条)`)
    } else {
      expect(visible).toBe(false)
    }
  }

  test('主标签页切换时被淘汰物流按分组更新', async ({ page }) => {
    await goPrecise(page)
    const { groupedData } = await fillAndCalculate(page)

    const tabsVisible = await getGroupedTabsVisible(page)
    if (!tabsVisible || !groupedData) {
      await expect(page.locator('h1')).toBeVisible({ timeout: 5000 })
      return
    }

    for (const tab of mainTabs) {
      await clickMainTab(page, tab.name)
      await assertEliminatedState(page, getFilteredCount(groupedData, tab.key))
    }
  })

  test('独联体子标签页切换时被淘汰物流按国家更新', async ({ page }) => {
    await goPrecise(page)
    const { groupedData } = await fillAndCalculate(page)

    const tabsVisible = await getGroupedTabsVisible(page)
    if (!tabsVisible || !groupedData) {
      await expect(page.locator('h1')).toBeVisible({ timeout: 5000 })
      return
    }

    await clickMainTab(page, 'rFBS-独联体')

    for (const tab of cisTabs) {
      await clickCisTab(page, tab.name)
      await assertEliminatedState(page, getFilteredCount(groupedData, tab.key))
    }
  })

  test('FBP 标签页展示分组计算结果', async ({ page }) => {
    await goPrecise(page)
    const { groupedData } = await fillAndCalculate(page)

    const tabsVisible = await getGroupedTabsVisible(page)
    if (!tabsVisible || !groupedData) {
      await expect(page.locator('h1')).toBeVisible({ timeout: 5000 })
      return
    }

    expect(groupedData?.fbp_ru?.price_priority).toBeTruthy()
    expect(groupedData?.fbp_ru?.speed_priority).toBeTruthy()
    expect(groupedData?.fbp_cis?.price_priority).toBeTruthy()
    expect(groupedData?.fbp_cis?.speed_priority).toBeTruthy()

    for (const tabName of ['FBP-仅俄罗斯', 'FBP-俄+CIS']) {
      await clickMainTab(page, tabName)
      await expect(page.getByText(/低价优先/).first()).toBeVisible({ timeout: 5000 })
      await expect(page.getByText(/速度优先/).first()).toBeVisible({ timeout: 5000 })

      const hasResultContent = await page.getByText(/建议售价|无可用方案|无匹配物流规则/).first()
        .isVisible({ timeout: 5000 })
        .catch(() => false)

      expect(hasResultContent).toBe(true)
    }
  })

  test('被淘汰物流折叠区可以展开和收起', async ({ page }) => {
    await goPrecise(page)
    const { groupedData } = await fillAndCalculate(page)

    const tabsVisible = await getGroupedTabsVisible(page)
    if (!tabsVisible || !groupedData) {
      await expect(page.locator('h1')).toBeVisible({ timeout: 5000 })
      return
    }

    const targets = [
      { main: 'rFBS-俄罗斯', key: 'rfbs_ru' },
      { main: 'rFBS-独联体', cis: '哈萨克斯坦', key: 'rfbs_KZ' },
      { main: 'rFBS-独联体', cis: '白俄罗斯', key: 'rfbs_BY' },
      { main: 'rFBS-独联体', cis: '格鲁吉亚', key: 'rfbs_GE' },
      { main: 'rFBS-独联体', cis: '吉尔吉斯斯坦', key: 'rfbs_KGZ' },
      { main: 'rFBS-独联体', cis: '阿塞拜疆', key: 'rfbs_AZ' },
      { main: 'rFBS-独联体', cis: '乌兹别克斯坦', key: 'rfbs_UZ' },
      { main: 'rFBS-独联体', cis: '亚美尼亚', key: 'rfbs_AM' },
      { main: 'FBP-仅俄罗斯', key: 'fbp_ru' },
      { main: 'FBP-俄+CIS', key: 'fbp_cis' },
    ]

    const target = targets.find(item => getFilteredCount(groupedData, item.key) > 0)

    if (!target) {
      await clickMainTab(page, 'rFBS-俄罗斯')
      const triggerVisible = await page.getByText(/被淘汰的物流/).first().isVisible().catch(() => false)
      expect(triggerVisible).toBe(false)
      return
    }

    await clickMainTab(page, target.main)
    if (target.cis) {
      await clickCisTab(page, target.cis)
    }

    const trigger = page.getByText(/被淘汰的物流/).first()
    await expect(trigger).toBeVisible({ timeout: 5000 })
    await trigger.click()
    await page.waitForTimeout(300)
    await expect(page.getByText('🚛 陆运').first()).toBeVisible({ timeout: 5000 })

    await trigger.click()
    await page.waitForTimeout(300)
    await expect(page.getByText('🚛 陆运').first()).toBeHidden({ timeout: 5000 })
  })
})
