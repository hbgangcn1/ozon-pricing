import { test as setup, expect } from '@playwright/test';
import path from 'path';
import { fileURLToPath } from 'url';
import { TEST_ADMIN, TEST_USER, URLS } from './fixtures/test-data.js';
import { LOGIN_PAGE } from './fixtures/selectors.js';
import { apiLogin, apiCreateUser, apiGetUsers, apiToggleRegistration } from './helpers/api-helpers.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ADMIN_AUTH_FILE = path.join(__dirname, '.auth', 'admin.json');
const USER_AUTH_FILE = path.join(__dirname, '.auth', 'user.json');

setup('authenticate as admin', async ({ page }) => {
  await page.goto(URLS.login);
  await page.waitForSelector(LOGIN_PAGE.usernameInput, { state: 'visible' });
  await page.fill(LOGIN_PAGE.usernameInput, TEST_ADMIN.username);
  await page.fill(LOGIN_PAGE.passwordInput, TEST_ADMIN.password);
  await page.click(LOGIN_PAGE.submitButton);
  await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 20000 });
  await expect(page).toHaveURL(/\/(pricing|dashboard)/);
  await page.context().storageState({ path: ADMIN_AUTH_FILE });
});

setup('authenticate as regular user', async ({ page }) => {
  const adminToken = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password);

  const existingUsers = await apiGetUsers(adminToken, TEST_USER.username);
  const usersArray = Array.isArray(existingUsers) ? existingUsers : (existingUsers.users || []);
  const existingUser = usersArray.find(u => u.username === TEST_USER.username);

  if (!existingUser) {
    await apiToggleRegistration(adminToken, true).catch(() => null);

    await apiCreateUser(adminToken, {
      username: TEST_USER.username,
      password: TEST_USER.password,
      confirm_password: TEST_USER.password,
      security_question: '您母亲的姓名？',
      security_answer: 'e2e_answer',
      role: 'user',
    }).catch(async (err) => {
      if (!err.message.includes('409') && !err.message.includes('already')) {
        throw err;
      }
    });
  }

  await page.goto(URLS.login);
  await page.waitForSelector(LOGIN_PAGE.usernameInput, { state: 'visible' });
  await page.fill(LOGIN_PAGE.usernameInput, TEST_USER.username);
  await page.fill(LOGIN_PAGE.passwordInput, TEST_USER.password);
  await page.click(LOGIN_PAGE.submitButton);
  await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 20000 });
  await expect(page).toHaveURL(/\/(pricing|dashboard)/);
  await page.context().storageState({ path: USER_AUTH_FILE });
});
