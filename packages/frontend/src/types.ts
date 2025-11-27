export interface Model {
  name: string
  filename: string
}

export interface Result {
  uid: number
  model: string
  topic: string
  question: string
  response: string
  timestamp: string
}

export interface ResultsResponse {
  results: Result[]
  total: number
}

export interface ModelsResponse {
  models: Model[]
}

export interface TopicsResponse {
  topics: string[]
}
