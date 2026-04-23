/* eslint-env node */
import { test, expect } from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
import { invalidateAdminToken, getAdminToken, REFRESH_THRESHOLD_SEC } from './helpers/admin-token.js';
import { ADMIN_AUTH_FILE, ADMIN_MARKER_FILE } from './helpers/auth-paths.js';

test('admin storageState exists and contains api_token in localStorage', () => {
  const authPath = path.resolve('tests/.auth/admin.json');
  if (!fs.existsSync(authPath)) {
    throw new Error('tests/.auth/admin.json missing. Run --project=setup first.');
  }
  const storageState = JSON.parse(fs.readFileSync(authPath, 'utf8'));
  const apiTokenEntry = storageState.origins
    .flatMap((o) => o.localStorage || [])
    .find((i) => i.name === 'api_token');
  expect(apiTokenEntry, 'api_token entry missing in admin.json localStorage').toBeDefined();
  expect(typeof apiTokenEntry.value).toBe('string');
  expect(apiTokenEntry.value.length).toBeGreaterThan(20);
});

test('marker token equals storageState api_token', () => {
  const markerPath = path.resolve('tests/.auth/admin-token-marker.json');
  const authPath = path.resolve('tests/.auth/admin.json');
  if (!fs.existsSync(markerPath)) {
    throw new Error('tests/.auth/admin-token-marker.json missing. Run --project=setup first.');
  }
  if (!fs.existsSync(authPath)) {
    throw new Error('tests/.auth/admin.json missing. Run --project=setup first.');
  }
  const marker = JSON.parse(fs.readFileSync(markerPath, 'utf8'));
  expect(typeof marker.token).toBe('string');
  expect(marker.token.length).toBeGreaterThan(20);
  expect(typeof marker.exp).toBe('number');
  expect(typeof marker.issuedAt).toBe('number');

  const storageState = JSON.parse(fs.readFileSync(authPath, 'utf8'));
  const apiTokenEntry = storageState.origins
    .flatMap((o) => o.localStorage || [])
    .find((i) => i.name === 'api_token');
  expect(apiTokenEntry, 'api_token entry missing in admin.json localStorage').toBeDefined();
  expect(apiTokenEntry.value).toBe(marker.token);
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
