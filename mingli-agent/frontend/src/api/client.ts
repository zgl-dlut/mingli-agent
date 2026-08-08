/**
 * API 客户端 - 封装 axios，统一处理认证和错误
 */
import axios from 'axios'

const apiClient = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// 请求拦截器 - 自动附加 Token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('mingli_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 响应拦截器 - 统一错误处理
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('mingli_token')
      localStorage.removeItem('mingli_user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export default apiClient
