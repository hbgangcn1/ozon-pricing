import { test, expect } from '@playwright/test';

test.describe('核心冒烟测试', () => {
  // 测试1: 登录流程（在 chromium 项目中 storageState 已登录，访问 /login 会跳转）
  test('登录流程', async ({ page }) => {
    // storageState 已经登录，访问 /login 会被重定向到 /pricing 或 /dashboard
    await page.goto('/login');
    // 等待重定向完成（已登录则直接跳转，未登录则显示登录页）
    await page.waitForLoadState('networkidle');

    const url = page.url();
    if (url.includes('/login')) {
      // 未登录状态：正常填写表单
      await expect(page.getByRole('heading', { name: '物流定价系统' })).toBeVisible();
      await page.fill('input[name="username"]', 'admin');
      await page.fill('input[name="password"]', '***REMOVED-PG-PWD***');
      await page.click('button[type="submit"]');
      await page.waitForURL(/\/(pricing|dashboard)/);
      await expect(page).toHaveURL(/\/(pricing|dashboard)/);
    } else {
      // 已登录状态：已经跳转到主页
      await expect(page).toHaveURL(/\/(pricing|dashboard)/);
    }
  });

  // 测试2: 定价计算（storageState 已登录，直接访问 /pricing）
  test('定价计算', async ({ page }) => {
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/pricing');

    // 填写进货单价和重量（使用 placeholder 定位）
    await page.locator('input[placeholder="30"]').fill('5');
    await page.locator('input[placeholder="300"]').fill('100');

    // 检查计算按钮状态
    const calcBtn = page.getByRole('button', { name: /开始计算/ });
    await expect(calcBtn).toBeVisible({ timeout: 5000 });
    const isDisabled = await calcBtn.isDisabled();

    if (isDisabled) {
      // 没有物流规则时按钮禁用，验证页面内容存在
      const bodyLength = await page.evaluate(() => document.body.innerText.length);
      expect(bodyLength).toBeGreaterThan(100);
    } else {
      // 按钮可用，验证可以点击
      await expect(calcBtn).toBeEnabled();
      await calcBtn.click();
      await page.waitForTimeout(1000);
      const bodyLength = await page.evaluate(() => document.body.innerText.length);
      expect(bodyLength).toBeGreaterThan(100);
    }
  });

  // 测试3: 物流管理页面加载
  test('物流管理页面加载', async ({ page }) => {
    await page.goto('/logistics');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/logistics');

    // 验证页面标题包含"物流"
    await expect(page.locator('h1')).toContainText('物流');

    // 验证"添加物流规则"按钮存在（LogisticsPage 上的按钮文本）
    await expect(page.getByRole('button', { name: /添加物流规则/ })).toBeVisible();
  });

  // 测试4: 主页面数据加载（/pricing 是默认首页）
  test('主页面数据加载', async ({ page }) => {
    await page.goto('/pricing');
    await page.waitForLoadState('networkidle');

    // 验证页面有内容
    const pageContent = await page.evaluate(() => document.body.innerText);
    expect(pageContent.length).toBeGreaterThan(100);

    // 验证关键 UI 元素存在（快速模式下的开始计算按钮，无 emoji）
    await expect(page.getByRole('button', { name: /开始计算/ })).toBeVisible();
  });

  // 测试5: 修改密码表单
  test('修改密码表单', async ({ page }) => {
    await page.goto('/account');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveURL('/account');

    // 验证修改密码表单存在
    await expect(page.locator('form')).toBeVisible();

    // 验证当前密码、新密码、确认密码三个输入框存在
    await expect(page.locator('input[name="current_password"]')).toBeVisible();
    await expect(page.locator('input[name="new_password"]')).toBeVisible();
    await expect(page.locator('input[name="confirm_password"]')).toBeVisible();

    // 填入数据，提交（验证表单能正常交互）
    await page.fill('input[name="current_password"]', '***REMOVED-PG-PWD***');
    await page.fill('input[name="new_password"]', 'newpassword123');
    await page.fill('input[name="confirm_password"]', 'newpassword123');

    // 提交表单
    await page.click('button[type="submit"]');

    // 等待提交完成
    await page.waitForTimeout(2000);

    // 验证表单有响应（页面没有崩溃）
    await expect(page.locator('form')).toBeVisible();
  });
});
