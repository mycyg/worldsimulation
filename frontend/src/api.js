import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
  headers: { 'Content-Type': 'application/json' },
})

// Scenarios
export const createScenario = (data) => api.post('/scenarios', data).then(r => r.data)
export const listScenarios = () => api.get('/scenarios').then(r => r.data)
export const getScenario = (id) => api.get(`/scenarios/${id}`).then(r => r.data)
export const updateScenario = (id, data) => api.put(`/scenarios/${id}`, data).then(r => r.data)
export const deleteScenario = (id) => api.delete(`/scenarios/${id}`).then(r => r.data)
export const uploadFiles = (id, files) => {
  const fd = new FormData()
  files.forEach(f => fd.append('files', f))
  return api.post(`/scenarios/${id}/upload`, fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000,
  }).then(r => r.data)
}
export const parseRules = (id) => api.post(`/scenarios/${id}/parse-rules`).then(r => r.data)

// Entities
export const listEntities = (id) => api.get(`/scenarios/${id}/entities`).then(r => r.data)
export const generateEntities = (id) => api.post(`/scenarios/${id}/generate`, {}, { timeout: 600000 }).then(r => r.data)
export const updateEntity = (id, data) => api.put(`/entities/${id}`, data).then(r => r.data)
export const deleteEntity = (id) => api.delete(`/entities/${id}`).then(r => r.data)
export const addEntity = (scenarioId, data) => api.post(`/scenarios/${scenarioId}/entities`, data).then(r => r.data)

// Simulation
export const startSim = (id) => api.post(`/simulations/${id}/start`).then(r => r.data)
export const pauseSim = (id) => api.post(`/simulations/${id}/pause`).then(r => r.data)
export const resumeSim = (id) => api.post(`/simulations/${id}/resume`).then(r => r.data)
export const stopSim = (id) => api.post(`/simulations/${id}/stop`).then(r => r.data)
export const resetSim = (id) => api.post(`/simulations/${id}/reset`).then(r => r.data)
export const injectEvent = (id, event) => api.post(`/simulations/${id}/inject`, { event }).then(r => r.data)
export const getSimState = (id) => api.get(`/simulations/${id}/state`).then(r => r.data)
export const getTimeline = (id) => api.get(`/simulations/${id}/timeline`).then(r => r.data)
export const getRounds = (id) => api.get(`/simulations/${id}/rounds`).then(r => r.data)
export const getMetrics = (id) => api.get(`/simulations/${id}/metrics`).then(r => r.data)

// Reports
export const getReport = (id) => api.get(`/reports/${id}`).then(r => r.data)
export const generateReport = (id) => api.post(`/reports/${id}/generate`, {}, { timeout: 300000 }).then(r => r.data)
export const exportReport = (id, format) => `/api/reports/${id}/export/${format}`

// Knowledge Graph
export const getGraphData = (id) => api.get(`/simulations/${id}/graph`).then(r => r.data)
export const searchGraph = (id, query) => api.post(`/simulations/${id}/graph/search`, { query }).then(r => r.data)
