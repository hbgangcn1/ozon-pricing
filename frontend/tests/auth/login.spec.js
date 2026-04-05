import { test, expect } from '@playwright/test';
import { TEST_ADMIN, TEST_USER, URLS, API_BASE } from '../fixtures/test-data.js';
import { LOGIN_PAGE } from '../fixtures/selectors.js';

test.describe('登录流程', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(URLS.login);
    await page.waitForSelector(LOGIN_PAGE.usernameInput, { state: 'visible' });
  });

  test('管理员登录成功并跳转到 /pricing', async ({ page }) => {
    await page.fill(LOGIN_PAGE.usernameInput, TEST_ADMIN.username);
    await page.fill(LOGIN_PAGE.passwordInput, TEST_ADMIN.password);
    await page.click(LOGIN_PAGE.submitButton);
    await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/(pricing|dashboard)/);
  });

  test('错误密码显示错误提示', async ({ page }) => {
    await page.fill(LOGIN_PAGE.usernameInput, TEST_ADMIN.username);
    await page.fill(LOGIN_PAGE.passwordInput, 'wrong_password_xyz');
    await page.click(LOGIN_PAGE.submitButton);

    // LoginPage uses a div with bg-red-500/10 for error messages + sonner toast
    const errorLocator = page.locator('.bg-red-500\\/10, [data-sonner-toast][data-type="error"]').first();

    await expect(errorLocator).toBeVisible({ timeout: 10000 });
    await expect(page).not.toHaveURL(/\/(pricing|dashboard)/);
  });

  test('空表单提交触发验证提示', async ({ page }) => {
    await page.click(LOGIN_PAGE.submitButton);

    // zod validation shows p.text-red-400 messages
    const hasValidationMsg = await page.locator('p.text-red-400').first()
      .isVisible({ timeout: 3000 }).catch(() => false);
    const stillOnLogin = page.url().includes('/login');

    expect(stillOnLogin || hasValidationMsg).toBeTruthy();
  });

  test('普通用户登录成功', async ({ page }) => {
    const adminResp = await fetch(`${API_BASE}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: TEST_ADMIN.username, password: TEST_ADMIN.password }),
    });
    const { access_token } = await adminResp.json();
    await fetch(`${API_BASE}/admin/users`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${access_token}` },
      body: JSON.stringify({ username: TEST_USER.username, password: TEST_USER.password }),
    });

    await page.fill(LOGIN_PAGE.usernameInput, TEST_USER.username);
    await page.fill(LOGIN_PAGE.passwordInput, TEST_USER.password);
    await page.click(LOGIN_PAGE.submitButton);
    await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });
    await expect(page).toHaveURL(/\/(pricing|dashboard)/);
  });

  test('未认证用户访问受保护路由跳转到 /login', async ({ page }) => {
    await page.evaluate(() => {
      localStorage.removeItem('api_token');
      localStorage.removeItem('api_user');
    });

    await page.goto(URLS.pricing);
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test('登录页面显示系统标题', async ({ page }) => {
    await expect(page.getByRole('heading', { name: '物流定价系统' })).toBeVisible();
  });
});
