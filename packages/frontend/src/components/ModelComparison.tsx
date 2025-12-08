import { useEffect, useState, useCallback } from 'react'
import {
  RadarChart,
  PolarGrid,
  PolarAngleAxis,
  PolarRadiusAxis,
  Radar,
  Legend,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'
import { fetchModels, fetchTopics, fetchGradesSummary } from '../api'
import type { Model, GradesSummary } from '../types'

const COLORS = [
  '#8884d8',
  '#82ca9d',
  '#ffc658',
  '#ff7300',
  '#00C49F',
  '#FFBB28',
  '#FF8042',
  '#0088FE',
  '#00C49F',
  '#FFBB28',
  '#FF8042',
  '#a4de6c',
]

interface ChartDataPoint {
  metric: string
  fullMark: number
  [key: string]: string | number
}

export function ModelComparison() {
  const [models, setModels] = useState<Model[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [selectedTopics, setSelectedTopics] = useState<string[]>([])
  const [summaries, setSummaries] = useState<GradesSummary[]>([])
  const [topicCounts, setTopicCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(false)
  const [sortKey, setSortKey] = useState<'model' | 'preference1' | 'preference2' | 'justification' | 'count'>('model')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('asc')

  useEffect(() => {
    fetchModels().then((data) => setModels(data.models))
    fetchTopics().then((data) => setTopics(data.topics))
  }, [])

  const loadSummaries = useCallback(async () => {
    if (selectedModels.length === 0) {
      setSummaries([])
      setTopicCounts({})
      return
    }
    setLoading(true)
    const data = await fetchGradesSummary({
      models: selectedModels,
      topics: selectedTopics.length > 0 ? selectedTopics : undefined,
    })
    setSummaries(data.summaries)
    setTopicCounts(data.topic_counts)
    setLoading(false)
  }, [selectedModels, selectedTopics])

  useEffect(() => {
    loadSummaries()
  }, [loadSummaries])

  const handleSort = (key: typeof sortKey) => {
    if (sortKey === key) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortKey(key)
      setSortDir('desc')
    }
  }

  const sortedSummaries = [...summaries].sort((a, b) => {
    const direction = sortDir === 'asc' ? 1 : -1
    switch (sortKey) {
      case 'preference1':
        return direction * (((a.preference1_avg ?? -Infinity) as number) - ((b.preference1_avg ?? -Infinity) as number))
      case 'preference2':
        return direction * (((a.preference2_avg ?? -Infinity) as number) - ((b.preference2_avg ?? -Infinity) as number))
      case 'justification':
        return direction * (((a.justification_avg ?? -Infinity) as number) - ((b.justification_avg ?? -Infinity) as number))
      case 'count':
        return direction * (a.count - b.count)
      case 'model':
      default:
        return direction * a.model.localeCompare(b.model)
    }
  })

  const handleModelToggle = (modelName: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelName)
        ? prev.filter((m) => m !== modelName)
        : [...prev, modelName]
    )
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

  // Transform summaries to chart data format
  // Normalize scores to 0-100 scale for radar chart
  const chartData: ChartDataPoint[] = [
    { metric: 'Preference 1', fullMark: 100 },
    { metric: 'Preference 2', fullMark: 100 },
    { metric: 'Justification', fullMark: 100 },
  ]

  summaries.forEach((summary) => {
    // Preference 1: -1 to 1 -> 0 to 100
    const pref1Normalized = summary.preference1_avg !== null
      ? ((summary.preference1_avg + 1) / 2) * 100
      : 0
    // Preference 2: -1 to 1 -> 0 to 100
    const pref2Normalized = summary.preference2_avg !== null
      ? ((summary.preference2_avg + 1) / 2) * 100
      : 0
    // Justification: 1 to 5 -> 0 to 100
    const justNormalized = summary.justification_avg !== null
      ? ((summary.justification_avg - 1) / 4) * 100
      : 0

    chartData[0][summary.model] = Math.round(pref1Normalized * 100) / 100
    chartData[1][summary.model] = Math.round(pref2Normalized * 100) / 100
    chartData[2][summary.model] = Math.round(justNormalized * 100) / 100
  })

  const displayedTopicCounts = selectedTopics.length > 0
    ? Object.entries(topicCounts).filter(([topic]) => selectedTopics.includes(topic))
    : Object.entries(topicCounts)

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Model Comparison</h2>

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
                  style={{ backgroundColor: selectedModels.includes(model.name) ? COLORS[idx % COLORS.length] : '#ccc' }}
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

      {/* Topic Counts */}
      {displayedTopicCounts.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Prompt Counts by Topic</h3>
          <div className="flex flex-wrap gap-2">
            {displayedTopicCounts.map(([topic, count]) => (
              <span
                key={topic}
                className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm"
              >
                {topic}: {count}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Radar Chart */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold text-gray-700 mb-4">Performance Comparison</h3>
        {loading ? (
          <div className="flex items-center justify-center h-96">
            <div className="text-gray-500">Loading...</div>
          </div>
        ) : selectedModels.length === 0 ? (
          <div className="flex items-center justify-center h-96">
            <div className="text-gray-500">Select at least one model to see the comparison chart</div>
          </div>
        ) : (
          <div className="h-96">
            <ResponsiveContainer width="100%" height="100%">
              <RadarChart data={chartData}>
                <PolarGrid />
                <PolarAngleAxis dataKey="metric" />
                <PolarRadiusAxis angle={30} domain={[0, 100]} />
                {summaries.map((summary) => (
                  <Radar
                    key={summary.model}
                    name={summary.model}
                    dataKey={summary.model}
                    stroke={COLORS[models.findIndex(m => m.name === summary.model) % COLORS.length]}
                    fill={COLORS[models.findIndex(m => m.name === summary.model) % COLORS.length]}
                    fillOpacity={0.2}
                  />
                ))}
                <Legend />
                <Tooltip
                  formatter={(value: number, name: string) => [
                    `${value.toFixed(2)}%`,
                    name
                  ]}
                />
              </RadarChart>
            </ResponsiveContainer>
          </div>
        )}
        <div className="mt-4 text-xs text-gray-500">
          <p>Score normalization:</p>
          <ul className="list-disc list-inside ml-2">
            <li>Preference 1 & 2: -1 to 1 mapped to 0-100%</li>
            <li>Justification: 1-5 mapped to 0-100%</li>
          </ul>
        </div>
      </div>

      {/* Summary Table */}
      {summaries.length > 0 && (
        <div className="bg-white rounded-lg shadow p-4 overflow-x-auto">
          <h3 className="font-semibold text-gray-700 mb-4">Raw Scores</h3>
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th
                  onClick={() => handleSort('model')}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                >
                  Model {sortKey === 'model' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleSort('preference1')}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                >
                  Preference 1 {sortKey === 'preference1' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleSort('preference2')}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                >
                  Preference 2 {sortKey === 'preference2' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleSort('justification')}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                >
                  Justification {sortKey === 'justification' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </th>
                <th
                  onClick={() => handleSort('count')}
                  className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                >
                  Samples {sortKey === 'count' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {sortedSummaries.map((summary) => (
                <tr key={summary.model} className="hover:bg-gray-50">
                  <td className="px-4 py-2 text-sm font-medium">{summary.model}</td>
                  <td className="px-4 py-2 text-sm">
                    {summary.preference1_avg !== null ? summary.preference1_avg.toFixed(3) : 'N/A'}
                  </td>
                  <td className="px-4 py-2 text-sm">
                    {summary.preference2_avg !== null ? summary.preference2_avg.toFixed(3) : 'N/A'}
                  </td>
                  <td className="px-4 py-2 text-sm">
                    {summary.justification_avg !== null ? summary.justification_avg.toFixed(2) : 'N/A'}
                  </td>
                  <td className="px-4 py-2 text-sm">{summary.count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
