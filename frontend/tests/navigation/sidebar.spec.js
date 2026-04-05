import { test, expect } from '@playwright/test'

test.describe('侧边栏导航 — sidebar (admin)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/pricing')
    await expect(page).toHaveURL('/pricing')
  })

  test('侧边栏在保护页面可见', async ({ page }) => {
    await expect(page.locator('nav')).toBeVisible()
  })

  test('侧边栏Logo存在', async ({ page }) => {
    await expect(page.locator('nav').getByText('物流定价')).toBeVisible()
  })

  test('物流定价菜单项存在', async ({ page }) => {
    await expect(page.locator('nav a[href="/pricing"]')).toBeVisible()
    await expect(page.locator('nav').getByText('物流定价')).toBeVisible()
  })

  test('物流管理菜单项存在', async ({ page }) => {
    await expect(page.locator('nav a[href="/logistics"]')).toBeVisible()
    await expect(page.locator('nav').getByText('物流管理')).toBeVisible()
  })

  test('账号管理菜单项存在', async ({ page }) => {
    await expect(page.locator('nav a[href="/account"]')).toBeVisible()
    await expect(page.locator('nav').getByText('账号管理')).toBeVisible()
  })

  test('订阅管理菜单项存在', async ({ page }) => {
    await expect(page.locator('nav a[href="/subscription"]')).toBeVisible()
    await expect(page.locator('nav').getByText('订阅管理')).toBeVisible()
  })

  test('关于系统菜单项存在', async ({ page }) => {
    await expect(page.locator('nav a[href="/about"]')).toBeVisible()
    await expect(page.locator('nav').getByText('关于系统')).toBeVisible()
  })

  test('管理员可以看到系统设置菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/settings"]')).toBeVisible()
    await expect(page.locator('nav').getByText('系统设置')).toBeVisible()
  })

  test('管理员可以看到用户管理菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/users"]')).toBeVisible()
    await expect(page.locator('nav').getByText('用户管理')).toBeVisible()
  })

  test('管理员可以看到方案管理菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/plans"]')).toBeVisible()
    await expect(page.locator('nav').getByText('方案管理')).toBeVisible()
  })

  test('管理员可以看到数据统计菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/statistics"]')).toBeVisible()
    await expect(page.locator('nav').getByText('数据统计')).toBeVisible()
  })

  test('点击物流管理导航到/logistics', async ({ page }) => {
    await page.locator('nav a[href="/logistics"]').click()
    await expect(page).toHaveURL('/logistics')
  })

  test('点击账号管理导航到/account', async ({ page }) => {
    await page.locator('nav a[href="/account"]').click()
    await expect(page).toHaveURL('/account')
    await expect(page.locator('h1')).toContainText('账户管理')
  })

  test('点击订阅管理导航到/subscription', async ({ page }) => {
    await page.locator('nav a[href="/subscription"]').click()
    await expect(page).toHaveURL('/subscription')
    await expect(page.locator('h1')).toContainText('订阅管理')
  })

  test('点击系统设置导航到/settings', async ({ page }) => {
    await page.locator('nav a[href="/settings"]').click()
    await expect(page).toHaveURL('/settings')
    await expect(page.locator('h1')).toContainText('系统设置')
  })

  test('点击用户管理导航到/users', async ({ page }) => {
    await page.locator('nav a[href="/users"]').click()
    await expect(page).toHaveURL('/users')
    await expect(page.locator('h1')).toContainText('用户管理')
  })

  test('点击数据统计导航到/statistics', async ({ page }) => {
    await page.locator('nav a[href="/statistics"]').click()
    await expect(page).toHaveURL('/statistics')
    await expect(page.locator('h1')).toContainText('数据统计')
  })

  test('点击关于系统导航到/about', async ({ page }) => {
    await page.locator('nav a[href="/about"]').click()
    await expect(page).toHaveURL('/about')
    await expect(page.locator('h1')).toContainText('关于我们')
  })

  test('当前激活菜单项有视觉高亮', async ({ page }) => {
    const pricingLink = page.locator('nav a[href="/pricing"]')
    const pricingClass = await pricingLink.getAttribute('class')
    expect(pricingClass).toContain('bg-surface-container')
  })

  test('点击物流定价后激活高亮切换', async ({ page }) => {
    await page.locator('nav a[href="/account"]').click()
    await expect(page).toHaveURL('/account')
    await page.locator('nav a[href="/pricing"]').click()
    await expect(page).toHaveURL('/pricing')
    const pricingLink = page.locator('nav a[href="/pricing"]')
    const pricingClass = await pricingLink.getAttribute('class')
    expect(pricingClass).toContain('bg-surface-container')
  })

  test('侧边栏收起按钮存在', async ({ page }) => {
    await expect(page.locator('button').filter({ has: page.locator('svg') }).last()).toBeVisible()
  })

  test('实时汇率下拉存在', async ({ page }) => {
    await expect(page.getByText('实时汇率')).toBeVisible()
  })
})

test.describe('侧边栏导航 — 普通用户看不到管理员菜单', () => {
  test.use({ storageState: 'tests/.auth/user.json' })

  test.beforeEach(async ({ page }) => {
    await page.goto('/pricing')
    await expect(page).toHaveURL('/pricing')
  })

  test('普通用户看不到系统设置菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/settings"]')).not.toBeVisible()
  })

  test('普通用户看不到用户管理菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/users"]')).not.toBeVisible()
  })

  test('普通用户看不到数据统计菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/statistics"]')).not.toBeVisible()
  })

  test('普通用户看不到方案管理菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/plans"]')).not.toBeVisible()
  })

  test('普通用户可以看到物流定价菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/pricing"]')).toBeVisible()
  })

  test('普通用户可以看到账号管理菜单项', async ({ page }) => {
    await expect(page.locator('nav a[href="/account"]')).toBeVisible()
  })
})
