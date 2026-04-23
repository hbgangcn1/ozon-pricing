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

async function renameWithRetry(src, dst, attempts = 5, baseDelayMs = 80) {
  let lastErr;
  for (let i = 0; i < attempts; i += 1) {
    try {
      await fs.rename(src, dst);
      return;
    } catch (err) {
      lastErr = err;
      if (err && (err.code === 'EPERM' || err.code === 'EBUSY' || err.code === 'EACCES')) {
        await new Promise((r) => setTimeout(r, baseDelayMs * (i + 1)));
        continue;
      }
      throw err;
    }
  }
  throw lastErr;
}

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

  await rewriteMarker(token, markerFile);

  return token;
}

export function invalidateAdminToken() {
  cachedToken = null;
  cachedExpSec = null;
}

export async function rewriteMarker(token, markerFile) {
  if (typeof token !== 'string' || token.length < 20) {
    throw new Error(`rewriteMarker: token must be a non-empty JWT string, got ${typeof token} length=${token?.length}`);
  }
  await fs.mkdir(path.dirname(markerFile), { recursive: true });
  const exp = decodeExp(token);
  const issuedAt = Math.floor(Date.now() / 1000);
  if (typeof exp !== 'number' || !Number.isFinite(exp)) {
    throw new Error(`rewriteMarker: decodeExp returned invalid exp: ${exp}`);
  }
  const tmp = `${markerFile}.tmp`;
  await fs.writeFile(tmp, JSON.stringify({ token, exp, issuedAt }, null, 2), 'utf8');
  await renameWithRetry(tmp, markerFile);
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
