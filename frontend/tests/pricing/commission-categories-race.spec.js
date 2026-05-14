// E2E race-condition regression for fix-commission-categories-race
//
// 历史 bug:精准模式佣金类目下拉只显示"不使用类目(0%)",新登录用户立刻进
// /pricing 时尤为明显。根因:usePricingCalculation 主 useEffect 在 user
// 还未 commit 时就跑(deps=[]),Promise.resolve([]) 永久占位,后续 user
// hydrate 不会重跑 fetch,commissionCategories 锁死为 [].
//
// 此 spec 必须在 NO storageState(chromium-no-auth project)下跑 —— 任何
// 预先持久化的 user 都会让 hydrate 在 effect 之前完成,从而掩盖 race。
// 流程:登录 → 立即跳 /pricing → 切精准模式 → 打开佣金类目下拉 → 断言
// 至少存在一个非"不使用类目(0%)"的 SelectItem。
//
// 任务:openspec/changes/fix-commission-categories-race/tasks.md §3.1-3.5

import { test, expect } from '@playwright/test';
import { TEST_ADMIN, URLS } from '../fixtures/test-data.js';
import { LOGIN_PAGE } from '../fixtures/selectors.js';

async function loginAsAdmin(page) {
  await page.goto(URLS.login);
  await page.waitForSelector(LOGIN_PAGE.usernameInput, { state: 'visible' });
  await page.fill(LOGIN_PAGE.usernameInput, TEST_ADMIN.username);
  await page.fill(LOGIN_PAGE.passwordInput, TEST_ADMIN.password);
  await page.click(LOGIN_PAGE.submitButton);
  // setAuth + navigate 同 tick —— 必须等到 URL 真正落地
  await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 15000 });
}

async function dismissSessionKickIfPresent(page) {
  const kick = page.getByRole('alertdialog', { name: /账号在其他设备登录/ });
  if (await kick.isVisible({ timeout: 500 }).catch(() => false)) {
    const ok = kick.getByRole('button').filter({ hasText: /确定|知道了|OK/ }).first();
    if (await ok.isVisible({ timeout: 500 }).catch(() => false)) {
      await ok.click();
    } else {
      await page.keyboard.press('Escape');
    }
    await expect(kick).toBeHidden({ timeout: 5000 });
  }
}

async function switchToPreciseModeAndOpenCommissionDropdown(page) {
  if (!page.url().includes('/pricing')) {
    await page.goto(URLS.pricing);
  }

  await dismissSessionKickIfPresent(page);

  const preciseTab = page.getByRole('tab').filter({ hasText: /精准/ }).first();
  await expect(preciseTab).toBeVisible({ timeout: 10000 });
  await preciseTab.click();

  await expect(page.locator('label').filter({ hasText: /^佣金类目$/ }).first()).toBeVisible({
    timeout: 10000,
  });

  // 等待 commission-categories API 真正完成(race fix 验证关键)
  // 若超时 → race 仍存在,fetch 没被触发
  try {
    await page.waitForResponse(
      (r) => r.url().includes('/commission-categories') && r.status() === 200,
      { timeout: 8000 },
    );
  } catch (e) {
    // 若已经在 dropdown 打开前发出 → 不会再触发,继续走断言
    // 但仍记录,便于诊断
    console.warn('[diag] waitForResponse(/commission-categories) timed out:', e.message);
  }

  // 打开佣金类目下拉(SelectTrigger placeholder="选择佣金类目")
  const trigger = page
    .locator('button[role="combobox"]')
    .filter({ hasText: /选择佣金类目|不使用类目/ })
    .first();
  await expect(trigger).toBeVisible({ timeout: 10000 });
  await trigger.click();
}

async function assertCommissionDropdownHasRealCategories(page) {
  const listbox = page.locator('[role="listbox"]').first();
  await expect(listbox).toBeVisible({ timeout: 5000 });

  const options = listbox.locator('[role="option"]');
  await expect(options).not.toHaveCount(0);

  const totalCount = await options.count();
  expect(totalCount).toBeGreaterThanOrEqual(2);

  const allTexts = [];
  for (let i = 0; i < totalCount; i += 1) {
    allTexts.push((await options.nth(i).textContent())?.trim() ?? '');
  }

  const realCategoryNames = allTexts.filter((t) => t && !t.includes('不使用类目'));
  expect(
    realCategoryNames.length,
    `expected at least 1 real commission category but got only ${JSON.stringify(realCategoryNames)}`,
  ).toBeGreaterThanOrEqual(1);
}

test.describe.configure({ mode: 'serial' });

test.describe('精准模式佣金类目 race-condition 回归', () => {
  test('新登录立即进定价页 → 精准模式下拉含真实类目', async ({ page }) => {
    await loginAsAdmin(page);
    await switchToPreciseModeAndOpenCommissionDropdown(page);
    await assertCommissionDropdownHasRealCategories(page);
  });

  test('登录后 reload → 精准模式下拉仍含真实类目', async ({ page }) => {
    await loginAsAdmin(page);
    await page.reload();
    await switchToPreciseModeAndOpenCommissionDropdown(page);
    await assertCommissionDropdownHasRealCategories(page);
  });
});
