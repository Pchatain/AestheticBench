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

// Justification Experiment types
export interface ExperimentPrompt {
  uid: number
  question: string
  topic: string
}

export interface ExperimentPromptsResponse {
  prompts: ExperimentPrompt[]
}

export interface QuestionConfig {
  id: string  // q1, q2, q3, q4
  prompt: string
  enabled: boolean
}

export interface DefaultQuestion {
  name: string
  prompt: string
  output_type: string
}

export interface DefaultQuestionsResponse {
  questions: Record<string, DefaultQuestion>
}

export interface MultiQuestionExperimentRequest {
  response_models: string[]
  grader_model: string
  questions: QuestionConfig[]
  prompt_uids: number[]
}

export interface SinglePairRequest {
  model_name: string
  uid: number
  original_question: string
  model_response: string
  grader_model: string
  questions: QuestionConfig[]
}

export interface PromptResult {
  uid: number
  model: string
  question: string
  response: string
  q1_score: string | null
  q1_response: string
  q1_error: string | null
  q2_score: string | null
  q2_response: string
  q2_error: string | null
  q3_score: string | null
  q3_response: string
  q3_error: string | null
  q4_score: string | null
  q4_response: string
  q4_error: string | null
}

export interface MultiQuestionExperimentResponse {
  results: PromptResult[]
  experiment_id: string
  questions_run: string[]
}

export interface SaveMultiExperimentRequest {
  experiment_id: string
  results: PromptResult[]
  questions: QuestionConfig[]
  grader_model: string
}

export interface SaveExperimentResponse {
  filepath: string
  saved: boolean
}
