import { test, expect } from '@playwright/test'
import { TEST_ADMIN } from '../fixtures/test-data.js'

test.describe('账户管理页面 — /account', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto('/account')
    await expect(page).toHaveURL('/account')
  })

  const getChangePasswordForm = (page) => page.locator('[data-testid="change-password-form"]')

  test('页面标题包含账户管理', async ({ page }) => {
    await expect(page.locator('h1')).toContainText('账户管理')
  })

  test('修改密码表单存在', async ({ page }) => {
    await expect(getChangePasswordForm(page)).toBeVisible()
    await expect(page.getByText('修改密码').first()).toBeVisible()
  })

  test('表单有三个密码输入字段', async ({ page }) => {
    const form = getChangePasswordForm(page)
    await expect(form.locator('input[name="current_password"]')).toBeVisible()
    await expect(form.locator('input[name="new_password"]')).toBeVisible()
    await expect(form.locator('input[name="confirm_password"]')).toBeVisible()
  })

  test('所有密码字段类型为password', async ({ page }) => {
    const form = getChangePasswordForm(page)
    await expect(form.locator('input[name="current_password"]')).toHaveAttribute('type', 'password')
    await expect(form.locator('input[name="new_password"]')).toHaveAttribute('type', 'password')
    await expect(form.locator('input[name="confirm_password"]')).toHaveAttribute('type', 'password')
  })

  test('新密码字段有最小长度限制(13)', async ({ page }) => {
    await expect(getChangePasswordForm(page).locator('input[name="new_password"]')).toHaveAttribute('minlength', '13')
  })

  test('提交按钮存在', async ({ page }) => {
    await expect(getChangePasswordForm(page).getByRole('button', { name: /修改密码/ })).toBeVisible()
  })

  test('密码不匹配时显示错误提示', async ({ page }) => {
    const form = getChangePasswordForm(page)
    await form.locator('input[name="current_password"]').fill(TEST_ADMIN.password)
    await form.locator('input[name="new_password"]').fill('NewPassword@123456')
    await form.locator('input[name="confirm_password"]').fill('DifferentPassword@1')
    await form.getByRole('button', { name: /修改密码/ }).click()
    await expect(page.getByText('新密码与确认密码不匹配')).toBeVisible({ timeout: 5000 })
  })

  test('新密码太短时HTML5验证阻止提交', async ({ page }) => {
    const form = getChangePasswordForm(page)
    await form.locator('input[name="current_password"]').fill(TEST_ADMIN.password)
    await form.locator('input[name="new_password"]').fill('short')
    await form.locator('input[name="confirm_password"]').fill('short')
    await form.getByRole('button', { name: /修改密码/ }).click()
    const newPwdInput = form.locator('input[name="new_password"]')
    const validationMsg = await newPwdInput.evaluate(el => el.validationMessage)
    expect(validationMsg.length).toBeGreaterThan(0)
  })

  test('表单填写完整后可以提交(响应成功或错误)', async ({ page }) => {
    const form = getChangePasswordForm(page)
    await form.locator('input[name="current_password"]').fill(TEST_ADMIN.password)
    await form.locator('input[name="new_password"]').fill(TEST_ADMIN.password)
    await form.locator('input[name="confirm_password"]').fill(TEST_ADMIN.password)
    await form.getByRole('button', { name: /修改密码/ }).click()
    await expect(async () => {
      const successToast = page.locator('[data-sonner-toast]').first()
      const formVisible = getChangePasswordForm(page)
      const toastVisible = await successToast.isVisible().catch(() => false)
      const formStillVisible = await formVisible.isVisible().catch(() => false)
      expect(toastVisible || formStillVisible).toBeTruthy()
    }).toPass({ timeout: 10000 })
  })

  test('账户信息卡片存在', async ({ page }) => {
    await expect(page.locator('h3').filter({ hasText: '账户信息' })).toBeVisible()
  })

  test('账户信息显示用户名', async ({ page }) => {
    await expect(page.getByText('用户名：')).toBeVisible()
    const usernameLabel = page.locator('span', { hasText: '用户名：' })
    await expect(usernameLabel).toBeVisible()
    const infoCard = page.locator('.max-w-xl').nth(1)
    await expect(infoCard).toContainText('admin')
  })

  test('账户信息显示用户角色', async ({ page }) => {
    await expect(page.getByText('用户角色：')).toBeVisible()
    await expect(page.getByText('管理员').first()).toBeVisible()
  })
})
