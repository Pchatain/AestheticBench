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
