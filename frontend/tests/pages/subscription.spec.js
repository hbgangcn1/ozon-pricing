import { test, expect } from '@playwright/test'

test.describe('订阅管理页面 — /subscription', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/subscription')
    await expect(page).toHaveURL('/subscription')
  })

  test('页面加载不崩溃', async ({ page }) => {
    await expect(page.locator('h1')).toBeVisible({ timeout: 10000 })
  })

  test('页面标题包含订阅管理', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('订阅管理')
  })

  test('当前套餐区域显示', async ({ page }) => {
    await expect(page.getByText('当前套餐').first()).toBeVisible()
  })

  test('套餐名称显示(管理员显示管理员)', async ({ page }) => {
    await expect(page.locator('h2').filter({ hasText: /管理员|免费版|效率版|专业版|企业版/ })).toBeVisible({ timeout: 10000 })
  })

  test('永久有效标签存在', async ({ page }) => {
    await expect(page.getByText('永久有效')).toBeVisible({ timeout: 10000 })
  })

  test('计算次数信息显示', async ({ page }) => {
    await expect(page.getByText(/计算次数/).first()).toBeVisible()
  })

  test('提示信息横幅显示', async ({ page }) => {
    await expect(page.getByText(/支付成功后.*刷新状态/)).toBeVisible()
  })

  test('套餐对比区域显示', async ({ page }) => {
    await expect(page.getByText('套餐对比')).toBeVisible()
  })

  test('四个套餐卡片显示', async ({ page }) => {
    await expect(page.getByText('免费版').first()).toBeVisible()
    await expect(page.getByText('效率版').first()).toBeVisible()
    await expect(page.getByText('专业版').first()).toBeVisible()
    await expect(page.getByText('企业版').first()).toBeVisible()
  })

  test('套餐卡片包含价格信息', async ({ page }) => {
    await expect(page.getByText(/¥\d+(?:\.\d+)?\s*\/月/).first()).toBeVisible()
    await expect(page.getByText(/¥\d{2,3}(?:\.\d+)?\s*\/月/).first()).toBeVisible()
  })

  test('套餐卡片包含功能列表', async ({ page }) => {
    await expect(page.getByText('极速模式').first()).toBeVisible()
    await expect(page.getByText('基础物流模板')).toBeVisible()
  })

  test('免费版显示"当前套餐"或"当前"标签(admin场景)', async ({ page }) => {
    const currentBadge = page.getByText('当前').first()
    await expect(currentBadge).toBeVisible()
  })

  test('非当前套餐显示升级按钮', async ({ page }) => {
    const upgradeBtn = page.getByRole('button', { name: /升级到/ }).first()
    await expect(upgradeBtn).toBeVisible()
  })

  test('企业版显示开发中标签', async ({ page }) => {
    await expect(page.getByText('开发中')).toBeVisible()
  })
})
