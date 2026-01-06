import { useEffect, useState, useCallback } from 'react'
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'
import { fetchModels, fetchTopics, fetchResults } from '../api'
import type { Model, Result } from '../types'
import { useAppStore } from '../store'

const COLORS = [
  '#8884d8',
  '#82ca9d',
  '#ffc658',
  '#ff7300',
  '#00C49F',
  '#FFBB28',
  '#FF8042',
  '#0088FE',
  '#a4de6c',
]

interface HistogramDataPoint {
  category: string
  [key: string]: string | number
}

export function Analytics() {
  const [models, setModels] = useState<Model[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const { selectedModels, toggleModel, setSelectedModels } = useAppStore()
  const [selectedTopics, setSelectedTopics] = useState<string[]>([])
  const [results, setResults] = useState<Result[]>([])
  const [loading, setLoading] = useState(false)
  const [binSize, setBinSize] = useState<number>(0.1)

  useEffect(() => {
    fetchModels().then((data) => setModels(data.models))
    fetchTopics().then((data) => setTopics(data.topics))
  }, [])

  const loadResults = useCallback(async () => {
    if (selectedModels.length === 0) {
      setResults([])
      return
    }
    setLoading(true)
    const data = await fetchResults({
      model: undefined, // Fetch all, filter client-side
      topic: selectedTopics.length > 0 ? selectedTopics[0] : undefined,
    })
    setResults(data.results)
    setLoading(false)
  }, [selectedModels, selectedTopics])

  useEffect(() => {
    loadResults()
  }, [loadResults])

  const handleModelToggle = (modelName: string) => {
    toggleModel(modelName)
  }

  const handleTopicToggle = (topic: string) => {
    setSelectedTopics((prev) =>
      prev.includes(topic)
        ? prev.filter((t) => t !== topic)
        : [...prev, topic]
    )
  }

  const handleSelectAllModels = () => {
    if (selectedModels.length === models.length) {
      setSelectedModels([])
    } else {
      setSelectedModels(models.map((m) => m.name))
    }
  }

  const handleSelectAllTopics = () => {
    if (selectedTopics.length === topics.length) {
      setSelectedTopics([])
    } else {
      setSelectedTopics([...topics])
    }
  }

  // Build discrete histogram for categorical data
  function buildDiscreteHistogram(
    scoreField: string,
    categories: number[]
  ): HistogramDataPoint[] {
    const filteredResults = results.filter((r) => {
      if (selectedModels.length > 0 && !selectedModels.includes(String(r.model))) {
        return false
      }
      if (selectedTopics.length > 0 && !selectedTopics.includes(String(r.Topic))) {
        return false
      }
      return true
    })

    const data: HistogramDataPoint[] = categories.map((cat) => ({
      category: String(cat),
    }))

    selectedModels.forEach((modelName) => {
      const modelResults = filteredResults.filter((r) => r.model === modelName)

      categories.forEach((cat, idx) => {
        const count = modelResults.filter((r) => {
          const score = r[scoreField]
          if (!score || String(score).startsWith('ERROR')) return false
          return Number(score) === cat
        }).length

        data[idx][modelName] = count
      })
    })

    return data
  }

  // Build continuous histogram with binning
  function buildContinuousHistogram(): HistogramDataPoint[] {
    const filteredResults = results.filter((r) => {
      if (selectedModels.length > 0 && !selectedModels.includes(String(r.model))) {
        return false
      }
      if (selectedTopics.length > 0 && !selectedTopics.includes(String(r.Topic))) {
        return false
      }
      return true
    })

    // Create bins from -1 to 1
    const bins: { min: number; max: number; label: string }[] = []
    for (let start = -1; start < 1; start += binSize) {
      const end = Math.min(start + binSize, 1)
      bins.push({
        min: start,
        max: end,
        label: `[${start.toFixed(2)}, ${end.toFixed(2)})`,
      })
    }

    const data: HistogramDataPoint[] = bins.map((bin) => ({
      category: bin.label,
    }))

    selectedModels.forEach((modelName) => {
      const modelResults = filteredResults.filter((r) => r.model === modelName)

      bins.forEach((bin, idx) => {
        const count = modelResults.filter((r) => {
          const score = r['Preference_2_Score']
          if (!score || String(score).startsWith('ERROR')) return false
          const val = Number(score)
          return val >= bin.min && (val < bin.max || (bin.max === 1 && val === 1))
        }).length

        data[idx][modelName] = count
      })
    })

    return data
  }

  const pref1Data = buildDiscreteHistogram('Preference_1_Score', [-1, 0, 1])
  const pref2Data = buildContinuousHistogram()
  const justificationData = buildDiscreteHistogram('Justification_Score', [1, 2, 3, 4, 5])
  const relativismData = buildDiscreteHistogram('Relativism_Score', [0, 1])
  const whimsicalData = buildDiscreteHistogram('Whimsical_Score', [1, 2, 3, 4, 5])
  const factualDepthData = buildDiscreteHistogram('Factual_Depth_Score', [1, 2, 3, 4, 5])

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Model Performance Analytics</h2>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Model Selection */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-700">Select Models</h3>
            <button
              onClick={handleSelectAllModels}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {selectedModels.length === models.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>
          <div className="max-h-48 overflow-y-auto space-y-2">
            {models.map((model, idx) => (
              <label
                key={model.filename}
                className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded"
              >
                <input
                  type="checkbox"
                  checked={selectedModels.includes(model.name)}
                  onChange={() => handleModelToggle(model.name)}
                  className="rounded border-gray-300"
                />
                <span
                  className="w-3 h-3 rounded-full"
                  style={{
                    backgroundColor: selectedModels.includes(model.name)
                      ? COLORS[idx % COLORS.length]
                      : '#ccc',
                  }}
                />
                <span className="text-sm">{model.name}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Topic Selection */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-700">Filter by Topics</h3>
            <button
              onClick={handleSelectAllTopics}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {selectedTopics.length === topics.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>
          <p className="text-xs text-gray-500 mb-2">Leave empty to include all topics</p>
          <div className="max-h-48 overflow-y-auto space-y-2">
            {topics.map((topic) => (
              <label
                key={topic}
                className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded"
              >
                <input
                  type="checkbox"
                  checked={selectedTopics.includes(topic)}
                  onChange={() => handleTopicToggle(topic)}
                  className="rounded border-gray-300"
                />
                <span className="text-sm">{topic}</span>
              </label>
            ))}
          </div>
        </div>
      </div>

      {/* Bin Size Slider */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold text-gray-700 mb-3">
          Preference 2 Bin Size: {binSize.toFixed(2)}
        </h3>
        <input
          type="range"
          min="0.05"
          max="0.5"
          step="0.05"
          value={binSize}
          onChange={(e) => setBinSize(Number(e.target.value))}
          className="w-full"
        />
        <div className="flex justify-between text-xs text-gray-500 mt-1">
          <span>0.05</span>
          <span>0.1</span>
          <span>0.2</span>
          <span>0.5</span>
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-96">
          <div className="text-gray-500">Loading...</div>
        </div>
      ) : selectedModels.length === 0 ? (
        <div className="flex items-center justify-center h-96">
          <div className="text-gray-500">Select at least one model to see analytics</div>
        </div>
      ) : (
        <>
          {/* Preference 1 Histogram */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-semibold text-gray-700 mb-4">Preference 1 Distribution</h3>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pref1Data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" label={{ value: 'Score', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  {selectedModels.map((modelName) => (
                    <Bar
                      key={modelName}
                      dataKey={modelName}
                      fill={COLORS[models.findIndex((m) => m.name === modelName) % COLORS.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Preference 2 Histogram */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-semibold text-gray-700 mb-4">Preference 2 Distribution</h3>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={pref2Data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="category"
                    angle={-45}
                    textAnchor="end"
                    height={100}
                    label={{ value: 'Score Range', position: 'insideBottom', offset: -5 }}
                  />
                  <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  {selectedModels.map((modelName) => (
                    <Bar
                      key={modelName}
                      dataKey={modelName}
                      fill={COLORS[models.findIndex((m) => m.name === modelName) % COLORS.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Justification Histogram */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-semibold text-gray-700 mb-4">Justification Distribution</h3>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={justificationData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" label={{ value: 'Score', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  {selectedModels.map((modelName) => (
                    <Bar
                      key={modelName}
                      dataKey={modelName}
                      fill={COLORS[models.findIndex((m) => m.name === modelName) % COLORS.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Relativism Histogram */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-semibold text-gray-700 mb-4">Relativism Distribution (0 = rejects premise, 1 = engages)</h3>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={relativismData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" label={{ value: 'Score', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  {selectedModels.map((modelName) => (
                    <Bar
                      key={modelName}
                      dataKey={modelName}
                      fill={COLORS[models.findIndex((m) => m.name === modelName) % COLORS.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Whimsical Histogram */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-semibold text-gray-700 mb-4">Whimsical Reasoning Distribution (1 = whimsical, 5 = committed)</h3>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={whimsicalData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" label={{ value: 'Score', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  {selectedModels.map((modelName) => (
                    <Bar
                      key={modelName}
                      dataKey={modelName}
                      fill={COLORS[models.findIndex((m) => m.name === modelName) % COLORS.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          {/* Factual Depth Histogram */}
          <div className="bg-white rounded-lg shadow p-4">
            <h3 className="font-semibold text-gray-700 mb-4">Factual Depth Distribution (1 = none, 5 = expert)</h3>
            <div className="h-96">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={factualDepthData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="category" label={{ value: 'Score', position: 'insideBottom', offset: -5 }} />
                  <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                  <Tooltip />
                  <Legend />
                  {selectedModels.map((modelName) => (
                    <Bar
                      key={modelName}
                      dataKey={modelName}
                      fill={COLORS[models.findIndex((m) => m.name === modelName) % COLORS.length]}
                    />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
