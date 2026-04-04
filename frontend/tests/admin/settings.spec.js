import { test, expect } from '@playwright/test'

test.describe('系统设置页面 — /settings (admin)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/settings')
    await expect(page).toHaveURL('/settings')
  })

  test('页面标题加载', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('系统设置')
    await expect(page.getByText('配置系统参数、备份管理和系统信息')).toBeVisible()
  })

  test('系统配置卡片存在', async ({ page }) => {
    await expect(page.getByText('系统配置')).toBeVisible()
  })

  test('开放注册开关存在', async ({ page }) => {
    await expect(page.getByText('开放注册')).toBeVisible()
    const switchEl = page.getByRole('switch')
    await expect(switchEl.first()).toBeVisible()
  })

  test('开放注册开关可以切换', async ({ page }) => {
    const switchEl = page.getByRole('switch').first()
    await expect(switchEl).toBeVisible()
    const initialState = await switchEl.getAttribute('aria-checked')
    await switchEl.click()
    await expect(async () => {
      const newState = await switchEl.getAttribute('aria-checked')
      expect(newState).not.toBe(initialState)
    }).toPass({ timeout: 5000 })
    await switchEl.click()
  })

  test('数据库备份管理卡片存在', async ({ page }) => {
    await expect(page.getByText('数据库备份管理')).toBeVisible()
  })

  test('备份列表标签页存在并默认激活', async ({ page }) => {
    const listTab = page.getByRole('tab', { name: /备份列表/ })
    await expect(listTab).toBeVisible()
    await expect(listTab).toHaveAttribute('data-state', 'active')
  })

  test('三个备份标签页都存在', async ({ page }) => {
    await expect(page.getByRole('tab', { name: /备份列表/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /自动备份设置/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /备份说明/ })).toBeVisible()
  })

  test('立即备份按钮存在', async ({ page }) => {
    await expect(page.getByRole('button', { name: /立即备份/ })).toBeVisible()
  })

  test('备份统计信息显示', async ({ page }) => {
    await expect(page.getByText(/共有.*个备份/)).toBeVisible({ timeout: 10000 })
  })

  test('备份列表区域显示（有数据或空状态）', async ({ page }) => {
    await page.waitForTimeout(2000)
    const hasTable = await page.locator('table').isVisible().catch(() => false)
    const hasEmpty = await page.getByText('暂无备份文件').isVisible().catch(() => false)
    const hasLoading = await page.getByText('加载中').isVisible().catch(() => false)
    expect(hasTable || hasEmpty || hasLoading).toBeTruthy()
  })

  test('切换到自动备份设置标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /自动备份设置/ }).click()
    await expect(page.getByText('自动备份', { exact: true })).toBeVisible()
    await expect(page.getByText('备份频率', { exact: true })).toBeVisible()
  })

  test('自动备份设置显示备份间隔和保留数量', async ({ page }) => {
    await page.getByRole('tab', { name: /自动备份设置/ }).click()
    await expect(page.locator('p.text-text-primary', { hasText: /每.*小时/ }).first()).toBeVisible()
    await expect(page.locator('p.text-text-primary', { hasText: /保留最近.*个/ }).first()).toBeVisible()
  })

  test('切换到备份说明标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /备份说明/ }).click()
    await expect(page.getByRole('heading', { name: /备份说明|如何恢复备份/ }).first()).toBeVisible()
  })

  test('FAQ区域存在', async ({ page }) => {
    await expect(page.getByText('常见问题')).toBeVisible()
  })

  test('FAQ项目可以展开', async ({ page }) => {
    await expect(page.getByText('备份文件格式是什么')).toBeVisible()
    await page.getByText('备份文件格式是什么').click()
    await expect(page.getByText(/PostgreSQL dump/)).toBeVisible()
  })
})
