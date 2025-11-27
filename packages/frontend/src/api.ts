import type { GradesSummaryResponse, HeadersResponse, ModelsResponse, ResultsResponse, TopicsResponse } from './types'

const API_BASE = '/api'

export async function fetchModels(): Promise<ModelsResponse> {
  const res = await fetch(`${API_BASE}/models`)
  return res.json()
}

export async function fetchTopics(model?: string): Promise<TopicsResponse> {
  const params = new URLSearchParams()
  if (model) params.set('model', model)
  const res = await fetch(`${API_BASE}/topics?${params}`)
  return res.json()
}

export async function fetchHeaders(): Promise<HeadersResponse> {
  const res = await fetch(`${API_BASE}/headers`)
  return res.json()
}

export async function fetchResults(params: {
  model?: string
  topic?: string
  search?: string
}): Promise<ResultsResponse> {
  const searchParams = new URLSearchParams()
  if (params.model) searchParams.set('model', params.model)
  if (params.topic) searchParams.set('topic', params.topic)
  if (params.search) searchParams.set('search', params.search)
  const res = await fetch(`${API_BASE}/results?${searchParams}`)
  return res.json()
}

export async function fetchGradesSummary(params: {
  models?: string[]
  topics?: string[]
}): Promise<GradesSummaryResponse> {
  const searchParams = new URLSearchParams()
  if (params.models && params.models.length > 0) {
    searchParams.set('models', params.models.join(','))
  }
  if (params.topics && params.topics.length > 0) {
    searchParams.set('topics', params.topics.join(','))
  }
  const res = await fetch(`${API_BASE}/grades/summary?${searchParams}`)
  return res.json()
}
