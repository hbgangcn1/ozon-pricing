import { apiLogin } from './api-helpers.js';
import { TEST_ADMIN } from '../fixtures/test-data.js';
import fs from 'node:fs/promises';
import path from 'node:path';
import { jwtDecode } from 'jwt-decode';

export const REFRESH_THRESHOLD_SEC = 4 * 60;

let cachedToken = null;
let cachedExpSec = null;
let cachedPaths = null;

function decodeExp(token) {
  try { return jwtDecode(token).exp ?? null; } catch { return null; }
}

function nowSec() { return Math.floor(Date.now() / 1000); }

function shouldRefresh() {
  if (!cachedToken || !cachedExpSec) return true;
  return (cachedExpSec - nowSec()) <= REFRESH_THRESHOLD_SEC;
}

export async function getAdminToken(request, opts) {
  if (!opts || !opts.authFile || !opts.markerFile) {
    throw new Error('getAdminToken requires { authFile, markerFile } - pass ADMIN_AUTH_FILE / ADMIN_MARKER_FILE from helpers/auth-paths.js');
  }
  const { authFile, markerFile } = opts;

  if (cachedPaths && (cachedPaths.authFile !== authFile || cachedPaths.markerFile !== markerFile)) {
    throw new Error(`Path drift: helper was previously called with ${JSON.stringify(cachedPaths)} but now ${JSON.stringify({ authFile, markerFile })}. All call sites must use the same constants.`);
  }
  cachedPaths = { authFile, markerFile };

  if (!shouldRefresh()) return cachedToken;

  const token = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password);
  if (!token || typeof token !== 'string') {
    throw new Error(`getAdminToken: apiLogin returned invalid token: ${typeof token}`);
  }
  cachedToken = token;
  cachedExpSec = decodeExp(token);

  await rewriteAdminStorageState(token, authFile);
  await rewriteMarker(token, markerFile);

  return token;
}

export function invalidateAdminToken() {
  cachedToken = null;
  cachedExpSec = null;
}

export async function rewriteAdminStorageState(token, authFile) {
  const raw = await fs.readFile(authFile, 'utf8');
  const state = JSON.parse(raw);
  let updated = false;
  for (const origin of state.origins ?? []) {
    for (const item of origin.localStorage ?? []) {
      if (item.name === 'api_token') {
        item.value = token;
        updated = true;
      }
    }
  }
  if (!updated) {
    throw new Error(`rewriteAdminStorageState: no api_token entry found in ${authFile}`);
  }
  const tmp = `${authFile}.tmp`;
  await fs.writeFile(tmp, JSON.stringify(state, null, 2), 'utf8');
  await fs.rename(tmp, authFile);
}

export async function rewriteMarker(token, markerFile) {
  await fs.mkdir(path.dirname(markerFile), { recursive: true });
  const exp = decodeExp(token);
  const issuedAt = Math.floor(Date.now() / 1000);
  if (!exp || typeof exp !== 'number') {
    throw new Error(`rewriteMarker: decodeExp returned invalid exp: ${exp}`);
  }
  const tmp = `${markerFile}.tmp`;
  await fs.writeFile(tmp, JSON.stringify({ token, exp, issuedAt }, null, 2), 'utf8');
  await fs.rename(tmp, markerFile);
}

export async function refreshAdminUiAuth(page) {
  if (!cachedToken) return;
  let url;
  try { url = page.url(); } catch { return; }
  if (!url || url === 'about:blank' || !url.startsWith('http')) return;

  const current = await page.evaluate(() => localStorage.getItem('api_token')).catch(() => null);
  if (current === cachedToken) return;

  await page.evaluate(([token, username]) => {
    localStorage.setItem('api_token', token);
    localStorage.setItem('auth-storage', JSON.stringify({ state: { token, user: { username, is_admin: true } }, version: 0 }));
  }, [cachedToken, TEST_ADMIN.username]);
  await page.reload();
}
