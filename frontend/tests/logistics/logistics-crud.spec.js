import { test, expect } from '@playwright/test'

test.describe('物流规则 CRUD 流程', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(90000)

  let ruleName
  let editedName

  test.beforeAll(async () => {
    const suffix = Date.now() % 100000
    ruleName = `TestRule${suffix}`
    editedName = `TestRule${suffix}E`
  })

  async function goLogistics(page) {
    await page.goto('/logistics')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(300)
  }

  async function openAddDialog(page) {
    await page.getByRole('button', { name: /添加物流规则/ }).click()
    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })
    return dialog
  }

  test('创建物流规则', async ({ page }) => {
    await goLogistics(page)

    const dialog = await openAddDialog(page)

    const nameInput = dialog.locator('input[placeholder="请输入名称"]')
    await expect(nameInput).toBeVisible({ timeout: 5000 })
    await nameInput.fill(ruleName)

    await dialog.getByRole('button', { name: /创建/ }).click()

    const response = await page.waitForResponse(
      r => r.url().includes('/api/logistics') && r.request().method() === 'POST',
      { timeout: 10000 }
    ).catch(() => null)

    if (response) {
      expect([200, 201]).toContain(response.status())
    }

    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 8000 })
    await page.waitForTimeout(500)
  })

  test('物流规则列表中可见新创建的规则', async ({ page }) => {
    await goLogistics(page)

    await expect(page.getByText(ruleName)).toBeVisible({ timeout: 8000 })
  })

  test('编辑物流规则名称', async ({ page }) => {
    await goLogistics(page)

    const ruleCard = page.locator('.font-medium', { hasText: ruleName }).first()
    await expect(ruleCard).toBeVisible({ timeout: 8000 })

    await ruleCard.locator('..').getByLabel('编辑').click()

    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    const nameInput = dialog.locator('input[placeholder="请输入名称"]')
    await expect(nameInput).toBeVisible({ timeout: 5000 })
    await nameInput.fill(editedName)

    await dialog.getByRole('button', { name: /更新/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/logistics') && r.request().method() === 'PUT',
      { timeout: 10000 }
    ).catch(() => null)

    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 8000 })
    await page.waitForTimeout(500)
  })

  test('物流规则列表可见编辑后的名称', async ({ page }) => {
    await goLogistics(page)

    await expect(page.getByText(editedName)).toBeVisible({ timeout: 8000 })
    await expect(page.getByText(ruleName, { exact: true })).not.toBeVisible()
  })

  test('删除物流规则', async ({ page }) => {
    await goLogistics(page)

    const ruleCard = page.locator('.font-medium', { hasText: editedName }).first()
    await expect(ruleCard).toBeVisible({ timeout: 8000 })

    await ruleCard.locator('..').getByLabel('删除').click()

    const alertDialog = page.locator('[role="alertdialog"]')
    await expect(alertDialog).toBeVisible({ timeout: 5000 })
    await alertDialog.getByRole('button', { name: /确认删除/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/logistics') && r.request().method() === 'DELETE',
      { timeout: 10000 }
    ).catch(() => null)

    await page.waitForTimeout(500)
  })

  test('删除后规则不可见', async ({ page }) => {
    await goLogistics(page)

    await expect(page.getByText(editedName, { exact: true })).not.toBeVisible()
  })
})

test.describe('物流规则 CRUD — 备选方案', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(90000)

  let ruleName2
  let editedName2

  test.beforeAll(async () => {
    const suffix = (Date.now() + 1) % 100000
    ruleName2 = `AltRule${suffix}`
    editedName2 = `AltRule${suffix}E`
  })

  test('通过按钮索引完成完整 CRUD', async ({ page }) => {
    await page.goto('/logistics')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(300)

    await page.getByRole('button', { name: /添加物流规则/ }).click()
    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    await dialog.locator('input[placeholder="请输入名称"]').fill(ruleName2)
    await dialog.getByRole('button', { name: /创建/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/logistics') && r.request().method() === 'POST',
      { timeout: 10000 }
    ).catch(() => null)

    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 8000 })
    await page.waitForTimeout(500)

    await expect(page.getByText(ruleName2)).toBeVisible({ timeout: 8000 })

    const allEditBtns = page.getByRole('button', { name: /编辑/ })
    const editBtnCount = await allEditBtns.count()
    expect(editBtnCount).toBeGreaterThan(0)

    await allEditBtns.first().click()
    const editDialog = page.locator('[role="dialog"]')
    await expect(editDialog).toBeVisible({ timeout: 5000 })

    await editDialog.locator('input[placeholder="请输入名称"]').fill(editedName2)
    await editDialog.getByRole('button', { name: /更新/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/logistics') && r.request().method() === 'PUT',
      { timeout: 10000 }
    ).catch(() => null)

    await expect(page.locator('[role="dialog"]')).not.toBeVisible({ timeout: 8000 })
    await page.waitForTimeout(500)

    await expect(page.getByText(editedName2)).toBeVisible({ timeout: 8000 })

    const allDeleteBtns = page.getByRole('button', { name: /删除/ })
    await allDeleteBtns.first().click()

    const alertDialog = page.locator('[role="alertdialog"]')
    await expect(alertDialog).toBeVisible({ timeout: 5000 })
    await alertDialog.getByRole('button', { name: /确认删除/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/logistics') && r.request().method() === 'DELETE',
      { timeout: 10000 }
    ).catch(() => null)

    await page.waitForTimeout(500)
    await expect(page.getByText(editedName2, { exact: true })).not.toBeVisible()
  })
})
