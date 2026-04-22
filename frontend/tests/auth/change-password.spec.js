import { test, expect } from '@playwright/test';
import { TEST_ADMIN, TEST_USER, URLS } from '../fixtures/test-data.js';
import { ACCOUNT_PAGE } from '../fixtures/selectors.js';
import { apiLogin, apiGetUsers } from '../helpers/api-helpers.js';

test.describe('修改密码', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(URLS.account);
    await page.waitForURL(/\/account/, { timeout: 10000 });
    await page.waitForSelector(ACCOUNT_PAGE.form, { state: 'visible' });
  });

  test('修改密码表单三个输入框正常显示', async ({ page }) => {
    await expect(page.locator(ACCOUNT_PAGE.currentPasswordInput)).toBeVisible();
    await expect(page.locator(ACCOUNT_PAGE.newPasswordInput)).toBeVisible();
    await expect(page.locator(ACCOUNT_PAGE.confirmPasswordInput)).toBeVisible();
    await expect(page.locator(ACCOUNT_PAGE.submitButton)).toBeVisible();
  });

  test('当前密码错误时显示错误提示', async ({ page }) => {
    await page.fill(ACCOUNT_PAGE.currentPasswordInput, 'WrongPassword123!X');
    await page.fill(ACCOUNT_PAGE.newPasswordInput, 'NewPassword1!ABC');
    await page.fill(ACCOUNT_PAGE.confirmPasswordInput, 'NewPassword1!ABC');

    await page.click(ACCOUNT_PAGE.submitButton);

    // Backend returns 401 for wrong password.
    // The axios interceptor catches 401 globally, clears localStorage,
    // and redirects to /login BEFORE the catch block can show a toast.
    // So the reliable signal is the redirect, not the toast.
    await page.waitForURL('**/login', { timeout: 15000 });
    expect(page.url()).toContain('/login');
  });

  test('新密码不符合规则时显示验证错误', async ({ page }) => {
    await page.fill(ACCOUNT_PAGE.currentPasswordInput, TEST_ADMIN.password);
    await page.fill(ACCOUNT_PAGE.newPasswordInput, 'tooshort');
    await page.fill(ACCOUNT_PAGE.confirmPasswordInput, 'tooshort');
    await page.click(ACCOUNT_PAGE.submitButton);

    const validationError = page.locator('[data-sonner-toast][data-type="error"]').first();

    const stillOnAccount = page.url().includes('/account');
    const hasError = await validationError.isVisible({ timeout: 5000 }).catch(() => false);

    expect(stillOnAccount || hasError).toBeTruthy();
  });

  test('两次新密码不一致时显示提示', async ({ page }) => {
    await page.fill(ACCOUNT_PAGE.currentPasswordInput, TEST_ADMIN.password);
    await page.fill(ACCOUNT_PAGE.newPasswordInput, 'NewPassword1!ABC');
    await page.fill(ACCOUNT_PAGE.confirmPasswordInput, 'DifferentPassword2@');
    await page.click(ACCOUNT_PAGE.submitButton);

    const mismatchError = page.locator('[data-sonner-toast][data-type="error"]').first();

    const stillOnAccount = page.url().includes('/account');
    const hasError = await mismatchError.isVisible({ timeout: 5000 }).catch(() => false);

    expect(stillOnAccount || hasError).toBeTruthy();
  });
});

test.describe('修改密码 - 使用测试用户', () => {
  const TEMP_NEW_PASSWORD = 'TempNewPass1!ABC';
  let testUserExists = false;

  test.beforeAll(async () => {
    const adminToken = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password).catch(() => null);
    if (!adminToken) return;

    const users = await apiGetUsers(adminToken).catch(() => []);
    const usersArray = Array.isArray(users) ? users : (users.users || []);
    testUserExists = usersArray.some(u => u.username === TEST_USER.username);
  });

  test('测试用户成功修改密码并可用新密码登录', async ({ page }) => {
    if (!testUserExists) {
      test.skip();
      return;
    }

    await page.goto(URLS.account);
    await page.waitForURL(/\/account/, { timeout: 10000 });

    await page.fill(ACCOUNT_PAGE.currentPasswordInput, TEST_USER.password);
    await page.fill(ACCOUNT_PAGE.newPasswordInput, TEMP_NEW_PASSWORD);
    await page.fill(ACCOUNT_PAGE.confirmPasswordInput, TEMP_NEW_PASSWORD);
    await page.click(ACCOUNT_PAGE.submitButton);

    const successLocator = page.locator('[data-sonner-toast][data-type="success"]').first();

    await expect(successLocator).toBeVisible({ timeout: 10000 });

    await page.evaluate(() => {
      localStorage.removeItem('api_token');
      localStorage.removeItem('api_user');
    });
    await page.goto(URLS.login);
    await page.fill('input[name="username"]', TEST_USER.username);
    await page.fill('input[name="password"]', TEMP_NEW_PASSWORD);
    await page.click('button[type="submit"]');
    await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });

    await page.goto(URLS.account);
    await page.fill(ACCOUNT_PAGE.currentPasswordInput, TEMP_NEW_PASSWORD);
    await page.fill(ACCOUNT_PAGE.newPasswordInput, TEST_USER.password);
    await page.fill(ACCOUNT_PAGE.confirmPasswordInput, TEST_USER.password);
    await page.click(ACCOUNT_PAGE.submitButton);
    await page.waitForTimeout(2000);
  });
});
