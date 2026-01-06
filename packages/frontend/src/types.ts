export interface Model {
  name: string
  filename: string
}

// Dynamic result with arbitrary columns from graded files
export type Result = Record<string, string | number>

export interface ResultsResponse {
  results: Result[]
  total: number
  headers: string[]
}

export interface ModelsResponse {
  models: Model[]
}

export interface TopicsResponse {
  topics: string[]
}

export interface HeadersResponse {
  headers: string[]
}

export interface GradesSummary {
  model: string
  preference1_avg: number | null
  preference2_avg: number | null
  justification_avg: number | null
  count: number
}

export interface GradesSummaryResponse {
  summaries: GradesSummary[]
  topic_counts: Record<string, number>
}

export interface PlaygroundRequest {
  prompt: string
  model: string
}

export interface PlaygroundResponse {
  response: string
  model: string
}

export interface Annotation {
  id: string
  result_uid: number
  model: string
  notes: string
  preference_reasoning: string
  preference_score: number | null
  justification_reasoning: string
  justification_score: number | null
  created_at: string
  updated_at: string
}

export interface AnnotationCreate {
  result_uid: number
  model: string
  notes: string
  preference_reasoning: string
  preference_score: number | null
  justification_reasoning: string
  justification_score: number | null
}

export interface AnnotationsResponse {
  annotations: Annotation[]
  total: number
}

export interface AnnotationLookupResponse {
  annotation: Annotation | null
  found: boolean
}

export interface AnnotationSaveResponse {
  annotation: Annotation
  created: boolean
}

export interface GraderPrompt {
  id: string
  title: string
  prompt: string
}

export interface GraderPromptsResponse {
  prompts: GraderPrompt[]
}

// === Workflow Types ===

export interface VersionInfo {
  name: string
  response_count: number
  grade_count: number
}

export interface VersionsResponse {
  versions: VersionInfo[]
}

export interface ResponseFileInfo {
  path: string
  filename: string
  model: string
  date: string
  size: string
  response_count: number
}

export interface FilesResponse {
  files: ResponseFileInfo[]
}

export interface PromptsFileInfo {
  path: string
  filename: string
  prompt_count: number
}

export interface PromptsFilesResponse {
  files: PromptsFileInfo[]
}

export interface GraderInfo {
  id: string
  name: string
  description: string
  score_range: string
  dependencies: string[]
}

export interface GradersResponse {
  graders: GraderInfo[]
}

export interface GraderValidationRequest {
  grader_ids: string[]
  custom_prompt?: string | null
}

export interface GraderValidationResponse {
  valid: boolean
  grader_ids: string[]
  errors: string[]
  warnings: string[]
}

export interface FileValidationRequest {
  files: string[]
}

export interface FileValidationResponse {
  valid: boolean
  valid_files: string[]
  errors: string[]
}

export interface RunEstimateRequest {
  models: string[]
  prompts_file: string
}

export interface ModelEstimate {
  model: string
  available: boolean
  input_cost_per_m?: number | null
  output_cost_per_m?: number | null
  estimated_min_cost?: number | null
  estimated_max_cost?: number | null
  error?: string | null
}

export interface DryRunEstimateResponse {
  prompts_count: number
  total_input_tokens: number
  models: ModelEstimate[]
  valid_models: string[]
  invalid_models: string[]
  total_min_cost: number
  total_max_cost: number
}

export interface GradeEstimateRequest {
  files: string[]
  grader_ids: string[]
  grader_model?: string
  custom_prompt?: string | null
}

export interface FileEstimate {
  path: string
  filename: string
  response_count: number
}

export interface GradingEstimateResponse {
  files: FileEstimate[]
  total_responses: number
  graders: string[]
  custom_prompt_included: boolean
  total_grading_calls: number
  estimated_input_tokens: number
  estimated_output_tokens: number
  grader_model: string
}

export interface JobStartResponse {
  job_id: string
  status: string
}

export interface JobStatus {
  job_id: string
  status: 'pending' | 'running' | 'completed' | 'failed'
  progress: number
  current_step?: string | null
  total_steps?: number | null
  current_step_index?: number | null
  result?: Record<string, unknown> | null
  error?: string | null
}

export interface CancelResponse {
  job_id: string
  cancelled: boolean
  message: string
}

// === Models Types ===

export interface OpenRouterModel {
  id: string
  name: string
  description?: string | null
  context_length?: number | null
  pricing_prompt?: number | null  // $ per 1M tokens
  pricing_completion?: number | null  // $ per 1M tokens
  top_provider?: string | null
}

export interface OpenRouterModelsResponse {
  models: OpenRouterModel[]
  cached: boolean
  cache_age_seconds?: number | null
}
