import { useState, useEffect, useMemo } from 'react'
import { fetchOpenRouterModels } from '../api'
import type { OpenRouterModel } from '../types'

interface ModelPickerProps {
  selectedModels: string[]
  onModelsChange: (models: string[]) => void
}

export function ModelPicker({ selectedModels, onModelsChange }: ModelPickerProps) {
  const [models, setModels] = useState<OpenRouterModel[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [search, setSearch] = useState('')
  const [cached, setCached] = useState(false)
  const [cacheAge, setCacheAge] = useState<number | null>(null)

  useEffect(() => {
    fetchOpenRouterModels()
      .then((res) => {
        setModels(res.models)
        setCached(res.cached)
        setCacheAge(res.cache_age_seconds ?? null)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message)
        setLoading(false)
      })
  }, [])

  const handleRefresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetchOpenRouterModels(true)
      setModels(res.models)
      setCached(res.cached)
      setCacheAge(res.cache_age_seconds ?? null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
    setLoading(false)
  }

  const filteredModels = useMemo(() => {
    if (!search.trim()) return models
    const lower = search.toLowerCase()
    return models.filter(
      (m) =>
        m.id.toLowerCase().includes(lower) ||
        m.name.toLowerCase().includes(lower) ||
        (m.top_provider && m.top_provider.toLowerCase().includes(lower))
    )
  }, [models, search])

  // Group by provider
  const groupedModels = useMemo(() => {
    const groups: Record<string, OpenRouterModel[]> = {}
    for (const model of filteredModels) {
      const provider = model.top_provider || 'Other'
      if (!groups[provider]) groups[provider] = []
      groups[provider].push(model)
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b))
  }, [filteredModels])

  const addModel = (modelId: string) => {
    if (!selectedModels.includes(modelId)) {
      onModelsChange([...selectedModels, modelId])
    }
  }

  const removeModel = (modelId: string) => {
    onModelsChange(selectedModels.filter((m) => m !== modelId))
  }

  const getModelInfo = (modelId: string) => {
    return models.find((m) => m.id === modelId)
  }

  const formatPrice = (price: number | null | undefined) => {
    if (price == null) return '-'
    if (price < 0.01) return `$${price.toFixed(4)}`
    return `$${price.toFixed(2)}`
  }

  if (loading && models.length === 0) {
    return (
      <div className="border rounded p-4 text-center text-gray-500">
        Loading models from OpenRouter...
      </div>
    )
  }

  if (error && models.length === 0) {
    return (
      <div className="border rounded p-4">
        <div className="text-red-600 mb-2">Error: {error}</div>
        <button
          onClick={handleRefresh}
          className="text-sm text-blue-600 hover:underline"
        >
          Retry
        </button>
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Selected Models */}
      <div>
        <label className="block text-sm font-medium mb-2">
          Selected Models ({selectedModels.length})
        </label>
        {selectedModels.length === 0 ? (
          <div className="border rounded p-3 text-gray-500 text-sm">
            No models selected. Search and click models below to add them.
          </div>
        ) : (
          <div className="border rounded p-2 space-y-1 max-h-40 overflow-y-auto">
            {selectedModels.map((modelId) => {
              const info = getModelInfo(modelId)
              return (
                <div
                  key={modelId}
                  className="flex items-center justify-between bg-blue-50 rounded px-2 py-1"
                >
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-medium truncate">{modelId}</div>
                    {info && (
                      <div className="text-xs text-gray-500">
                        {formatPrice(info.pricing_prompt)}/M in, {formatPrice(info.pricing_completion)}/M out
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => removeModel(modelId)}
                    className="ml-2 text-red-500 hover:text-red-700 text-lg leading-none"
                    title="Remove"
                  >
                    &times;
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </div>

      {/* Search and Model List */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium">
            Available Models ({models.length})
          </label>
          <div className="flex items-center gap-2 text-xs text-gray-500">
            {cached && cacheAge != null && (
              <span>Cached {Math.floor(cacheAge / 60)}m ago</span>
            )}
            <button
              onClick={handleRefresh}
              disabled={loading}
              className="text-blue-600 hover:underline disabled:opacity-50"
            >
              {loading ? 'Refreshing...' : 'Refresh'}
            </button>
          </div>
        </div>

        <input
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search models (e.g., 'gpt-4', 'claude', 'anthropic')..."
          className="w-full p-2 border rounded mb-2"
        />

        <div className="border rounded max-h-64 overflow-y-auto">
          {filteredModels.length === 0 ? (
            <div className="p-4 text-center text-gray-500 text-sm">
              No models match your search
            </div>
          ) : (
            groupedModels.map(([provider, providerModels]) => (
              <div key={provider}>
                <div className="sticky top-0 bg-gray-100 px-3 py-1 text-xs font-semibold text-gray-600 border-b">
                  {provider} ({providerModels.length})
                </div>
                {providerModels.map((model) => {
                  const isSelected = selectedModels.includes(model.id)
                  return (
                    <button
                      key={model.id}
                      onClick={() => addModel(model.id)}
                      disabled={isSelected}
                      className={`w-full text-left px-3 py-2 border-b last:border-b-0 hover:bg-gray-50 disabled:opacity-50 disabled:bg-green-50 ${
                        isSelected ? 'bg-green-50' : ''
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="text-sm font-medium truncate">
                            {model.name}
                          </div>
                          <div className="text-xs text-gray-500 truncate">
                            {model.id}
                          </div>
                        </div>
                        <div className="text-xs text-gray-400 text-right ml-2 whitespace-nowrap">
                          <div>{formatPrice(model.pricing_prompt)}/M</div>
                          {model.context_length && (
                            <div>{(model.context_length / 1000).toFixed(0)}k ctx</div>
                          )}
                        </div>
                      </div>
                    </button>
                  )
                })}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}
