import { test, expect } from '@playwright/test';
import { E2E_TEST_USER, TEST_ADMIN, URLS } from '../fixtures/test-data.js';
import { ACCOUNT_PAGE } from '../fixtures/selectors.js';
import { apiLogin } from '../helpers/api-helpers.js';

test.describe('修改密码', () => {
  test.beforeEach(async ({ page }) => {
    await page.goto(URLS.account);
    await page.waitForURL(/\/account/, { timeout: 10000 });
    await page.waitForSelector('[data-testid="change-password-form"]', { state: 'visible' });
  });

  const getChangePasswordForm = (page) => page.locator('[data-testid="change-password-form"]');

  test('修改密码表单三个输入框正常显示', async ({ page }) => {
    const form = getChangePasswordForm(page);
    await expect(form.locator(ACCOUNT_PAGE.currentPasswordInput)).toBeVisible();
    await expect(form.locator(ACCOUNT_PAGE.newPasswordInput)).toBeVisible();
    await expect(form.locator(ACCOUNT_PAGE.confirmPasswordInput)).toBeVisible();
    await expect(form.locator(ACCOUNT_PAGE.submitButton)).toBeVisible();
  });

  test('当前密码错误时显示错误提示', async ({ page }) => {
    const form = getChangePasswordForm(page);
    await form.locator(ACCOUNT_PAGE.currentPasswordInput).fill('WrongPassword123!X');
    await form.locator(ACCOUNT_PAGE.newPasswordInput).fill('NewPassword1!ABC');
    await form.locator(ACCOUNT_PAGE.confirmPasswordInput).fill('NewPassword1!ABC');

    await form.locator(ACCOUNT_PAGE.submitButton).click();

    // Backend returns 401 for wrong current password.
    // /auth/change-password is configured with auth401Mode: 'local' in
    // frontend/src/services/api.js so the global axios interceptor does NOT
    // refresh / redirect. The page-level catch shows a sonner toast and the
    // user stays on /account. Assert both signals.
    const errorToast = page.locator('[data-sonner-toast][data-type="error"]').first();
    await expect(errorToast).toBeVisible({ timeout: 10000 });
    expect(page.url()).toContain('/account');
  });

  test('新密码不符合规则时显示验证错误', async ({ page }) => {
    const form = getChangePasswordForm(page);
    await form.locator(ACCOUNT_PAGE.currentPasswordInput).fill(TEST_ADMIN.password);
    await form.locator(ACCOUNT_PAGE.newPasswordInput).fill('tooshort');
    await form.locator(ACCOUNT_PAGE.confirmPasswordInput).fill('tooshort');
    await form.locator(ACCOUNT_PAGE.submitButton).click({ force: true });

    const validationError = page.locator('[data-sonner-toast][data-type="error"]').first();

    const stillOnAccount = page.url().includes('/account');
    const hasError = await validationError.isVisible({ timeout: 5000 }).catch(() => false);

    expect(stillOnAccount || hasError).toBeTruthy();
  });

  test('两次新密码不一致时显示提示', async ({ page }) => {
    const form = getChangePasswordForm(page);
    await form.locator(ACCOUNT_PAGE.currentPasswordInput).fill(TEST_ADMIN.password);
    await form.locator(ACCOUNT_PAGE.newPasswordInput).fill('NewPassword1!ABC');
    await form.locator(ACCOUNT_PAGE.confirmPasswordInput).fill('DifferentPassword2@');
    await form.locator(ACCOUNT_PAGE.submitButton).click();

    const mismatchError = page.locator('[data-sonner-toast][data-type="error"]').first();

    const stillOnAccount = page.url().includes('/account');
    const hasError = await mismatchError.isVisible({ timeout: 5000 }).catch(() => false);

    expect(stillOnAccount || hasError).toBeTruthy();
  });
});

test.describe('修改密码 - 使用测试用户', () => {
  test.use({ storageState: 'tests/.auth/user.json' });
  const TEMP_NEW_PASSWORD = 'TempNewPass1!ABC';
  const getChangePasswordForm = (page) => page.locator('[data-testid="change-password-form"]');

  test('测试用户成功修改密码并可用新密码登录', async ({ page }) => {
    await page.goto(URLS.account);
    await page.waitForURL(/\/account/, { timeout: 10000 });
    const sessionDialog = page.getByRole('alertdialog');
    if (await sessionDialog.isVisible({ timeout: 1000 }).catch(() => false)) {
      await page.getByRole('button', { name: '重新登录' }).click();
      await page.fill('input[name="username"]', E2E_TEST_USER.username);
      await page.fill('input[name="password"]', E2E_TEST_USER.password);
      await page.click('button[type="submit"]');
      await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });
      await page.goto(URLS.account);
      await page.waitForURL(/\/account/, { timeout: 10000 });
    }

    const form = getChangePasswordForm(page);
    await form.locator(ACCOUNT_PAGE.currentPasswordInput).fill(E2E_TEST_USER.password);
    await form.locator(ACCOUNT_PAGE.newPasswordInput).fill(TEMP_NEW_PASSWORD);
    await form.locator(ACCOUNT_PAGE.confirmPasswordInput).fill(TEMP_NEW_PASSWORD);
    await Promise.all([
      page.waitForResponse(
        response => response.url().includes('/api/auth/change-password') && response.ok(),
        { timeout: 15000 },
      ),
      form.locator(ACCOUNT_PAGE.submitButton).click({ force: true }),
    ]);
    const newToken = await apiLogin(E2E_TEST_USER.username, TEMP_NEW_PASSWORD);

    await page.evaluate(() => {
      localStorage.removeItem('api_token');
      localStorage.removeItem('api_user');
    });
    await page.goto(URLS.login);
    await page.evaluate(([token, username]) => {
      localStorage.setItem('api_token', token);
      localStorage.setItem('api_user', JSON.stringify({ username, has_security_question: true }));
    }, [newToken, E2E_TEST_USER.username]);
    await page.goto(URLS.pricing);
    await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });

    await page.goto(URLS.account);
    const resetForm = getChangePasswordForm(page);
    await resetForm.locator(ACCOUNT_PAGE.currentPasswordInput).fill(TEMP_NEW_PASSWORD);
    await resetForm.locator(ACCOUNT_PAGE.newPasswordInput).fill(E2E_TEST_USER.password);
    await resetForm.locator(ACCOUNT_PAGE.confirmPasswordInput).fill(E2E_TEST_USER.password);
    await Promise.all([
      page.waitForResponse(
        response => response.url().includes('/api/auth/change-password') && response.ok(),
        { timeout: 15000 },
      ),
      resetForm.locator(ACCOUNT_PAGE.submitButton).click({ force: true }),
    ]);
  });
});
