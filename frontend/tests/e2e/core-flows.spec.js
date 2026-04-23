import { test, expect } from '@playwright/test';
import { apiCreateProduct, apiGetProducts } from '../helpers/api-helpers.js';
import { getAdminToken } from '../helpers/admin-token.js';
import { ADMIN_AUTH_FILE, ADMIN_MARKER_FILE } from '../helpers/auth-paths.js';

test.describe('核心业务流程测试', () => {
  test.describe.configure({ mode: 'serial' });
  test.setTimeout(60000);

  test('产品完整CRUD流程', async ({ page, request }) => {
    const uniqueName = `EP${Date.now() % 10000}`;
    const editedName = `${uniqueName}E`;

    const adminToken = await getAdminToken(request, { authFile: ADMIN_AUTH_FILE, markerFile: ADMIN_MARKER_FILE });
    const product = await apiCreateProduct(adminToken, {
      name: uniqueName,
      unit_price: 99,
      weight_g: 500,
      length_cm: 20,
      width_cm: 15,
      height_cm: 10,
    });
    expect(product).toBeTruthy();

    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await page.getByRole('tab', { name: /精准模式/ }).click();
    await page.waitForTimeout(500);

    const openBtn = page.getByRole('button', { name: /打开产品列表/ });
    if (await openBtn.isVisible().catch(() => false)) {
      await Promise.all([
        page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
        openBtn.click(),
      ]);
    }
    const listDialog = page.locator('[role="dialog"]');
    await expect(listDialog).toBeVisible({ timeout: 5000 });
    await page.waitForTimeout(500);

    const row = listDialog.locator('.font-medium', { hasText: uniqueName }).first();
    await expect(row).toBeVisible({ timeout: 10000 });

    await row.locator('..').locator('..').locator('button').first().click();
    await page.waitForTimeout(300);

    const editDialog = page.locator('[role="dialog"]');
    await expect(editDialog).toBeVisible({ timeout: 5000 });
    const nameInput = editDialog.locator('input').first();
    await nameInput.click();
    await page.keyboard.press('Control+a');
    await page.keyboard.type(editedName, { delay: 20 });

    await editDialog.getByRole('button', { name: /保存修改|创建/ }).click();
    await page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'PUT', { timeout: 5000 }).catch(() => null);
    await page.waitForTimeout(2000);

    const openBtn1b = page.getByRole('button', { name: /打开产品列表/ });
    await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
      openBtn1b.click(),
    ]);
    const listDialog2 = page.locator('[role="dialog"]');
    await expect(listDialog2).toBeVisible({ timeout: 5000 });

    const editedRow = listDialog2.locator('.font-medium', { hasText: editedName }).first();
    await expect(editedRow).toBeVisible({ timeout: 10000 });

    await editedRow.locator('..').locator('..').locator('button').last().click();
    const alertDialog = page.locator('[role="alertdialog"]');
    await expect(alertDialog).toBeVisible({ timeout: 5000 });
    await alertDialog.getByRole('button', { name: /确认删除/ }).click();
    await page.waitForTimeout(2000);

    const openBtn2 = page.getByRole('button', { name: /打开产品列表/ });
    if (await openBtn2.isVisible({ timeout: 5000 }).catch(() => false)) {
      await Promise.all([
        page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
        openBtn2.click(),
      ]);
      await expect(page.locator('[role="dialog"]').locator('.font-medium', { hasText: editedName })).toHaveCount(0, { timeout: 5000 });
    } else {
      const products = await apiGetProducts(adminToken);
      const found = products.some(p => p.name === editedName);
      expect(found).toBeFalsy();
    }
  });

  test('物流规则完整CRUD流程', async ({ page }) => {
    const uniqueName = `EL${Date.now() % 10000}`;
    const editedName = `${uniqueName}E`;

    await page.goto('/logistics');
    await page.waitForLoadState('networkidle');

    await page.getByRole('button', { name: /添加物流规则/ }).click();
    await page.waitForTimeout(500);
    const dialog = page.locator('[role="dialog"]');
    await expect(dialog).toBeVisible({ timeout: 3000 });

    await dialog.locator('input[placeholder="请输入名称"]').fill(uniqueName);

    await dialog.getByRole('button', { name: /创建/ }).click();
    await page.waitForResponse(
      r => r.url().includes('/api/logistics') && r.request().method() === 'POST',
      { timeout: 10000 }
    ).catch(() => null);
    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 8000 });
    await page.waitForTimeout(500);

    await expect(page.getByText(uniqueName)).toBeVisible({ timeout: 5000 });

    const ruleCard = page.locator('.font-medium', { hasText: uniqueName }).first();
    const cardContainer = ruleCard.locator('xpath=ancestor::div[contains(@class,"p-4")]');
    await cardContainer.getByLabel('操作菜单').click();
    await page.getByLabel('编辑').click();
    await page.waitForTimeout(500);
    await expect(page.locator('[role="dialog"]')).toBeVisible({ timeout: 3000 });
    await page.locator('[role="dialog"]').locator('input[placeholder="请输入名称"]').fill(editedName);
    await page.locator('[role="dialog"]').getByRole('button', { name: /更新/ }).click();
    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 5000 });
    await expect(page.getByText(editedName)).toBeVisible({ timeout: 10000 });

    const editedCard = page.locator('.font-medium', { hasText: editedName }).first();
    const editedCardContainer = editedCard.locator('xpath=ancestor::div[contains(@class,"p-4")]');
    await editedCardContainer.getByLabel('操作菜单').click();
    await page.getByLabel('删除').click();
    const alertDialog = page.locator('[role="alertdialog"]');
    await expect(alertDialog).toBeVisible({ timeout: 5000 });
    await alertDialog.getByRole('button', { name: /确认删除/ }).click();
    await page.waitForTimeout(1000);
    await expect(page.getByText(editedName, { exact: true })).not.toBeVisible();
  });

  test('精准模式定价计算', async ({ page }) => {
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await page.getByRole('tab', { name: /精准模式/ }).click();
    await page.waitForTimeout(500);

    // 选择产品（combobox）
    const cb = page.locator('[role="combobox"]').first();
    await cb.click();
    await page.waitForTimeout(500);

    const optCount = await page.locator('[role="option"]').count();
    if (optCount === 0) {
      await page.keyboard.press('Escape');
      const nameInput = page.getByPlaceholder('必填');
      await nameInput.click();
      await nameInput.type('PriceTest', { delay: 20 });
      await page.locator('input[type="number"]').first().fill('50');
      await page.getByRole('button', { name: /保存产品/ }).click();
      await page.waitForResponse(r => r.url().includes('/api/products'), { timeout: 5000 }).catch(() => null);
      await page.waitForTimeout(1000);
      await cb.click();
      await page.waitForTimeout(500);
    }

    const firstOpt = page.locator('[role="option"]').first();
    if (await firstOpt.isVisible({ timeout: 2000 }).catch(() => false)) {
      await firstOpt.click();
    }
    await page.waitForTimeout(500);

    // 填写参数
    await page.locator('input[type="number"]').nth(1).fill('500');
    await page.locator('input[type="number"]').nth(2).fill('20');
    await page.locator('input[type="number"]').nth(3).fill('15');
    await page.locator('input[type="number"]').nth(4).fill('10');

    // 计算
    const calcBtn = page.getByRole('button', { name: /计算/ });
    await expect(calcBtn).toBeVisible({ timeout: 3000 });
    if (await calcBtn.isEnabled()) {
      await calcBtn.click();
      await page.waitForTimeout(2000);
      const result = page.locator('text=/结果|可用物流|定价|报价|物流方案/').first();
      await expect.soft(result).toBeVisible({ timeout: 5000 });
    }
  });
});
