import { test, expect } from '@playwright/test'
import { TEST_ADMIN } from '../fixtures/test-data.js'
import { apiLogin, apiCreateProduct, apiDeleteProduct, apiGetProducts } from '../helpers/api-helpers.js'

test.describe('产品 CRUD 流程', () => {
  test.describe.configure({ mode: 'serial' })
  test.setTimeout(90000)

  let productName
  let editedName
  let adminToken
  test.beforeAll(async () => {
    const suffix = Date.now() % 100000
    productName = `TestProduct${suffix}`
    editedName = `TestProduct${suffix}E`
    adminToken = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password)
  })

  test.afterAll(async () => {
    if (!adminToken) return
    const products = await apiGetProducts(adminToken).catch(() => [])
    const arr = Array.isArray(products) ? products : []
    for (const p of arr) {
      if (p.name === productName || p.name === editedName) {
        await apiDeleteProduct(adminToken, p.id).catch(() => null)
      }
    }
  })

  async function goPrecise(page) {
    await page.goto('/pricing')
    await page.waitForLoadState('networkidle')
    await page.getByRole('tab', { name: /精准模式/ }).click()
    await page.waitForTimeout(600)
  }

  test('创建产品', async ({ _page }) => {
    const product = await apiCreateProduct(adminToken, {
      name: productName,
      unit_price: 49.9,
      weight_g: 350,
      length_cm: 20,
      width_cm: 15,
      height_cm: 10,
    })
    expect(product).toBeTruthy()
  })

  test('产品列表中可见新创建的产品', async ({ page }) => {
    await goPrecise(page)

    const listBtn = page.getByRole('button', { name: /打开产品列表/ })
    await expect(listBtn).toBeVisible({ timeout: 5000 })

    await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
      listBtn.click(),
    ])

    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })
    await expect(dialog.getByText(productName)).toBeVisible({ timeout: 10000 })
  })

  test('编辑产品名称', async ({ page }) => {
    await goPrecise(page)

    const listBtn = page.getByRole('button', { name: /打开产品列表/ })
    await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
      listBtn.click(),
    ])
    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    const productRow = dialog.locator('.font-medium', { hasText: productName }).locator('..').locator('..')
    await expect(productRow).toBeVisible({ timeout: 10000 })

    await productRow.locator('button').first().click()
    await page.waitForTimeout(500)

    const editDialog = page.locator('[role="dialog"]')
    await expect(editDialog).toBeVisible({ timeout: 5000 })

    const nameInput = editDialog.locator('input').first()
    await nameInput.click()
    await nameInput.fill(editedName)

    await editDialog.getByRole('button', { name: /保存修改|创建/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/products') && r.request().method() === 'PUT',
      { timeout: 10000 }
    ).catch(() => null)

    await page.waitForTimeout(800)
  })

  test('产品列表可见编辑后的名称', async ({ page }) => {
    await goPrecise(page)

    const listBtn = page.getByRole('button', { name: /打开产品列表/ })
    await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
      listBtn.click(),
    ])
    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    await expect(dialog.getByText(editedName)).toBeVisible({ timeout: 10000 })
    await expect(dialog.getByText(productName, { exact: true })).not.toBeVisible()
  })

  test('删除产品', async ({ page }) => {
    await goPrecise(page)

    const listBtn = page.getByRole('button', { name: /打开产品列表/ })
    await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
      listBtn.click(),
    ])
    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    const productRow = dialog.locator('.font-medium', { hasText: editedName }).locator('..').locator('..')
    await expect(productRow).toBeVisible({ timeout: 10000 })

    await productRow.locator('button').last().click()

    const alertDialog = page.locator('[role="alertdialog"]')
    await expect(alertDialog).toBeVisible({ timeout: 5000 })
    await alertDialog.getByRole('button', { name: /确认删除/ }).click()

    await page.waitForResponse(
      r => r.url().includes('/api/products') && r.request().method() === 'DELETE',
      { timeout: 10000 }
    ).catch(() => null)

    await page.waitForTimeout(800)
  })

  test('删除后产品列表中不可见', async ({ page }) => {
    await goPrecise(page)

    const listBtn = page.getByRole('button', { name: /打开产品列表/ })
    await Promise.all([
      page.waitForResponse(r => r.url().includes('/api/products') && r.request().method() === 'GET'),
      listBtn.click(),
    ])
    const dialog = page.locator('[role="dialog"]')
    await expect(dialog).toBeVisible({ timeout: 5000 })

    await expect(dialog.getByText(editedName, { exact: true })).not.toBeVisible()
  })
})

test.describe('产品表单验证', () => {
  test.setTimeout(30000)

  test('精准模式页面包含产品管理UI', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')

    const preciseTab = page.getByRole('tab', { name: /精准模式/ })
    await expect(preciseTab).toBeVisible({ timeout: 5000 })
    await preciseTab.click()
    await page.waitForTimeout(500)

    await expect(page.getByRole('button', { name: /保存产品/ })).toBeVisible({ timeout: 5000 })
    await expect(page.getByRole('button', { name: /打开产品列表/ })).toBeVisible({ timeout: 5000 })
    await expect(page.locator('input[placeholder="必填"]')).toBeVisible({ timeout: 5000 })
  })

  test('选择产品下拉框存在', async ({ page }) => {
    await page.goto('/pricing')
    await page.waitForLoadState('domcontentloaded')

    await page.getByRole('tab', { name: /精准模式/ }).click()
    await page.waitForTimeout(500)

    const combobox = page.locator('[role="combobox"]').first()
    await expect(combobox).toBeVisible({ timeout: 5000 })
  })
})
