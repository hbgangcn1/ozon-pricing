import { test, expect } from '@playwright/test'

test.describe('Exchange API - 汇率接口', () => {
  test('GET /api/exchange/rates - 返回 200', async ({ request }) => {
    const resp = await request.get('/api/exchange/rates')
    expect(resp.status()).toBe(200)
  })

  test('GET /api/exchange/rates - 返回四种汇率字段', async ({ request }) => {
    const resp = await request.get('/api/exchange/rates')
    const data = await resp.json()
    expect(data).toHaveProperty('RUB/CNY')
    expect(data).toHaveProperty('CNY/RUB')
    expect(data).toHaveProperty('USD/CNY')
    expect(data).toHaveProperty('CNY/USD')
  })

  test('GET /api/exchange/rates - 汇率值为正数', async ({ request }) => {
    const resp = await request.get('/api/exchange/rates')
    const data = await resp.json()
    expect(typeof data['RUB/CNY']).toBe('number')
    expect(typeof data['CNY/RUB']).toBe('number')
    expect(typeof data['USD/CNY']).toBe('number')
    expect(typeof data['CNY/USD']).toBe('number')
    expect(data['RUB/CNY']).toBeGreaterThan(0)
    expect(data['CNY/RUB']).toBeGreaterThan(0)
    expect(data['USD/CNY']).toBeGreaterThan(0)
    expect(data['CNY/USD']).toBeGreaterThan(0)
  })

  test('GET /api/exchange/rates - 互逆汇率乘积接近 1', async ({ request }) => {
    const resp = await request.get('/api/exchange/rates')
    const data = await resp.json()
    const rubCnyProduct = data['RUB/CNY'] * data['CNY/RUB']
    const usdCnyProduct = data['USD/CNY'] * data['CNY/USD']
    expect(rubCnyProduct).toBeGreaterThan(0.9)
    expect(rubCnyProduct).toBeLessThan(1.1)
    expect(usdCnyProduct).toBeGreaterThan(0.9)
    expect(usdCnyProduct).toBeLessThan(1.1)
  })

  test('GET /api/exchange/rates - 接口无需认证即可访问', async ({ request }) => {
    const resp = await request.get('/api/exchange/rates')
    expect(resp.ok()).toBeTruthy()
    expect(resp.status()).not.toBe(401)
    expect(resp.status()).not.toBe(403)
  })
})
