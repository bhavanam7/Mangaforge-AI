import apiClient from './client'

export const listEpisodes = (projectId) => apiClient.get(`/projects/${projectId}/episodes/`)
export const createEpisode = (projectId, payload) => apiClient.post(`/projects/${projectId}/episodes/`, payload)
export const getEpisode = (episodeId) => apiClient.get(`/episodes/${episodeId}/`)
export const updateEpisode = (episodeId, payload) => apiClient.patch(`/episodes/${episodeId}/`, payload)
export const deleteEpisode = (episodeId) => apiClient.delete(`/episodes/${episodeId}/`)