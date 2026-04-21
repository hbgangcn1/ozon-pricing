import { expect } from '@playwright/test';
import { TEST_ADMIN, URLS } from '../fixtures/test-data.js';
import { LOGIN_PAGE } from '../fixtures/selectors.js';

export async function loginAsAdmin(page) {
  await loginAsUser(page, TEST_ADMIN.username, TEST_ADMIN.password);
}

export async function loginAsUser(page, username, password) {
  await page.goto(URLS.login);
  await page.waitForSelector(LOGIN_PAGE.usernameInput, { state: 'visible' });
  await page.fill(LOGIN_PAGE.usernameInput, username);
  await page.fill(LOGIN_PAGE.passwordInput, password);
  await page.click(LOGIN_PAGE.submitButton);
  await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });
  await expect(page).toHaveURL(/\/(pricing|dashboard)/);
}

export async function logout(page) {
  const userMenuCandidates = [
    '.ant-dropdown-trigger',
    '[aria-haspopup="menu"]',
    'button:has-text("admin")',
    'button:has-text("用户")',
    '.user-menu',
    '[data-testid="user-menu"]',
  ];

  let clicked = false;
  for (const selector of userMenuCandidates) {
    const el = page.locator(selector).first();
    if (await el.isVisible({ timeout: 2000 }).catch(() => false)) {
      await el.click();
      clicked = true;
      break;
    }
  }

  if (clicked) {
    const logoutBtn = page.locator('text=退出登录, text=Logout, text=登出').first();
    if (await logoutBtn.isVisible({ timeout: 3000 }).catch(() => false)) {
      await logoutBtn.click();
    }
  } else {
    await page.evaluate(() => {
      localStorage.removeItem('api_token');
      localStorage.removeItem('api_user');
    });
    await page.goto(URLS.login);
  }

  await page.waitForURL(/\/login/, { timeout: 10000 });
}

export async function clearAuthState(page) {
  await page.evaluate(() => {
    localStorage.removeItem('api_token');
    localStorage.removeItem('api_user');
  });
}
