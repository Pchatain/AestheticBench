import { useEffect, useState, useCallback } from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js-dist-min'
import { fetchModels, fetchTopics, fetchGradesSummary } from '../api'
import type { Model, GradesSummary } from '../types'
import { useAppStore } from '../store'
import { CollapsibleSection } from './CollapsibleSection'

const Plot = createPlotlyComponent(Plotly)

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

const RADAR_METRICS = [
  'Preference 1',
  'Preference 2',
  'Justification',
  'Q1 Relativism',
  'Q2 Preference',
  'Q3 Evidence',
  'Q4 Justification',
]

export function ModelComparison() {
  const [models, setModels] = useState<Model[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const { selectedModels, toggleModel, setSelectedModels } = useAppStore()
  const [selectedTopics, setSelectedTopics] = useState<string[]>([])
  const [summaries, setSummaries] = useState<GradesSummary[]>([])
  const [topicCounts, setTopicCounts] = useState<Record<string, number>>({})
  const [loading, setLoading] = useState(false)
  const [sortKey, setSortKey] = useState<'model' | 'preference1' | 'preference2' | 'justification' | 'q1' | 'q2' | 'q3' | 'q4' | 'count'>('model')
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
      case 'q1':
        return direction * (((a.q1_relativism_avg ?? -Infinity) as number) - ((b.q1_relativism_avg ?? -Infinity) as number))
      case 'q2':
        return direction * (((a.q2_preference_avg ?? -Infinity) as number) - ((b.q2_preference_avg ?? -Infinity) as number))
      case 'q3':
        return direction * (((a.q3_evidence_avg ?? -Infinity) as number) - ((b.q3_evidence_avg ?? -Infinity) as number))
      case 'q4':
        return direction * (((a.q4_justification_avg ?? -Infinity) as number) - ((b.q4_justification_avg ?? -Infinity) as number))
      case 'count':
        return direction * (a.count - b.count)
      case 'model':
      default:
        return direction * a.model.localeCompare(b.model)
    }
  })

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

  // Build Plotly scatterpolar traces
  function normalize(val: number | null | undefined, min: number, max: number): number {
    if (val === null || val === undefined) return 0
    return Math.round(((val - min) / (max - min)) * 100 * 100) / 100
  }

  const radarTraces: Partial<Plotly.PlotData>[] = summaries.map((summary) => {
    const r = [
      normalize(summary.preference1_avg, -1, 1),
      normalize(summary.preference2_avg, -1, 1),
      normalize(summary.justification_avg, 1, 5),
      normalize(summary.q1_relativism_avg, 0, 1),
      normalize(summary.q2_preference_avg, -1, 1),
      normalize(summary.q3_evidence_avg, -1, 1),
      normalize(summary.q4_justification_avg, 1, 5),
    ]
    const color = COLORS[models.findIndex((m) => m.name === summary.model) % COLORS.length]
    return {
      type: 'scatterpolar' as Plotly.PlotType,
      r: [...r, r[0]],
      theta: [...RADAR_METRICS, RADAR_METRICS[0]],
      fill: 'toself',
      fillcolor: color + '33',
      line: { color },
      name: summary.model,
    }
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
        <CollapsibleSection id="comparison-topic-counts" title="Prompt Counts by Topic">
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
        </CollapsibleSection>
      )}

      {/* Radar Chart */}
      <CollapsibleSection id="comparison-radar" title="Performance Radar Chart">
        {loading ? (
          <div className="flex items-center justify-center h-96">
            <div className="text-gray-500">Loading...</div>
          </div>
        ) : selectedModels.length === 0 ? (
          <div className="flex items-center justify-center h-96">
            <div className="text-gray-500">Select at least one model to see the comparison chart</div>
          </div>
        ) : (
          <Plot
            data={radarTraces as Plotly.Data[]}
            layout={{
              polar: {
                radialaxis: { visible: true, range: [0, 100] },
              },
              showlegend: true,
              height: 500,
              margin: { t: 40, b: 40 },
            }}
            config={{ responsive: true }}
            style={{ width: '100%' }}
          />
        )}
        <div className="mt-4 text-xs text-gray-500">
          <p>Score normalization:</p>
          <ul className="list-disc list-inside ml-2">
            <li>Preference 1 & 2: -1 to 1 mapped to 0-100%</li>
            <li>Justification: 1-5 mapped to 0-100%</li>
            <li>Q1 Relativism: 0-1 mapped to 0-100%</li>
            <li>Q2 Preference & Q3 Evidence: -1 to 1 mapped to 0-100%</li>
            <li>Q4 Justification Quality: 1-5 mapped to 0-100%</li>
          </ul>
        </div>
      </CollapsibleSection>

      {/* Summary Table */}
      {summaries.length > 0 && (
        <CollapsibleSection id="comparison-scores-table" title="Raw Scores Summary Table">
          <div className="overflow-x-auto">
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
                    onClick={() => handleSort('q1')}
                    className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                  >
                    Q1 Relativism {sortKey === 'q1' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th
                    onClick={() => handleSort('q2')}
                    className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                  >
                    Q2 Preference {sortKey === 'q2' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th
                    onClick={() => handleSort('q3')}
                    className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                  >
                    Q3 Evidence {sortKey === 'q3' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
                  </th>
                  <th
                    onClick={() => handleSort('q4')}
                    className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase cursor-pointer select-none"
                  >
                    Q4 Justification {sortKey === 'q4' ? (sortDir === 'asc' ? '▲' : '▼') : ''}
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
                    <td className="px-4 py-2 text-sm">
                      {summary.q1_relativism_avg !== null && summary.q1_relativism_avg !== undefined ? summary.q1_relativism_avg.toFixed(3) : 'N/A'}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      {summary.q2_preference_avg !== null && summary.q2_preference_avg !== undefined ? summary.q2_preference_avg.toFixed(3) : 'N/A'}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      {summary.q3_evidence_avg !== null && summary.q3_evidence_avg !== undefined ? summary.q3_evidence_avg.toFixed(3) : 'N/A'}
                    </td>
                    <td className="px-4 py-2 text-sm">
                      {summary.q4_justification_avg !== null && summary.q4_justification_avg !== undefined ? summary.q4_justification_avg.toFixed(2) : 'N/A'}
                    </td>
                    <td className="px-4 py-2 text-sm">{summary.count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </CollapsibleSection>
      )}
    </div>
  )
}
