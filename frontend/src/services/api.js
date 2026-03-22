import axios from 'axios'

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api'

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('api_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('api_token')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  login: (username, password) =>
    apiClient.post('/auth/login', { username, password }),
  logout: () => apiClient.post('/auth/logout'),
  getMe: () => apiClient.get('/auth/me'),
}

export const productsAPI = {
  getAll: () => apiClient.get('/products'),
  getById: (id) => apiClient.get(`/products/${id}`),
  create: (data) => apiClient.post('/products', data),
  update: (id, data) => apiClient.put(`/products/${id}`, data),
  delete: (id) => apiClient.delete(`/products/${id}`),
}

export const logisticsAPI = {
  getAll: () => apiClient.get('/logistics'),
  getById: (id) => apiClient.get(`/logistics/${id}`),
  create: (data) => apiClient.post('/logistics', data),
  update: (id, data) => apiClient.put(`/logistics/${id}`, data),
  delete: (id) => apiClient.delete(`/logistics/${id}`),
}

export const pricingAPI = {
  calculate: (productId, logisticsId, mode = 'fast') =>
    apiClient.post('/pricing/calculate', null, {
      params: { product_id: productId, logistics_id: logisticsId, mode },
    }),
}

export default apiClient
