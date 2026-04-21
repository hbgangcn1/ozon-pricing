/* eslint-env node */
import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './tests',
  globalTeardown: './tests/global-teardown.js',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 1,
  workers: process.env.CI ? 1 : undefined,
  reporter: 'html',
  use: {
    baseURL: 'http://localhost:3001',
    trace: 'on-first-retry',
    headless: true,
    actionTimeout: 30000,
    navigationTimeout: 30000,
  },
  timeout: 60000,
  expect: {
    timeout: 10000,
  },
  projects: [
    // Auth setup project — runs first, no dependencies
    {
      name: 'setup',
      testMatch: /auth\.setup\.js/,
      use: { ...devices['Desktop Chrome'] },
    },

    // Main test project — depends on setup, uses saved auth state
    {
      name: 'chromium',
      use: {
        ...devices['Desktop Chrome'],
        // Default to admin storageState; individual tests can override
        storageState: 'tests/.auth/admin.json',
      },
      dependencies: ['setup'],
      testIgnore: [
        '**/auth/login.spec.js',
        '**/auth/register.spec.js',
        '**/auth.setup.js',
      ],
    },

    // No-auth project — for login/register tests (no storageState)
    {
      name: 'chromium-no-auth',
      use: { ...devices['Desktop Chrome'] },
      testMatch: [
        '**/auth/login.spec.js',
        '**/auth/register.spec.js',
      ],
    },
  ],
  webServer: [
    {
      command: 'npm run dev',
      url: 'http://localhost:3001',
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
    },
    {
      // Windows: use env object instead of inline E2E_TEST=1 prefix
      command: 'python -m uvicorn api.main:app --host 0.0.0.0 --port 8003',
      url: 'http://localhost:8003/health',
      reuseExistingServer: !process.env.CI,
      timeout: 120000,
      cwd: '../',
      env: { ...process.env, E2E_TEST: '1' },
    },
  ],
});
