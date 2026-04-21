import { apiLogin, apiDeleteUser } from './helpers/api-helpers.js';
import { TEST_ADMIN, API_BASE } from './fixtures/test-data.js';

const TEST_USER_PATTERNS = [
  /^e2e_/,
  /^test_user_/,
  /^test_admin_/,
  /^int_test_/,
  /^verifycaseuser_/,
  /^prefmode_/,
  /^notypeusr_/,
  /^nullpwd_/,
  /^verifyemci_/,
  /^verifyemail_/,
  /^admin_user_/,
  /^admin_wrong_/,
  /^regular_/,
  /^short_/,
  /^eula_/,
  /^closed_reg_/,
  /^newuser_/,
];

function isTestUser(username) {
  return TEST_USER_PATTERNS.some(p => p.test(username));
}

/**
 * Fetch all users across all pages (page_size=100 per request).
 */
async function fetchAllUsers(token) {
  const allUsers = [];
  let page = 1;
  const pageSize = 100;

  let hasMore = true;
  while (hasMore) {
    const resp = await fetch(
      `${API_BASE}/admin/users?page=${page}&page_size=${pageSize}`,
      { headers: { Authorization: `Bearer ${token}` } },
    );
    if (!resp.ok) break;

    const data = await resp.json();
    const users = data.users || [];
    allUsers.push(...users);

    hasMore = !(allUsers.length >= (data.total || 0) || users.length < pageSize);
    page++;
  }

  return allUsers;
}

async function globalTeardown() {
  let adminToken;
  try {
    adminToken = await apiLogin(TEST_ADMIN.username, TEST_ADMIN.password);
  } catch {
    console.warn('[global-teardown] Admin login failed, skipping e2e user cleanup');
    return;
  }

  let users;
  try {
    users = await fetchAllUsers(adminToken);
  } catch {
    console.warn('[global-teardown] Failed to fetch users, skipping cleanup');
    return;
  }

  const testUsers = users.filter(u => isTestUser(u.username));
  if (testUsers.length === 0) return;

  let deleted = 0;
  for (const user of testUsers) {
    try {
      await apiDeleteUser(adminToken, user.id);
      deleted++;
    } catch {
      console.warn(`[global-teardown] Failed to delete user ${user.username} (id=${user.id})`);
    }
  }

  if (deleted > 0) {
    console.log(`[global-teardown] Cleaned up ${deleted} test user(s)`);
  }
}

export default globalTeardown;
