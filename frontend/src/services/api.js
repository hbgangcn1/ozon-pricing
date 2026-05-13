import axios from 'axios'
import { toast } from 'sonner'
import { useAuthStore } from '../stores/authStore'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

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
    sessionStorage.removeItem('api_token')
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
  apiClient.interceptors.request.use(async (config) => {
    const token = useAuthStore.getState().token;
    if (token) {
      // Skip proactive refresh for refresh endpoint itself to avoid self-deadlock
      // (refreshToken() awaits authAPI.refreshAccess(), whose request interceptor
      // would otherwise re-enter refreshToken() and await the same refreshPromise).
      const isRefreshEndpoint = config.url?.includes('/auth/refresh-access')
        || config.url?.includes('/auth/refresh')
      if (!isRefreshEndpoint && useAuthStore.getState().shouldRefreshToken()) {
        try {
          await useAuthStore.getState().refreshToken()
        } catch (_) {
          // Proactive refresh failed; proceed with existing token
        }
      }
      const currentToken = useAuthStore.getState().token
      if (currentToken) {
        config.headers.Authorization = `Bearer ${currentToken}`;
      }
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
      || originalRequest.url?.includes('/auth/refresh-access')
    const status = error.response?.status
    const detail = error.response?.data?.detail

    if (status === 401 && isSessionKickedDetail(detail)) {
      useAuthStore.getState().setSessionKicked({ reason: detail.reason ?? null })
      return Promise.reject(error)
    }

    const isLocalAuth401 = originalRequest.auth401Mode === 'local'

    const shouldRetry = status === 401
      && !originalRequest._retry
      && !isRefreshRequest
      && !isLocalAuth401

    if (shouldRetry) {
      originalRequest._retry = true
      try {
        const newAccessToken = await useAuthStore.getState().refreshToken()
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

    if (
      status === 401
      && typeof detail === 'string'
      && window.location.pathname !== '/login'
      && !isLocalAuth401
    ) {
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
  login: (username, password, options = {}) => apiClient.post('/auth/login', { username, password }, options),
  logout: (options = {}) => apiClient.post('/auth/logout', null, options),
  getMe: (options = {}) => apiClient.get('/auth/me', options),
  refreshAccess: (options = {}) => apiClient.post('/auth/refresh-access', null, options),
  setSecurityQuestion: (question, answer, options = {}) => apiClient.post('/auth/security-question', { question, answer }, options),
  changePassword: (data, options = {}) => apiClient.post('/auth/change-password', data, { auth401Mode: 'local', ...options }),
  register: (data, options = {}) => apiClient.post('/auth/register', data, options),
  loginAs: (username, password, options = {}) => apiClient.post('/auth/login', { username, password }, options),
  checkUsername: (username, options = {}) => apiClient.get('/auth/check-username', { params: { username }, ...options }),
  getSecurityQuestions: (options = {}) => apiClient.get('/auth/security-questions', options),
  startRecovery: (username, options = {}) => apiClient.post('/auth/recover/start', { username }, options),
  verifySecurity: (username, answer, options = {}) => apiClient.post('/auth/recover/verify', { username, answer }, options),
  resetPassword: (reset_token, new_password, options = {}) => apiClient.post('/auth/recover/reset', { reset_token, new_password }, options),
}

export const logoutUser = () => {
  clearAuthForRedirect()
  window.location.href = '/login'
}

export const productsAPI = {
  getAll: (options = {}) => apiClient.get('/products', { params: { limit: 200 }, ...options }),
  getById: (id, options = {}) => apiClient.get(`/products/${id}`, options),
  create: (data, options = {}) => apiClient.post('/products', data, options),
  update: (id, data, options = {}) => apiClient.put(`/products/${id}`, data, options),
  delete: (id, options = {}) => apiClient.delete(`/products/${id}`, options),
}

export const logisticsAPI = {
  getAll: (params, options = {}) => apiClient.get('/logistics', { params, ...options }),
  getById: (id, options = {}) => apiClient.get(`/logistics/${id}`, options),
  create: (data, options = {}) => apiClient.post('/logistics', data, options),
  update: (id, data, options = {}) => apiClient.put(`/logistics/${id}`, data, options),
  delete: (id, options = {}) => apiClient.delete(`/logistics/${id}`, options),
  batchDelete: (ids, options = {}) => apiClient.post('/logistics/batch-delete', ids, options),
  toggleTransport: (id, options = {}) => apiClient.patch(`/logistics/${id}/toggle-transport`, null, options),
}

export const pricingAPI = {
  calculate: (productId, mode, productData, options = {}) => apiClient.post('/pricing/calculate', { product_id: productId, product_data: productData, mode: mode }, options),
  calculateGrouped: (productId, mode, productData, options = {}) => apiClient.post('/pricing/calculate-grouped', { product_id: productId, product_data: productData, mode: mode }, options),
}

export const subscriptionsAPI = {
  getPlans: (options = {}) => apiClient.get('/subscriptions/plans', options),
  getCurrent: (options = {}) => apiClient.get('/subscriptions/current', options),
}

// Priority 3: documents non-obvious endpoint contract for OpenSpec change add-pro-trial-overflow
// (claim is one-shot 7-day Pro trial; status drives banner + expired modal).
export const trialAPI = {
  claim: (options = {}) => apiClient.post('/subscriptions/trial/claim', null, options),
  getStatus: (options = {}) => apiClient.get('/subscriptions/trial/status', options),
}

// Priority 3: documents non-obvious endpoint contract for OpenSpec change add-pro-trial-overflow
// (reselect consumes the open 48h window; status drives the auto-popup modal).
export const overflowAPI = {
  reselect: (keepIds, options = {}) => apiClient.post('/logistics/overflow/reselect', { keep_ids: keepIds }, options),
  getStatus: (options = {}) => apiClient.get('/logistics/overflow/status', options),
}

export const plansAPI = {
  getAll: (activeOnly = false, options = {}) => apiClient.get('/subscriptions/plans', { params: { active_only: activeOnly }, ...options }),
  create: (data, options = {}) => apiClient.post('/subscriptions/plans', data, options),
  update: (id, data, options = {}) => apiClient.put(`/subscriptions/plans/${id}`, data, options),
  delete: (id, options = {}) => apiClient.delete(`/subscriptions/plans/${id}`, options),
  toggleActive: (id, options = {}) => apiClient.patch(`/subscriptions/plans/${id}/toggle`, null, options),
}

export const ordersAPI = {
  getAll: (params = {}, options = {}) => apiClient.get('/orders', { params, ...options }),
}

export const paymentAPI = {
  createOrder: (data, options = {}) => apiClient.post('/payments/create', data, options),
  getStatus: (orderId, options = {}) => apiClient.get(`/payments/${orderId}/status`, options),
}

export const adminAPI = {
  getUsers: (page = 1, pageSize = 20, keyword = '', options = {}) => apiClient.get('/admin/users', { params: { page, page_size: pageSize, keyword }, ...options }),
  createUser: (data, options = {}) => apiClient.post('/admin/users', data, options),
  updateUser: (id, data, options = {}) => apiClient.put(`/admin/users/${id}`, data, options),
  resetPassword: (id, options = {}) => apiClient.post(`/admin/users/${id}/reset-password`, null, options),
  deleteUser: (id, options = {}) => apiClient.delete(`/admin/users/${id}`, options),
  getPlans: (options = {}) => apiClient.get('/subscriptions/plans', options),
  updatePlan: (id, data, options = {}) => apiClient.put(`/admin/plans/${id}`, data, options),
  extendSubscription: (id, days, options = {}) => apiClient.post(`/admin/users/${id}/subscription/extend`, { days }, options),
  adjustCalculations: (id, delta, options = {}) => apiClient.post(`/admin/users/${id}/calculations/adjust`, { delta }, options),
  setUserType: (id, userType, options = {}) => apiClient.post(`/admin/users/${id}/type`, { user_type: userType }, options),
}

export const settingsAPI = {
  get: (options = {}) => apiClient.get('/settings', options),
  updateOpenRegistration: (enabled, options = {}) => apiClient.put('/settings/open-registration', null, { params: { enabled }, ...options }),
  getBackups: (options = {}) => apiClient.get('/settings/backups', options),
  createBackup: (options = {}) => apiClient.post('/settings/backup', null, options),
  getBackupSettings: (options = {}) => apiClient.get('/settings/backup/settings', options),
  updateBackupSettings: (data, options = {}) => apiClient.put('/settings/backup/settings', data, options),
  getBackupStats: (options = {}) => apiClient.get('/settings/backup/stats', options),
  deleteBackup: (filename, options = {}) => apiClient.delete(`/settings/backup/${filename}`, options),
  restoreBackup: (filename, createSnapshot = true, options = {}) => apiClient.post(`/settings/backup/${filename}/restore`, { create_snapshot: createSnapshot }, options),
  downloadBackup: (filename, options = {}) => apiClient.get(`/settings/backup/${filename}/download`, { responseType: 'blob', ...options }),
}

export const statisticsAPI = {
  getOverview: (options = {}) => apiClient.get('/statistics/overview', options),
  getRetention: (options = {}) => apiClient.get('/statistics/retention', options),
  getRevenue: (months = 12, options = {}) => apiClient.get('/statistics/revenue', { params: { months }, ...options }),
  getLoginLogs: (page = 1, pageSize = 20, search = '', dateFrom = '', dateTo = '', options = {}) => apiClient.get('/statistics/login-logs', { params: { page, page_size: pageSize, search: search || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }, ...options }),
  getAdminLogs: (page = 1, pageSize = 20, search = '', dateFrom = '', dateTo = '', options = {}) => apiClient.get('/statistics/admin-logs', { params: { page, page_size: pageSize, search: search || undefined, date_from: dateFrom || undefined, date_to: dateTo || undefined }, ...options }),
  getActiveUsers: (options = {}) => apiClient.get('/statistics/active-users', options),
}

export const commissionCategoriesAPI = {
  getAll: (options = {}) => apiClient.get('/commission-categories', options),
  create: (data, options = {}) => apiClient.post('/commission-categories', data, options),
  update: (id, data, options = {}) => apiClient.patch(`/commission-categories/${id}`, data, options),
  delete: (id, options = {}) => apiClient.delete(`/commission-categories/${id}`, options),
}

export const logisticsPoolAPI = {
  getAll: (params, options = {}) => apiClient.get('/logistics-pool', { params, ...options }),
  importXlsx: (formData, options = {}) => apiClient.post('/logistics-pool/import', formData, { headers: { 'Content-Type': 'multipart/form-data' }, ...options }),
  addToMyLogistics: (id, options = {}) => apiClient.post(`/logistics-pool/${id}/add-to-my-logistics`, null, options),
  batchAddToMyLogistics: (ids, options = {}) => apiClient.post('/logistics-pool/batch-add-to-my-logistics', { ids }, options),
  deleteAll: (options = {}) => apiClient.delete('/logistics-pool/all', options),
}

export const productImportAPI = {
  preview: (formData, options = {}) => apiClient.post('/products/import/preview', formData, { headers: { 'Content-Type': 'multipart/form-data' }, ...options }),
  confirm: (data, options = {}) => apiClient.post('/products/import/confirm', data, options),
}

export default apiClient
