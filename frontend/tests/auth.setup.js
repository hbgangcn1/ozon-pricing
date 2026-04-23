import { test as setup, expect } from '@playwright/test';
import path from 'path';
import fs from 'node:fs/promises';
import { fileURLToPath } from 'url';
import {
  TEST_ADMIN,
  TEST_ADMIN_SECURITY_QUESTION,
  TEST_USER,
  URLS,
  API_BASE,
} from './fixtures/test-data.js';
import { LOGIN_PAGE } from './fixtures/selectors.js';
import {
  apiLogin,
  apiCreateUser,
  apiGetUsers,
  apiSetMySecurityQuestion,
  apiToggleRegistration,
} from './helpers/api-helpers.js';
import { ADMIN_AUTH_FILE, ADMIN_MARKER_FILE } from './helpers/auth-paths.js';
import { rewriteMarker } from './helpers/admin-token.js';
import {
  upsertAdminSecurityQuestion,
  verifyAdminSecurityQuestion,
} from './helpers/db-direct.js';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const USER_AUTH_FILE = path.join(__dirname, '.auth', 'user.json');

setup('authenticate as admin', async ({ page, request }) => {
  // R-W14-C0-line25-redir fix (Oracle Route D):
  // ProtectedRoute 判定依据是 `useAuthStore.initAuth()`，它只读
  //   localStorage.api_user + localStorage.api_token
  // 完全不读 `auth-storage`（那是死数据，旧 Zustand persist 的残留）。
  // 因此 setup 必须写入 api_user，否则下次 spec 加载 storageState 后
  // initAuth() 因 api_user 缺失而 isAuthenticated=false → ProtectedRoute redirect /login。
  // 同时不再写 auth-storage（不再制造一致性维护负担）。
  //
  // 步骤：
  // 1) APIRequestContext POST /auth/login → adminToken + Set-Cookie
  // 2) GET /auth/me 拿真实 user object（含 id/role/subscription_type/has_security_question 等）
  // 3) 把 cookies 注入 browser context；goto /login（建立 origin）后写 api_user + api_token
  // 4) goto /pricing 验证 ProtectedRoute 放行
  // 5) 设置安全问题、写盘 storageState、写 marker
  const loginResp = await request.post(`${API_BASE}/auth/login`, {
    data: { username: TEST_ADMIN.username, password: TEST_ADMIN.password },
  });
  if (!loginResp.ok()) {
    throw new Error(`admin login failed ${loginResp.status()}: ${await loginResp.text()}`);
  }
  const loginBody = await loginResp.json();
  const adminToken = loginBody.access_token || loginBody.token;
  if (!adminToken) {
    throw new Error('admin login response missing access_token');
  }

  // 拿真实 user object（authStore.buildPersistedUser 字段：
  //   id, username, role, subscription_type, user_type,
  //   remaining_calculations, has_security_question）
  const meResp = await request.get(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  if (!meResp.ok()) {
    throw new Error(`/auth/me failed ${meResp.status()}: ${await meResp.text()}`);
  }
  const adminUser = await meResp.json();

  // 提取 cookies 注入 browser context
  const apiState = await request.storageState();
  await page.context().addCookies(apiState.cookies);

  // 必须先注入 localStorage 再访问 protected route，否则 initAuth() 无 api_user
  // → isAuthenticated=false → ProtectedRoute redirect /login。
  await page.goto(URLS.login);
  await page.evaluate(([token, user]) => {
    localStorage.setItem('api_token', token);
    localStorage.setItem('api_user', JSON.stringify(user));
  }, [adminToken, adminUser]);
  await page.goto(URLS.pricing);
  await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 20000 });

  // 设置安全问题（同一 token，gate 后无 kick）
  await apiSetMySecurityQuestion(request, adminToken);
  await upsertAdminSecurityQuestion(
    TEST_ADMIN_SECURITY_QUESTION.question,
    TEST_ADMIN_SECURITY_QUESTION.answer,
  );
  const verification = await verifyAdminSecurityQuestion();
  expect(verification.has_security_question).toBe(true);
  expect(verification.security_q1).toBe(TEST_ADMIN_SECURITY_QUESTION.question);

  // 写盘 storageState（cookies + localStorage 一致快照）+ marker
  // 注意：不再调 rewriteAdminStorageState（已废弃，会制造 sid 漂移）
  await page.context().storageState({ path: ADMIN_AUTH_FILE });
  await rewriteMarker(adminToken, ADMIN_MARKER_FILE);

  const writtenStorage = JSON.parse(await fs.readFile(ADMIN_AUTH_FILE, 'utf8'));
  const writtenApiToken = writtenStorage.origins
    .flatMap((o) => o.localStorage || [])
    .find((i) => i.name === 'api_token');
  expect(writtenApiToken?.value, 'admin.json must contain api_token matching login token').toBe(adminToken);
  const writtenMarker = JSON.parse(await fs.readFile(ADMIN_MARKER_FILE, 'utf8'));
  expect(writtenMarker.token, 'marker.token must equal login token at setup time').toBe(adminToken);
});

setup('authenticate as regular user', async ({ page }) => {
  const adminToken = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password);

  const existingUsers = await apiGetUsers(adminToken, TEST_USER.username);
  const usersArray = Array.isArray(existingUsers) ? existingUsers : (existingUsers.users || []);
  const existingUser = usersArray.find(u => u.username === TEST_USER.username);

  if (!existingUser) {
    await apiToggleRegistration(adminToken, true).catch(() => null);

    await apiCreateUser(adminToken, {
      username: TEST_USER.username,
      password: TEST_USER.password,
      confirm_password: TEST_USER.password,
      security_question: '您母亲的姓名？',
      security_answer: 'e2e_answer',
      role: 'user',
    }).catch(async (err) => {
      if (!err.message.includes('409') && !err.message.includes('already')) {
        throw err;
      }
    });
  }

  await page.goto(URLS.login);
  await page.waitForSelector(LOGIN_PAGE.usernameInput, { state: 'visible' });
  await page.fill(LOGIN_PAGE.usernameInput, TEST_USER.username);
  await page.fill(LOGIN_PAGE.passwordInput, TEST_USER.password);
  await page.click(LOGIN_PAGE.submitButton);
  await page.waitForURL(/\/(pricing|dashboard)/, { timeout: 20000 });
  await expect(page).toHaveURL(/\/(pricing|dashboard)/);
  await page.context().storageState({ path: USER_AUTH_FILE });
});
