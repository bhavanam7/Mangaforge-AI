import apiClient from './client'

export const getStorySession = (projectId) => apiClient.get(`/projects/${projectId}/story/`)
export const sendStoryMessage = (projectId, content) => apiClient.post(`/projects/${projectId}/story/`, { content })
export const finalizeStory = (projectId) => apiClient.post(`/projects/${projectId}/story/finalize/`)
