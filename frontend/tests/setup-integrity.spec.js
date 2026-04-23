/* eslint-env node */
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { invalidateAdminToken, getAdminToken, REFRESH_THRESHOLD_SEC } from './helpers/admin-token.js';
import { ADMIN_AUTH_FILE, ADMIN_MARKER_FILE } from './helpers/auth-paths.js';

function readAdminStorageState() {
  const authPath = path.resolve('tests/.auth/admin.json');
  if (!fs.existsSync(authPath)) {
    throw new Error('tests/.auth/admin.json missing. Run --project=setup first.');
  }
  return JSON.parse(fs.readFileSync(authPath, 'utf8'));
}

function getLocalStorageEntry(storageState, name) {
  return storageState.origins
    .flatMap((o) => o.localStorage || [])
    .find((i) => i.name === name);
}

test('admin storageState exists and contains api_token in localStorage', () => {
  const storageState = readAdminStorageState();
  const apiTokenEntry = getLocalStorageEntry(storageState, 'api_token');
  expect(apiTokenEntry, 'api_token entry missing in admin.json localStorage').toBeDefined();
  expect(typeof apiTokenEntry.value).toBe('string');
  expect(apiTokenEntry.value.length).toBeGreaterThan(20);
});

// R-W14-C0-line25-redir (Oracle Route D):
// authStore.initAuth() 只读 localStorage.api_user + localStorage.api_token，
// 完全不读 auth-storage。如果 admin.json 缺 api_user，
// 下次 spec 加载 storageState 后 ProtectedRoute 会 redirect /login。
test('admin storageState contains api_user in localStorage with required fields', () => {
  const storageState = readAdminStorageState();
  const apiUserEntry = getLocalStorageEntry(storageState, 'api_user');
  expect(apiUserEntry, 'api_user entry missing in admin.json localStorage (Route D requires it)').toBeDefined();
  expect(typeof apiUserEntry.value).toBe('string');
  const user = JSON.parse(apiUserEntry.value);
  // authStore.buildPersistedUser 关键字段
  expect(user.username).toBeDefined();
  expect(user.role).toBeDefined();
  expect(typeof user.has_security_question).toBe('boolean');
});

test('marker file exists with valid shape (token / exp / issuedAt)', () => {
  const markerPath = path.resolve('tests/.auth/admin-token-marker.json');
  if (!fs.existsSync(markerPath)) {
    throw new Error('tests/.auth/admin-token-marker.json missing. Run --project=setup first.');
  }
  const marker = JSON.parse(fs.readFileSync(markerPath, 'utf8'));
  expect(typeof marker.token).toBe('string');
  expect(marker.token.length).toBeGreaterThan(20);
  expect(typeof marker.exp).toBe('number');
  expect(typeof marker.issuedAt).toBe('number');
});

test('getAdminToken(request, opts) returns a JWT with exp > now + REFRESH_THRESHOLD_SEC', async ({ request }) => {
  invalidateAdminToken();
  const token = await getAdminToken(request, { authFile: ADMIN_AUTH_FILE, markerFile: ADMIN_MARKER_FILE });
  expect(typeof token).toBe('string');
  expect(token.length).toBeGreaterThan(20);
  const [, payloadB64] = token.split('.');
  const payload = JSON.parse(Buffer.from(payloadB64, 'base64').toString('utf8'));
  const nowSec = Math.floor(Date.now() / 1000);
  expect(payload.exp - nowSec).toBeGreaterThan(REFRESH_THRESHOLD_SEC);
});

// R-W14-C0-line25-redir (Oracle Route D):
// getAdminToken 不再写盘 admin.json，避免 sid 漂移（不同 token = 不同 session）。
// admin.json 的 api_token 必须永远等于 setup 时刻写入的值。
test('getAdminToken does NOT mutate admin.json (no sid drift)', async ({ request }) => {
  const beforeRaw = fs.readFileSync(path.resolve('tests/.auth/admin.json'), 'utf8');
  invalidateAdminToken();
  await getAdminToken(request, { authFile: ADMIN_AUTH_FILE, markerFile: ADMIN_MARKER_FILE });
  const afterRaw = fs.readFileSync(path.resolve('tests/.auth/admin.json'), 'utf8');
  expect(afterRaw, 'admin.json must NOT be rewritten by getAdminToken (would cause sid drift)').toBe(beforeRaw);
});
