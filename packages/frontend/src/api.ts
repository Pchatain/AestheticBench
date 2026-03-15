import type {
  AnnotationCreate,
  AnnotationLookupResponse,
  AnnotationsResponse,
  AnnotationSaveResponse,
  CancelResponse,
  DefaultQuestionsResponse,
  DryRunEstimateResponse,
  ExperimentPromptsResponse,
  FileValidationResponse,
  FilesResponse,
  GraderPromptsResponse,
  GradersResponse,
  GraderValidationResponse,
  GradesSummaryResponse,
  GradingEstimateResponse,
  HeadersResponse,
  JobStartResponse,
  JobStatus,
  ModelsResponse,
  MultiQuestionExperimentRequest,
  MultiQuestionExperimentResponse,
  OpenRouterModelsResponse,
  PlaygroundResponse,
  PromptResult,
  PromptsFilesResponse,
  Q1Q4AnnotationCreate,
  Q1Q4AnnotationLookupResponse,
  Q1Q4AnnotationSaveResponse,
  Q1Q4ModelsResponse,
  Q1Q4ResponsesResponse,
  ResultsResponse,
  SaveExperimentResponse,
  SaveMultiExperimentRequest,
  SinglePairRequest,
  TopicsResponse,
  VersionsResponse,
} from './types'

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

export async function fetchGraderPrompts(): Promise<GraderPromptsResponse> {
  const res = await fetch(`${API_BASE}/grader-prompts`)
  return res.json()
}

// === Workflow API ===

export async function fetchVersions(): Promise<VersionsResponse> {
  const res = await fetch(`${API_BASE}/workflow/versions`)
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to fetch versions')
  }
  return res.json()
}

export async function fetchVersionFiles(version: string): Promise<FilesResponse> {
  const res = await fetch(`${API_BASE}/workflow/versions/${encodeURIComponent(version)}/files`)
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to fetch version files')
  }
  return res.json()
}

export async function fetchPromptsFiles(): Promise<PromptsFilesResponse> {
  const res = await fetch(`${API_BASE}/workflow/prompts`)
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to fetch prompts files')
  }
  return res.json()
}

export async function fetchGraders(): Promise<GradersResponse> {
  const res = await fetch(`${API_BASE}/workflow/graders`)
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to fetch graders')
  }
  return res.json()
}

export async function validateGraders(
  grader_ids: string[],
  custom_prompt?: string | null
): Promise<GraderValidationResponse> {
  const res = await fetch(`${API_BASE}/workflow/graders/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ grader_ids, custom_prompt }),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to validate graders')
  }
  return res.json()
}

// === Multi-Question Experiment API ===

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

export async function validateFiles(files: string[]): Promise<FileValidationResponse> {
  const res = await fetch(`${API_BASE}/workflow/files/validate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ files }),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to validate files')
  }
  return res.json()
}

export async function estimateRun(
  models: string[],
  prompts_file: string
): Promise<DryRunEstimateResponse> {
  const res = await fetch(`${API_BASE}/workflow/run/estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ models, prompts_file }),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to estimate run')
  }
  return res.json()
}

export async function estimateGrading(
  files: string[],
  grader_ids: string[],
  grader_model?: string,
  custom_prompt?: string | null
): Promise<GradingEstimateResponse> {
  const res = await fetch(`${API_BASE}/workflow/grade/estimate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ files, grader_ids, grader_model, custom_prompt }),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to estimate grading')
  }
  return res.json()
}

export async function startRun(
  models: string[],
  prompts_file: string,
  output_dir?: string
): Promise<JobStartResponse> {
  const res = await fetch(`${API_BASE}/workflow/run/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ models, prompts_file, output_dir }),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to start run')
  }
  return res.json()
}

export async function startGrading(
  files: string[],
  grader_ids: string[],
  grader_model?: string,
  custom_prompt?: string | null,
  output_dir?: string
): Promise<JobStartResponse> {
  const res = await fetch(`${API_BASE}/workflow/grade/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ files, grader_ids, grader_model, custom_prompt, output_dir }),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to start grading')
  }
  return res.json()
}

export async function getJobStatus(job_id: string): Promise<JobStatus> {
  const res = await fetch(`${API_BASE}/workflow/jobs/${encodeURIComponent(job_id)}`)
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to get job status')
  }
  return res.json()
}

export async function cancelJob(job_id: string): Promise<CancelResponse> {
  const res = await fetch(`${API_BASE}/workflow/jobs/${encodeURIComponent(job_id)}`, {
    method: 'DELETE',
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to cancel job')
  }
  return res.json()
}

export async function fetchOpenRouterModels(refresh: boolean = false): Promise<OpenRouterModelsResponse> {
  const params = refresh ? '?refresh=true' : ''
  const res = await fetch(`${API_BASE}/workflow/models${params}`)
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to fetch OpenRouter models')
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

// === Q1-Q4 Annotation API ===

export async function fetchQ1Q4Responses(params?: {
  model?: string
  limit?: number
  offset?: number
}): Promise<Q1Q4ResponsesResponse> {
  const searchParams = new URLSearchParams()
  if (params?.model) searchParams.set('model', params.model)
  if (params?.limit !== undefined) searchParams.set('limit', String(params.limit))
  if (params?.offset !== undefined) searchParams.set('offset', String(params.offset))
  const res = await fetch(`${API_BASE}/annotations/q1q4?${searchParams}`)
  return res.json()
}

export async function lookupQ1Q4Annotation(response_id: number, model: string): Promise<Q1Q4AnnotationLookupResponse> {
  const params = new URLSearchParams({ response_id: String(response_id), model })
  const res = await fetch(`${API_BASE}/annotations/q1q4/lookup?${params}`)
  return res.json()
}

export async function saveQ1Q4Annotation(data: Q1Q4AnnotationCreate): Promise<Q1Q4AnnotationSaveResponse> {
  const res = await fetch(`${API_BASE}/annotations/q1q4`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!res.ok) {
    const error = await res.json()
    throw new Error(error.detail || 'Failed to save Q1-Q4 annotation')
  }
  return res.json()
}

export async function fetchQ1Q4Models(): Promise<Q1Q4ModelsResponse> {
  const res = await fetch(`${API_BASE}/annotations/q1q4/models`)
  return res.json()
}
