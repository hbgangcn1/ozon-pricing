import { apiLogin, apiGetUsers, apiDeleteUser } from './helpers/api-helpers.js';
import { TEST_ADMIN } from './fixtures/test-data.js';

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
    const resp = await apiGetUsers(adminToken);
    users = Array.isArray(resp) ? resp : (resp.users || []);
  } catch {
    console.warn('[global-teardown] Failed to fetch users, skipping cleanup');
    return;
  }

  const e2eUsers = users.filter(u => /^e2e/.test(u.username));
  if (e2eUsers.length === 0) return;

  let deleted = 0;
  for (const user of e2eUsers) {
    try {
      await apiDeleteUser(adminToken, user.id);
      deleted++;
    } catch {
      console.warn(`[global-teardown] Failed to delete user ${user.username} (id=${user.id})`);
    }
  }

  if (deleted > 0) {
    console.log(`[global-teardown] Cleaned up ${deleted} e2e user(s)`);
  }
}

export default globalTeardown;
