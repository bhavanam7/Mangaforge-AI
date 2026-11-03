import apiClient from './client'

export const getStorySession = (projectId) => apiClient.get(`/projects/${projectId}/story/`)

// `context` carries the enhancement-hub markers
// (`{ scope: 'character' | 'background' | 'scene', target_id: 'char_02' }`).
// They are optional: without them the backend routes the turn itself.
export const sendStoryMessage = (projectId, content, context = {}) =>
  apiClient.post(`/projects/${projectId}/story/`, {
    content,
    ...(context.scope ? { scope: context.scope } : {}),
    ...(context.target_id ? { target_id: context.target_id } : {}),
  })

export const finalizeStory = (projectId) => apiClient.post(`/projects/${projectId}/story/finalize/`)
