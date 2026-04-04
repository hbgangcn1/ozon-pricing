import { test, expect } from '@playwright/test'

test.describe('关于页面 — /about', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/about')
    await expect(page).toHaveURL('/about')
  })

  test('页面加载不崩溃', async ({ page }) => {
    const bodyText = await page.evaluate(() => document.body.innerText)
    expect(bodyText.length).toBeGreaterThan(50)
  })

  test('页面标题显示关于我们', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('关于我们')
  })

  test('公司信息卡片存在', async ({ page }) => {
    await expect(page.getByText('公司信息')).toBeVisible()
  })

  test('公司名称显示', async ({ page }) => {
    await expect(page.getByText('公司名称')).toBeVisible()
    await expect(page.getByText('深圳超凡酷玩电子商务有限公司')).toBeVisible()
  })

  test('主营业务信息显示', async ({ page }) => {
    await expect(page.getByText('主营业务')).toBeVisible()
    await expect(page.getByText(/跨境电商/).first()).toBeVisible()
  })

  test('办公地址信息显示', async ({ page }) => {
    await expect(page.getByText('办公地址')).toBeVisible()
    await expect(page.getByText(/深圳/).first()).toBeVisible()
  })

  test('联系电话信息显示', async ({ page }) => {
    await expect(page.getByText('联系电话')).toBeVisible()
    await expect(page.getByText('19328702460')).toBeVisible()
  })

  test('业务简介卡片存在', async ({ page }) => {
    await expect(page.getByText('业务简介')).toBeVisible()
  })

  test('业务简介包含物流定价描述', async ({ page }) => {
    await expect(page.getByText(/物流定价/).first()).toBeVisible()
    await expect(page.getByText(/跨境卖家/).first()).toBeVisible()
  })

  test('公司信息以表格形式展示', async ({ page }) => {
    await expect(page.locator('table')).toBeVisible()
    const rows = page.locator('table tbody tr')
    const count = await rows.count()
    expect(count).toBeGreaterThanOrEqual(4)
  })
})
