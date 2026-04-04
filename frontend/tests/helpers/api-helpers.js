import { API_BASE } from '../fixtures/test-data.js';

export async function apiLogin(username, password) {
  const resp = await fetch(`${API_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiLogin failed ${resp.status}: ${body}`);
  }
  const data = await resp.json();
  return data.access_token || data.token;
}

export async function apiGetMe(token) {
  const resp = await fetch(`${API_BASE}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiGetMe failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

export async function apiCreateUser(token, userData) {
  const resp = await fetch(`${API_BASE}/admin/users`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(userData),
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiCreateUser failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

export async function apiDeleteUser(token, userId) {
  const resp = await fetch(`${API_BASE}/admin/users/${userId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiDeleteUser failed ${resp.status}: ${body}`);
  }
  return resp.status === 204 ? null : resp.json();
}

export async function apiToggleRegistration(token, enabled) {
  const resp = await fetch(`${API_BASE}/settings/open-registration?enabled=${enabled}`, {
    method: 'PUT',
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiToggleRegistration failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

export async function apiGetSettings(token) {
  const resp = await fetch(`${API_BASE}/settings`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiGetSettings failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

export async function apiGetUsers(token) {
  const resp = await fetch(`${API_BASE}/admin/users`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiGetUsers failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

export async function apiCreateProduct(token, productData) {
  const resp = await fetch(`${API_BASE}/products`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
    body: JSON.stringify(productData),
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiCreateProduct failed ${resp.status}: ${body}`);
  }
  return resp.json();
}

export async function apiDeleteProduct(token, productId) {
  const resp = await fetch(`${API_BASE}/products/${productId}`, {
    method: 'DELETE',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiDeleteProduct failed ${resp.status}: ${body}`);
  }
  return resp.status === 204 ? null : resp.json();
}

export async function apiGetProducts(token) {
  const resp = await fetch(`${API_BASE}/products`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!resp.ok) {
    const body = await resp.text();
    throw new Error(`apiGetProducts failed ${resp.status}: ${body}`);
  }
  return resp.json();
}
