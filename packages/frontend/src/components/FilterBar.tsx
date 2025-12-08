import type { Model } from '../types'

interface FilterBarProps {
  models: Model[]
  topics: string[]
  selectedModel: string
  selectedTopic: string
  searchQuery: string
  onModelChange: (model: string) => void
  onTopicChange: (topic: string) => void
  onSearchChange: (search: string) => void
}

export function FilterBar({
  models,
  topics,
  selectedModel,
  selectedTopic,
  searchQuery,
  onModelChange,
  onTopicChange,
  onSearchChange,
}: FilterBarProps) {
  return (
    <div className="flex flex-wrap gap-4 p-4 bg-white rounded-lg shadow mb-4">
      <div className="flex flex-col">
        <label htmlFor="model-select" className="text-sm font-medium text-gray-700 mb-1">
          Model
        </label>
        <select
          id="model-select"
          value={selectedModel}
          onChange={(e) => onModelChange(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 bg-white min-w-[200px]"
        >
          <option value="">All Models</option>
          {models.map((model) => (
            <option key={model.filename} value={model.name}>
              {model.name}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col">
        <label htmlFor="topic-select" className="text-sm font-medium text-gray-700 mb-1">
          Topic
        </label>
        <select
          id="topic-select"
          value={selectedTopic}
          onChange={(e) => onTopicChange(e.target.value)}
          className="border border-gray-300 rounded-md px-3 py-2 bg-white min-w-[200px]"
        >
          <option value="">All Topics</option>
          {topics.map((topic) => (
            <option key={topic} value={topic}>
              {topic}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-col flex-1 min-w-[250px]">
        <label htmlFor="search-input" className="text-sm font-medium text-gray-700 mb-1">
          Search Questions
        </label>
        <input
          id="search-input"
          type="text"
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          placeholder="Type to search..."
          className="border border-gray-300 rounded-md px-3 py-2"
        />
      </div>
    </div>
  )
}
