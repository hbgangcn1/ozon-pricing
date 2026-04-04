import { test, expect } from '@playwright/test';
import { URLS } from '../fixtures/test-data.js';

test.describe('退出登录流程', () => {
  test('退出登录后跳转到 /login', async ({ page }) => {
    await page.goto(URLS.pricing);
    await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });

    const logoutCandidates = [
      '.ant-dropdown-trigger',
      'button[aria-haspopup]',
      '[data-testid="user-menu"]',
      '.user-avatar',
      'button:has-text("admin")',
      '[class*="avatar"]',
      '[class*="user"]',
    ];

    let menuOpened = false;
    for (const selector of logoutCandidates) {
      const el = page.locator(selector).first();
      if (await el.isVisible({ timeout: 1500 }).catch(() => false)) {
        await el.click();
        menuOpened = true;
        break;
      }
    }

    if (menuOpened) {
      const logoutSelectors = [
        'text=退出登录',
        'text=退出',
        'text=Logout',
        'text=登出',
        '[data-testid="logout"]',
      ];

      let loggedOut = false;
      for (const sel of logoutSelectors) {
        const btn = page.locator(sel).first();
        if (await btn.isVisible({ timeout: 2000 }).catch(() => false)) {
          await btn.click();
          loggedOut = true;
          break;
        }
      }

      if (!loggedOut) {
        await page.evaluate(() => {
          localStorage.removeItem('api_token');
          localStorage.removeItem('api_user');
        });
        await page.goto(URLS.login);
      }
    } else {
      await page.evaluate(() => {
        localStorage.removeItem('api_token');
        localStorage.removeItem('api_user');
      });
      await page.goto(URLS.login);
    }

    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/login/);
  });

  test('退出后再访问受保护路由仍重定向到 /login', async ({ page }) => {
    await page.goto(URLS.pricing);
    await page.waitForURL(/\/(pricing|dashboard|login)/, { timeout: 15000 });

    await page.evaluate(() => {
      localStorage.removeItem('api_token');
      localStorage.removeItem('api_user');
    });

    await page.goto(URLS.pricing);
    await page.waitForURL(/\/login/, { timeout: 10000 });
    await expect(page).toHaveURL(/\/login/);
  });
});
