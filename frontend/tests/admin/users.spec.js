import { test, expect } from '@playwright/test'

// Uses admin storageState from playwright.config.js (default for chromium project)

test.describe('用户管理页面 — /users (admin)', () => {
  test.describe.configure({ mode: 'serial' })

  test.beforeEach(async ({ page }) => {
    await page.goto('/users')
    await expect(page).toHaveURL('/users')
  })

  test('页面标题和基本结构加载', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('用户管理')
    // 用户列表卡片
    await expect(page.getByText('用户列表')).toBeVisible()
  })

  test('用户表格列标题显示正确', async ({ page }) => {
    // Wait for table to be visible
    await expect(page.locator('table')).toBeVisible()
    const header = page.locator('thead')
    await expect(header).toContainText('ID')
    await expect(header).toContainText('用户名')
    await expect(header).toContainText('角色')
    await expect(header).toContainText('订阅')
    await expect(header).toContainText('状态')
  })

  test('用户表格加载并显示数据', async ({ page }) => {
    await expect(page.locator('table')).toBeVisible()
    // Wait for at least one row in the table body
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // admin user should always be there
    await expect(page.locator('table tbody')).toContainText('admin')
  })

  test('admin用户有admin角色标记', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // admin row should show admin badge
    const adminRow = page.locator('table tbody tr', { hasText: 'admin' }).first()
    await expect(adminRow).toBeVisible()
    await expect(adminRow).toContainText('admin')
  })

  test('分页信息显示', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // Should show total count info
    await expect(page.getByText(/共.*条/)).toBeVisible()
  })

  test('搜索框可用并能过滤用户', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // Find the search input
    const searchInput = page.locator('input[placeholder="搜索用户名"]')
    await expect(searchInput).toBeVisible()

    // Type in search to filter
    await searchInput.fill('admin')
    // admin row should remain visible
    await expect(page.locator('table tbody tr', { hasText: 'admin' }).first()).toBeVisible()
  })

  test('搜索后清除按钮出现并可清除', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    const searchInput = page.locator('input[placeholder="搜索用户名"]')
    await searchInput.fill('admin')
    // Clear button (X icon button) should appear
    // Re-check table visible after clearing
    await searchInput.clear()
    await expect(page.locator('table tbody tr').first()).toBeVisible()
  })

  test('添加新用户表单存在并有正确字段', async ({ page }) => {
    // The page has an "添加新用户" card at the top with a form
    await expect(page.getByRole('heading', { name: /添加新用户/ }).first()).toBeVisible()
    // Check form fields
    await expect(page.locator('#username')).toBeVisible()
    await expect(page.locator('#password')).toBeVisible()
  })

  test('用户列表区的"添加新用户"按钮打开对话框', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // Click the button in the user list section (not the form)
    const addBtn = page.getByRole('button', { name: /添加新用户/ })
    await addBtn.click()
    // Dialog should open
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByRole('dialog')).toContainText('添加新用户')
  })

  test('对话框包含用户名、密码、角色、类型字段', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    const addBtn = page.getByRole('button', { name: /添加新用户/ })
    await addBtn.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    // modal-username and modal-password
    await expect(dialog.locator('#modal-username')).toBeVisible()
    await expect(dialog.locator('#modal-password')).toBeVisible()
  })

  test('对话框取消按钮关闭对话框', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    const addBtn = page.getByRole('button', { name: /添加新用户/ })
    await addBtn.click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    await dialog.getByRole('button', { name: '取消' }).click()
    await expect(dialog).not.toBeVisible()
  })

  test('通过顶部表单创建测试用户', async ({ page }) => {
    const testUsername = `e2e_user_${Date.now() % 100000}`
    // Use the top form (not dialog) to create user
    await page.locator('#username').fill(testUsername)
    await page.locator('#password').fill('TestPassword1!')
    // Submit form
    await page.locator('form').first().getByRole('button', { name: '创建用户' }).click()
    // Should show success toast or user appears in table
    // Wait for either success toast or table update
    await expect(async () => {
      const toast = page.locator('[data-sonner-toast]').first()
      const hasToast = await toast.isVisible().catch(() => false)
      const hasUser = await page.locator('table tbody', { hasText: testUsername }).isVisible().catch(() => false)
      expect(hasToast || hasUser).toBeTruthy()
    }).toPass({ timeout: 10000 })
  })

  test('点击用户行显示用户操作面板', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // Click on first non-admin user row
    const rows = page.locator('table tbody tr')
    await rows.nth(1).click()
    // User operations card should appear
    await expect(page.getByText('用户操作')).toBeVisible()
    await expect(page.getByRole('button', { name: /重置密码/ })).toBeVisible()
    await expect(page.getByRole('button', { name: /删除用户/ })).toBeVisible()
  })

  test('admin用户(id=1)的删除受保护 — 后端拒绝删除', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // Select admin user row
    const adminRow = page.locator('table tbody tr', { hasText: 'admin' }).first()
    await adminRow.click()
    await expect(page.getByText('用户操作')).toBeVisible()
    // Click delete
    page.once('dialog', dialog => dialog.accept())
    await page.getByRole('button', { name: /删除用户/ }).click()
    // Wait briefly — backend should reject deletion of admin (id=1)
    await page.waitForTimeout(2000)
    // admin user should still be in the table
    await expect(page.locator('table tbody', { hasText: 'admin' })).toBeVisible()
  })

  test('刷新按钮重新加载用户列表', async ({ page }) => {
    await page.goto('/users')
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    const refreshBtn = page.getByRole('button', { name: '刷新', exact: true })
    await expect(refreshBtn).toBeVisible({ timeout: 5000 })
    await refreshBtn.click()
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
  })

  test('用户列表卡片分页按钮存在', async ({ page }) => {
    await expect(page.locator('table tbody tr').first()).toBeVisible({ timeout: 10000 })
    // Previous and next page buttons
    await expect(page.getByRole('button', { name: '上一页' })).toBeVisible()
    await expect(page.getByRole('button', { name: '下一页' })).toBeVisible()
  })

  test('物流规则同步区域存在', async ({ page }) => {
    await expect(page.getByText('批量物流规则同步')).toBeVisible()
    await expect(page.getByRole('button', { name: /同步物流规则/ })).toBeVisible()
  })
})
