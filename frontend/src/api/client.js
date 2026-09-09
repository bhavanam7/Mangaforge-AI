import axios from 'axios'

const ACCESS_KEY = 'mangaforge_access_token'
const REFRESH_KEY = 'mangaforge_refresh_token'

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000/api',
  headers: { 'Content-Type': 'application/json' },
})

apiClient.interceptors.request.use((config) => {
  const accessToken = sessionStorage.getItem(ACCESS_KEY)
  if (accessToken && !config.skipAuthRefresh) config.headers.Authorization = `Bearer ${accessToken}`
  if (config.data instanceof FormData) delete config.headers['Content-Type']
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status !== 401 || originalRequest?.skipAuthRefresh || originalRequest?._retry) {
      return Promise.reject(error)
    }

    const refreshToken = sessionStorage.getItem(REFRESH_KEY)
    if (!refreshToken) return Promise.reject(error)

    originalRequest._retry = true
    try {
      const response = await apiClient.post('/auth/refresh/', { refresh: refreshToken }, { skipAuthRefresh: true })
      sessionStorage.setItem(ACCESS_KEY, response.data.access)
      if (response.data.refresh) sessionStorage.setItem(REFRESH_KEY, response.data.refresh)
      originalRequest.headers.Authorization = `Bearer ${response.data.access}`
      return apiClient(originalRequest)
    } catch (refreshError) {
      sessionStorage.removeItem(ACCESS_KEY)
      sessionStorage.removeItem(REFRESH_KEY)
      sessionStorage.removeItem('mangaforge_user')
      window.dispatchEvent(new Event('mangaforge:auth-expired'))
      return Promise.reject(refreshError)
    }
  },
)

export default apiClient
