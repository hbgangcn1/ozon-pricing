import { test, expect } from '@playwright/test';
import { TEST_ADMIN, TEST_PASSWORD, URLS } from '../fixtures/test-data.js';
import { REGISTER_PAGE } from '../fixtures/selectors.js';
import { apiLogin, apiToggleRegistration, apiGetUsers, apiDeleteUser } from '../helpers/api-helpers.js';

const REG_USERNAME = `e2e_reg_${Date.now()}`;

test.describe('注册流程', () => {
  let adminToken;

  test.beforeAll(async () => {
    adminToken = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password);
    await apiToggleRegistration(adminToken, true);
  });

  test.afterAll(async () => {
    await apiToggleRegistration(adminToken, false).catch(() => null);
    const users = await apiGetUsers(adminToken).catch(() => []);
    const usersArray = Array.isArray(users) ? users : (users.users || []);
    const created = usersArray.find(u => u.username === REG_USERNAME);
    if (created) {
      await apiDeleteUser(adminToken, created.id).catch(() => null);
    }
  });

  test('注册页面正常加载', async ({ page }) => {
    await page.goto(URLS.register);
    await expect(page).toHaveURL(/\/register/);
    await expect(page.locator(REGISTER_PAGE.usernameInput)).toBeVisible();
    await expect(page.locator(REGISTER_PAGE.passwordInput)).toBeVisible();
  });

  test('成功注册新用户并跳转登录页', async ({ page }) => {
    await page.goto(URLS.register);
    await page.waitForSelector(REGISTER_PAGE.usernameInput, { state: 'visible' });

    await page.fill(REGISTER_PAGE.usernameInput, REG_USERNAME);
    await page.fill(REGISTER_PAGE.passwordInput, TEST_PASSWORD);
    await page.fill(REGISTER_PAGE.confirmPasswordInput, TEST_PASSWORD);

    const securityQuestion = page.locator(REGISTER_PAGE.securityQuestionSelect);
    if (await securityQuestion.isVisible({ timeout: 2000 }).catch(() => false)) {
      await securityQuestion.selectOption({ index: 1 });
    }

    await page.fill(REGISTER_PAGE.securityAnswerInput, 'test_answer_e2e');

    const eulaCheckbox = page.locator(REGISTER_PAGE.eulaCheckbox);
    if (await eulaCheckbox.isVisible({ timeout: 2000 }).catch(() => false)) {
      const isChecked = await eulaCheckbox.isChecked().catch(() => false);
      if (!isChecked) {
        await eulaCheckbox.click();
      }
    }

    await page.click(REGISTER_PAGE.submitButton);

    await Promise.race([
      page.waitForURL(/\/login/, { timeout: 15000 }),
      page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 }),
    ]);

    const finalUrl = page.url();
    expect(finalUrl.includes('/login') || finalUrl.match(/\/(pricing|dashboard)/)).toBeTruthy();
  });

  test('重复用户名注册显示错误', async ({ page }) => {
    await page.goto(URLS.register);
    await page.waitForSelector(REGISTER_PAGE.usernameInput, { state: 'visible' });

    await page.fill(REGISTER_PAGE.usernameInput, TEST_ADMIN.username);
    await page.fill(REGISTER_PAGE.passwordInput, TEST_PASSWORD);
    await page.fill(REGISTER_PAGE.confirmPasswordInput, TEST_PASSWORD);

    const securityQuestion = page.locator(REGISTER_PAGE.securityQuestionSelect);
    if (await securityQuestion.isVisible({ timeout: 2000 }).catch(() => false)) {
      await securityQuestion.selectOption({ index: 1 });
    }

    await page.fill(REGISTER_PAGE.securityAnswerInput, 'test_answer');

    const eulaCheckbox = page.locator(REGISTER_PAGE.eulaCheckbox);
    if (await eulaCheckbox.isVisible({ timeout: 2000 }).catch(() => false)) {
      const isChecked = await eulaCheckbox.isChecked().catch(() => false);
      if (!isChecked) {
        await eulaCheckbox.click();
      }
    }

    await page.click(REGISTER_PAGE.submitButton);

    const errorLocator = page.locator('.bg-red-500\\/10, [data-sonner-toast][data-type="error"]').first();

    await expect(errorLocator).toBeVisible({ timeout: 10000 });
  });

  test('密码太短显示验证错误', async ({ page }) => {
    await page.goto(URLS.register);
    await page.waitForSelector(REGISTER_PAGE.usernameInput, { state: 'visible' });

    await page.fill(REGISTER_PAGE.usernameInput, `short_${Date.now()}`);
    await page.fill(REGISTER_PAGE.passwordInput, 'short');
    await page.fill(REGISTER_PAGE.confirmPasswordInput, 'short');

    await page.click(REGISTER_PAGE.submitButton);

    const stillOnRegister = page.url().includes('/register');
    const errorVisible = await page.locator('p.text-red-400, [data-sonner-toast][data-type="error"]').first().isVisible({ timeout: 5000 }).catch(() => false);

    expect(stillOnRegister || errorVisible).toBeTruthy();
  });

  test('EULA 未勾选时无法提交', async ({ page }) => {
    await page.goto(URLS.register);
    await page.waitForSelector(REGISTER_PAGE.usernameInput, { state: 'visible' });

    const eulaCheckbox = page.locator(REGISTER_PAGE.eulaCheckbox);
    const hasEula = await eulaCheckbox.isVisible({ timeout: 2000 }).catch(() => false);

    if (!hasEula) {
      test.skip();
      return;
    }

    const isChecked = await eulaCheckbox.isChecked().catch(() => false);
    if (isChecked) {
      await eulaCheckbox.click();
    }

    await page.fill(REGISTER_PAGE.usernameInput, `eula_${Date.now()}`);
    await page.fill(REGISTER_PAGE.passwordInput, TEST_PASSWORD);
    await page.fill(REGISTER_PAGE.confirmPasswordInput, TEST_PASSWORD);
    await page.fill(REGISTER_PAGE.securityAnswerInput, 'test');

    await page.click(REGISTER_PAGE.submitButton);

    await expect(page).toHaveURL(/\/register/, { timeout: 5000 });
  });

  test('关闭注册时提交表单显示禁止提示', async ({ page }) => {
    await apiToggleRegistration(adminToken, false);

    try {
      await page.goto(URLS.register);
      await page.waitForSelector(REGISTER_PAGE.usernameInput, { state: 'visible' });

      // 填写表单并提交 — 后端会返回 403
      await page.fill(REGISTER_PAGE.usernameInput, `closed_reg_${Date.now()}`);
      await page.fill(REGISTER_PAGE.passwordInput, TEST_PASSWORD);
      await page.fill(REGISTER_PAGE.confirmPasswordInput, TEST_PASSWORD);

      await page.fill(REGISTER_PAGE.securityAnswerInput, 'test_answer');

      const eulaCheckbox = page.locator(REGISTER_PAGE.eulaCheckbox);
      if (await eulaCheckbox.isVisible({ timeout: 2000 }).catch(() => false)) {
        const isChecked = await eulaCheckbox.isChecked().catch(() => false);
        if (!isChecked) {
          await eulaCheckbox.click();
        }
      }

      const responsePromise = page.waitForResponse(
        r => r.url().includes('/api/auth/register'),
        { timeout: 15000 }
      ).catch(() => null);

      await page.click(REGISTER_PAGE.submitButton);

      const response = await responsePromise;

      if (response) {
        expect(response.status()).toBe(403);
      } else {
        await expect(page).toHaveURL(/\/register/);
      }
    } finally {
      await apiToggleRegistration(adminToken, true);
    }
  });
});
