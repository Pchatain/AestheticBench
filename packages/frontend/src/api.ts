import type { AnnotationCreate, AnnotationLookupResponse, AnnotationsResponse, AnnotationSaveResponse, DefaultQuestionsResponse, ExperimentPromptsResponse, GradesSummaryResponse, HeadersResponse, ModelsResponse, MultiQuestionExperimentRequest, MultiQuestionExperimentResponse, PlaygroundResponse, PromptResult, ResultsResponse, SaveExperimentResponse, SaveMultiExperimentRequest, SinglePairRequest, TopicsResponse } from './types'

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

export async function runPrompt(prompt: string, model: string): Promise<PlaygroundResponse> {
  const res = await fetch(`${API_BASE}/playground/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt, model }),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to run prompt')
  }
  return res.json()
}

export async function fetchAnnotations(params?: {
  result_uid?: number
  model?: string
}): Promise<AnnotationsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.result_uid !== undefined) searchParams.set('result_uid', String(params.result_uid))
  if (params?.model) searchParams.set('model', params.model)
  const res = await fetch(`${API_BASE}/annotations?${searchParams}`)
  return res.json()
}

export async function lookupAnnotation(result_uid: number, model: string): Promise<AnnotationLookupResponse> {
  const params = new URLSearchParams({ result_uid: String(result_uid), model })
  const res = await fetch(`${API_BASE}/annotations/lookup?${params}`)
  return res.json()
}

export async function saveAnnotation(data: AnnotationCreate): Promise<AnnotationSaveResponse> {
  const res = await fetch(`${API_BASE}/annotations`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to save annotation')
  }
  return res.json()
}

export async function deleteAnnotation(annotationId: string): Promise<void> {
  const res = await fetch(`${API_BASE}/annotations/${annotationId}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to delete annotation')
  }
}

// Multi-Question Experiment API

export async function fetchExperimentPrompts(models?: string[]): Promise<ExperimentPromptsResponse> {
  const params = new URLSearchParams()
  if (models && models.length > 0) {
    params.set('models', models.join(','))
  }
  const res = await fetch(`${API_BASE}/experiments/prompts?${params}`)
  return res.json()
}

export async function fetchDefaultQuestions(): Promise<DefaultQuestionsResponse> {
  const res = await fetch(`${API_BASE}/experiments/questions`)
  return res.json()
}

export async function runMultiQuestionExperiment(request: MultiQuestionExperimentRequest): Promise<MultiQuestionExperimentResponse> {
  const res = await fetch(`${API_BASE}/experiments/multi/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to run experiment')
  }
  return res.json()
}

export async function gradeSinglePair(request: SinglePairRequest): Promise<PromptResult> {
  const res = await fetch(`${API_BASE}/experiments/grade-single`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to grade pair')
  }
  return res.json()
}

export async function saveMultiExperimentResults(request: SaveMultiExperimentRequest): Promise<SaveExperimentResponse> {
  const res = await fetch(`${API_BASE}/experiments/multi/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to save experiment')
  }
  return res.json()
}
