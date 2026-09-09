import apiClient from './client'

export const listAllCharacters = () => apiClient.get('/characters/')
export const listCharacters = (projectId) => apiClient.get(`/projects/${projectId}/characters/`)
export const createCharacter = (projectId, payload) => apiClient.post(`/projects/${projectId}/characters/`, payload)
export const getCharacter = (characterId) => apiClient.get(`/characters/${characterId}/`)
export const updateCharacter = (characterId, payload) => apiClient.patch(`/characters/${characterId}/`, payload)
export const deleteCharacter = (characterId) => apiClient.delete(`/characters/${characterId}/`)
