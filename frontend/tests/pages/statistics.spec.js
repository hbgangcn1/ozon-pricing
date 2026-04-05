import { test, expect } from '@playwright/test'

test.describe('数据统计页面 — /statistics (admin)', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/statistics')
    await expect(page).toHaveURL('/statistics')
  })

  test('页面加载不崩溃', async ({ page }) => {
    const bodyText = await page.evaluate(() => document.body.innerText)
    expect(bodyText.length).toBeGreaterThan(50)
  })

  test('页面标题包含数据统计', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('数据统计')
  })

  test('标签页列表存在', async ({ page }) => {
    await expect(page.getByRole('tablist')).toBeVisible()
  })

  test('七个标签页都存在', async ({ page }) => {
    await expect(page.getByRole('tab', { name: /总览/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /留存分析/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /用户活跃/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /充值与收入/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /操作日志/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /登录记录/ })).toBeVisible()
    await expect(page.getByRole('tab', { name: /异常监控/ })).toBeVisible()
  })

  test('总览标签页默认激活显示统计卡片', async ({ page }) => {
    await expect(page.getByRole('tab', { name: /总览/ })).toHaveAttribute('data-state', 'active')
    await expect(page.getByText('总用户数')).toBeVisible()
    await expect(page.getByText('活跃用户')).toBeVisible()
    await expect(page.getByText('今日新增')).toBeVisible()
    await expect(page.getByText('总收入')).toBeVisible()
  })

  test('总览显示套餐分布', async ({ page }) => {
    await expect(page.getByText('专业版用户')).toBeVisible()
    await expect(page.getByText('效率版用户')).toBeVisible()
    await expect(page.getByText('免费版用户')).toBeVisible()
  })

  test('总览显示用户留存趋势', async ({ page }) => {
    await expect(page.getByText('用户留存趋势')).toBeVisible()
  })

  test('切换到留存分析标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /留存分析/ }).click()
    await expect(page.getByText('用户留存率分析')).toBeVisible()
    await expect(page.locator('table')).toBeVisible()
  })

  test('切换到用户活跃标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /用户活跃/ }).click()
    await expect(page.getByText('用户活跃统计')).toBeVisible()
    await expect(page.getByText('日活趋势')).toBeVisible()
  })

  test('切换到充值与收入标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /充值与收入/ }).click()
    await expect(page.getByText('本月收入')).toBeVisible()
    await expect(page.getByText('累计收入')).toBeVisible()
    await expect(page.getByText('月度收入趋势')).toBeVisible()
  })

  test('切换到操作日志标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /操作日志/ }).click()
    await expect(page.getByText('管理员操作日志')).toBeVisible()
    await expect(page.locator('table')).toBeVisible()
    const header = page.locator('thead')
    await expect(header).toContainText('管理员')
    await expect(header).toContainText('操作内容')
    await expect(header).toContainText('时间')
  })

  test('切换到登录记录标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /登录记录/ }).click()
    await expect(page.getByText('用户登录记录')).toBeVisible()
    await expect(page.locator('table')).toBeVisible()
    const header = page.locator('thead')
    await expect(header).toContainText('用户名')
    await expect(header).toContainText('操作')
    await expect(header).toContainText('状态')
  })

  test('切换到异常监控标签页', async ({ page }) => {
    await page.getByRole('tab', { name: /异常监控/ }).click()
    await expect(page.getByText('系统异常告警')).toBeVisible()
    await expect(page.getByText(/暂无异常|系统运行正常/).first()).toBeVisible()
  })

  test('操作日志有导出按钮', async ({ page }) => {
    await page.getByRole('tab', { name: /操作日志/ }).click()
    await expect(page.getByRole('button', { name: /导出/ })).toBeVisible()
  })

  test('登录记录有搜索框', async ({ page }) => {
    await page.getByRole('tab', { name: /登录记录/ }).click()
    await expect(page.locator('input[placeholder*="搜索"]')).toBeVisible()
  })
})
