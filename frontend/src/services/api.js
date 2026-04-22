import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '../stores/authStore'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'
let refreshPromise = null

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
})

function getCsrfToken() {
  const match = document.cookie.match(/(?:^|;\s*)csrf_token=([^;]*)/)
  return match ? decodeURIComponent(match[1]) : null
}

async function refreshAccessToken() {
  const csrfToken = getCsrfToken()
  const response = await axios.post(
    '/auth/refresh',
    null,
    {
      baseURL: API_BASE_URL,
      withCredentials: true,
      headers: csrfToken ? { 'X-CSRF-Token': csrfToken } : {},
    }
  )
  return response.data.access_token
}

function buildSessionExpiredLoginUrl() {
  const returnTo = encodeURIComponent(`${window.location.pathname}${window.location.search || ''}`)
  return `/login?returnTo=${returnTo}&reason=expired`
}

function isSessionKickedDetail(detail) {
  return typeof detail === 'object'
    && detail !== null
    && Object.prototype.hasOwnProperty.call(detail, 'reason')
}

function clearAuthForRedirect() {
  useAuthStore.getState().logout()
  if (import.meta.env.MODE === 'test') {
    localStorage.removeItem('api_user')
    localStorage.removeItem('api_token')
  }
}

function redirectToExpiredLogin() {
  clearAuthForRedirect()
  toast.error('会话已过期，您的填写内容已保存。请重新登录。')
  window.location.href = buildSessionExpiredLoginUrl()
}

function redirectToUnauthorizedLogin(message) {
  clearAuthForRedirect()
  toast.error(message || '登录状态已失效，请重新登录。')
  window.location.href = '/login'
}

if (import.meta.env.MODE !== 'test') {
  apiClient.interceptors.request.use((config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    const csrfToken = getCsrfToken()
    if (csrfToken) {
      config.headers['X-CSRF-Token'] = csrfToken
    }
    return config;
  });
}

