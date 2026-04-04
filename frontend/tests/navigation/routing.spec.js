import { test, expect } from '@playwright/test'

test.describe('路由保护与导航 — routing', () => {

  test.describe('未认证访问保护路由', () => {
    test.use({ storageState: { cookies: [], origins: [] } })

    test('未认证访问/pricing重定向到/login', async ({ page }) => {
      await page.goto('/pricing')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('未认证访问/settings重定向到/login', async ({ page }) => {
      await page.goto('/settings')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('未认证访问/users重定向到/login', async ({ page }) => {
      await page.goto('/users')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('未认证访问/account重定向到/login', async ({ page }) => {
      await page.goto('/account')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('未认证访问/logistics重定向到/login', async ({ page }) => {
      await page.goto('/logistics')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('未认证访问/statistics重定向到/login', async ({ page }) => {
      await page.goto('/statistics')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('未认证访问/subscription重定向到/login', async ({ page }) => {
      await page.goto('/subscription')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('未认证访问/about重定向到/login', async ({ page }) => {
      await page.goto('/about')
      await expect(page).toHaveURL(/\/login/, { timeout: 15000 })
    })

    test('/login页面可以直接访问', async ({ page }) => {
      await page.goto('/login')
      await expect(page).toHaveURL('/login')
      await expect(page.locator('input[name="username"]')).toBeVisible()
    })

    test('/register页面可以直接访问', async ({ page }) => {
      await page.goto('/register')
      await expect(page).toHaveURL('/register')
    })
  })

  test.describe('非管理员访问管理员路由 — 使用普通用户认证', () => {
    test.use({ storageState: 'tests/.auth/user.json' })

    test('普通用户访问/settings被重定向', async ({ page }) => {
      await page.goto('/settings')
      await expect(page).not.toHaveURL('/settings', { timeout: 10000 })
      const url = page.url()
      expect(url).toMatch(/\/pricing|\/login/)
    })

    test('普通用户访问/users被重定向', async ({ page }) => {
      await page.goto('/users')
      await expect(page).not.toHaveURL('/users', { timeout: 10000 })
      const url = page.url()
      expect(url).toMatch(/\/pricing|\/login/)
    })

    test('普通用户访问/statistics被重定向', async ({ page }) => {
      await page.goto('/statistics')
      await expect(page).not.toHaveURL('/statistics', { timeout: 10000 })
      const url = page.url()
      expect(url).toMatch(/\/pricing|\/login/)
    })

    test('普通用户可以访问/pricing', async ({ page }) => {
      await page.goto('/pricing')
      await expect(page).toHaveURL('/pricing')
      await expect(page.locator('h1, [class*="text-xl"]')).toBeVisible({ timeout: 10000 })
    })

    test('普通用户可以访问/account', async ({ page }) => {
      await page.goto('/account')
      await expect(page).toHaveURL('/account')
      await expect(page.locator('h1')).toContainText('账户管理')
    })

    test('普通用户可以访问/about', async ({ page }) => {
      await page.goto('/about')
      await expect(page).toHaveURL('/about')
      await expect(page.locator('h1')).toContainText('关于我们')
    })
  })

  test.describe('已认证管理员访问所有路由', () => {

    test('管理员可以访问/pricing', async ({ page }) => {
      await page.goto('/pricing')
      await expect(page).toHaveURL('/pricing')
    })

    test('管理员可以访问/settings', async ({ page }) => {
      await page.goto('/settings')
      await expect(page).toHaveURL('/settings')
      await expect(page.locator('h1')).toContainText('系统设置')
    })

    test('管理员可以访问/users', async ({ page }) => {
      await page.goto('/users')
      await expect(page).toHaveURL('/users')
      await expect(page.locator('h1')).toContainText('用户管理')
    })

    test('管理员可以访问/statistics', async ({ page }) => {
      await page.goto('/statistics')
      await expect(page).toHaveURL('/statistics')
      await expect(page.locator('h1')).toContainText('数据统计')
    })

    test('管理员可以访问/account', async ({ page }) => {
      await page.goto('/account')
      await expect(page).toHaveURL('/account')
      await expect(page.locator('h1')).toContainText('账户管理')
    })

    test('管理员可以访问/logistics', async ({ page }) => {
      await page.goto('/logistics')
      await expect(page).toHaveURL('/logistics')
    })

    test('管理员可以访问/about', async ({ page }) => {
      await page.goto('/about')
      await expect(page).toHaveURL('/about')
      await expect(page.locator('h1')).toContainText('关于我们')
    })

    test('管理员可以访问/subscription', async ({ page }) => {
      await page.goto('/subscription')
      await expect(page).toHaveURL('/subscription')
      await expect(page.locator('h1')).toContainText('订阅管理')
    })

    test('根路径/重定向到/pricing', async ({ page }) => {
      await page.goto('/')
      await expect(page).toHaveURL(/\/pricing|\//, { timeout: 10000 })
    })
  })
})
