import apiClient from './client'

export const register = (payload) => apiClient.post('/auth/register/', payload)
export const login = (payload) => apiClient.post('/auth/login/', payload)
export const refresh = (refreshToken) => apiClient.post('/auth/refresh/', { refresh: refreshToken })
export const logout = (refreshToken) => apiClient.post('/auth/logout/', { refresh: refreshToken })
export const getHealth = () => apiClient.get('/health/')