apiClient.interceptors.response.use(
  (response) => response.data,
  async (error) => {
    const originalRequest = error.config || {}
    const isRefreshRequest = originalRequest.url?.includes('/auth/refresh')
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401 && isSessionKickedDetail(detail)) {
      useAuthStore.getState().setSessionKicked({ reason: detail.reason ?? null })
      return Promise.reject(error)
    }

    const shouldRetry = status === 401
      && !originalRequest._retry
      && !isRefreshRequest

    if (shouldRetry) {
      originalRequest._retry = true
      try {
        if (!refreshPromise) {
          refreshPromise = refreshAccessToken().finally(() => {
            refreshPromise = null
          })
        }
        const newAccessToken = await refreshPromise
        useAuthStore.getState().setToken(newAccessToken)
        originalRequest.headers = originalRequest.headers || {}
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`
        return apiClient(originalRequest)
      } catch (refreshError) {
        const refreshDetail = refreshError?.response?.data?.detail
        if (refreshError?.response?.status === 401 && window.location.pathname !== '/login') {
          if (isSessionKickedDetail(refreshDetail)) {
            useAuthStore.getState().setSessionKicked({ reason: refreshDetail.reason ?? null })
          } else if (typeof refreshDetail === 'string') {
            redirectToUnauthorizedLogin(refreshDetail)
          } else {
            redirectToExpiredLogin()
          }
        }
        return Promise.reject(error)
      }
    }

    if (status === 401 && typeof detail === 'string' && window.location.pathname !== '/login') {
      redirectToUnauthorizedLogin(detail)
      return Promise.reject(error)
    }

    if (error.code === 'ECONNABORTED') {
      error.userMessage = '请求超时，请检查网络连接'
    } else if (!error.response) {
      error.userMessage = '网络连接失败，请稍后重试'
    } else if (error.response.status >= 500) {
      error.userMessage = '服务器繁忙，请稍后重试'
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  login: (username, password) =>
    apiClient.post('/auth/login', { username, password }),
  logout: () => apiClient.post('/auth/logout'),
  getMe: () => apiClient.get('/auth/me'),
  changePassword: (data) => apiClient.post('/auth/change-password', data),
  register: (data) => apiClient.post('/auth/register', data),
  loginAs: (username, password) =>
    apiClient.post('/auth/login', { username, password }),
  checkUsername: (username) =>
    apiClient.get('/auth/check-username', { params: { username } }),
  getSecurityQuestions: () => apiClient.get('/auth/security-questions'),
  startRecovery: (username) =>
    apiClient.post('/auth/recover/start', { username }),
  verifySecurity: (username, answer) =>
    apiClient.post('/auth/recover/verify', { username, answer }),
  resetPassword: (reset_token, new_password) =>
    apiClient.post('/auth/recover/reset', { reset_token, new_password }),
}

export const logoutUser = () => {
  clearAuthForRedirect()
  window.location.href = '/login'
}

export const productsAPI = {
  getAll: () => apiClient.get('/products', { params: { limit: 1000 } }),
  getById: (id) => apiClient.get(`/products/${id}`),
  create: (data) => apiClient.post('/products', data),
  update: (id, data) => apiClient.put(`/products/${id}`, data),
  delete: (id) => apiClient.delete(`/products/${id}`),
}

export const logisticsAPI = {
  getAll: (params) => apiClient.get('/logistics', { params }),
  getById: (id) => apiClient.get(`/logistics/${id}`),
  create: (data) => apiClient.post('/logistics', data),
  update: (id, data) => apiClient.put(`/logistics/${id}`, data),
  delete: (id) => apiClient.delete(`/logistics/${id}`),
  batchDelete: (ids) => apiClient.post('/logistics/batch-delete', ids),
  toggleTransport: (id) => apiClient.patch(`/logistics/${id}/toggle-transport`),
}

export const pricingAPI = {
  calculate: (productId, mode, productData) =>
    apiClient.post('/pricing/calculate', {
      product_id: productId,
      product_data: productData,
      mode: mode,
    }),
  calculateGrouped: (productId, mode, productData) =>
    apiClient.post('/pricing/calculate-grouped', {
      product_id: productId,
      product_data: productData,
      mode: mode,
    }),
}

export const subscriptionsAPI = {
  getPlans: () => apiClient.get('/subscriptions/plans'),
  getCurrent: () => apiClient.get('/subscriptions/current'),
}

export const plansAPI = {
  getAll: (activeOnly = false) => apiClient.get('/subscriptions/plans', { params: { active_only: activeOnly } }),
  create: (data) => apiClient.post('/subscriptions/plans', data),
  update: (id, data) => apiClient.put(`/subscriptions/plans/${id}`, data),
  delete: (id) => apiClient.delete(`/subscriptions/plans/${id}`),
  toggleActive: (id) => apiClient.patch(`/subscriptions/plans/${id}/toggle`),
}

export const ordersAPI = {
  getAll: (params = {}) => apiClient.get('/orders', { params }),
}

export const paymentAPI = {
  createOrder: (data) => apiClient.post('/payments/create', data),
  getStatus: (orderId) => apiClient.get(`/payments/${orderId}/status`),
}

export const adminAPI = {
  getUsers: (page = 1, pageSize = 20, keyword = '') =>
    apiClient.get('/admin/users', { params: { page, page_size: pageSize, keyword } }),
  createUser: (data) => apiClient.post('/admin/users', data),
  updateUser: (id, data) => apiClient.put(`/admin/users/${id}`, data),
  resetPassword: (id) => apiClient.post(`/admin/users/${id}/reset-password`),
  deleteUser: (id) => apiClient.delete(`/admin/users/${id}`),
  getPlans: () => apiClient.get('/subscriptions/plans'),
  updatePlan: (id, data) => apiClient.put(`/admin/plans/${id}`, data),
  extendSubscription: (id, days) => apiClient.post(`/admin/users/${id}/subscription/extend`, { days }),
  adjustCalculations: (id, delta) => apiClient.post(`/admin/users/${id}/calculations/adjust`, { delta }),
  setUserType: (id, userType) => apiClient.post(`/admin/users/${id}/type`, { user_type: userType }),
}

export const settingsAPI = {
  get: () => apiClient.get('/settings'),
  updateOpenRegistration: (enabled) => apiClient.put('/settings/open-registration', null, { params: { enabled } }),
  getBackups: () => apiClient.get('/settings/backups'),
  createBackup: () => apiClient.post('/settings/backup'),
  getBackupSettings: () => apiClient.get('/settings/backup/settings'),
  updateBackupSettings: (data) => apiClient.put('/settings/backup/settings', data),
  getBackupStats: () => apiClient.get('/settings/backup/stats'),
  deleteBackup: (filename) => apiClient.delete(`/settings/backup/${filename}`),
  restoreBackup: (filename, createSnapshot = true) =>
    apiClient.post(`/settings/backup/${filename}/restore`, { create_snapshot: createSnapshot }),
  downloadBackup: (filename) =>
    apiClient.get(`/settings/backup/${filename}/download`, { responseType: 'blob' }),
}

export const statisticsAPI = {
  getOverview: () => apiClient.get('/statistics/overview'),
  getRetention: () => apiClient.get('/statistics/retention'),
  getRevenue: (months = 12) => apiClient.get('/statistics/revenue', { params: { months } }),
  getLoginLogs: (page = 1, pageSize = 20, search = '', dateFrom = '', dateTo = '') =>
    apiClient.get('/statistics/login-logs', {
      params: {
        page,
        page_size: pageSize,
        search: search || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      },
    }),
  getAdminLogs: (page = 1, pageSize = 20, search = '', dateFrom = '', dateTo = '') =>
    apiClient.get('/statistics/admin-logs', {
      params: {
        page,
        page_size: pageSize,
        search: search || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      },
    }),
  getActiveUsers: () => apiClient.get('/statistics/active-users'),
}

export const commissionCategoriesAPI = {
  getAll: () => apiClient.get('/commission-categories'),
  create: (data) => apiClient.post('/commission-categories', data),
  update: (id, data) => apiClient.patch(`/commission-categories/${id}`, data),
  delete: (id) => apiClient.delete(`/commission-categories/${id}`),
}

export const logisticsPoolAPI = {
  getAll: (params) => apiClient.get('/logistics-pool', { params }),
  importXlsx: (formData) => apiClient.post('/logistics-pool/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  addToMyLogistics: (id) => apiClient.post(`/logistics-pool/${id}/add-to-my-logistics`),
  batchAddToMyLogistics: (ids) => apiClient.post('/logistics-pool/batch-add-to-my-logistics', { ids }),
  deleteAll: () => apiClient.delete('/logistics-pool/all'),
}

export const productImportAPI = {
  preview: (formData) => apiClient.post('/products/import/preview', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  confirm: (data) => apiClient.post('/products/import/confirm', data),
}

export default apiClient
