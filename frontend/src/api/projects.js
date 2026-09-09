import apiClient from './client'

export const listProjects = () => apiClient.get('/projects/')
export const createProject = (payload) => apiClient.post('/projects/', payload)
export const getProject = (projectId) => apiClient.get(`/projects/${projectId}/`)
export const updateProject = (projectId, payload) => apiClient.patch(`/projects/${projectId}/`, payload)
export const deleteProject = (projectId) => apiClient.delete(`/projects/${projectId}/`)
