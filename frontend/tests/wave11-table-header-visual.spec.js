import { test, expect } from '@playwright/test';

test.describe('Wave 11 Table Header Visual Regression', () => {
  test('logistics-pool virtual table header remains opaque after scroll', async ({ page }) => {
    await page.goto('/logistics-pool');
    
    const header = page.locator('[data-testid="virtual-table-header"]');
    await expect(header).toBeVisible({ timeout: 15000 });

    await page.waitForTimeout(2000);

    await header.evaluate((el) => {
      const container = el.closest('.overflow-auto');
      if (container) {
        container.scrollBy(0, 800);
      } else {
        window.scrollBy(0, 800);
      }
    });

    await page.waitForTimeout(500);

    await expect(header).toHaveScreenshot('logistics-pool-header.png', {
      maxDiffPixelRatio: 0.01,
      threshold: 0.2
    });
  });

  test('users shadcn table header remains opaque after scroll', async ({ page }) => {
    await page.goto('/users');
    
    const header = page.locator('table thead').first();
    await expect(header).toBeVisible({ timeout: 15000 });

    await page.waitForTimeout(2000);

    await expect(page.locator('table tbody tr').first()).toBeVisible();

    await header.evaluate((el) => {
      const container = el.closest('.overflow-auto');
      if (container) {
        container.scrollBy(0, 800);
      } else {
        window.scrollBy(0, 800);
      }
    });

    await page.waitForTimeout(500);

    await expect(header).toHaveScreenshot('users-header.png', {
      maxDiffPixelRatio: 0.01,
      threshold: 0.2
    });
  });
});
