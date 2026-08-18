import { useEffect, useState, useMemo, useCallback } from 'react'
import createPlotlyComponent from 'react-plotly.js/factory'
import Plotly from 'plotly.js-dist-min'
import { fetchGradesHeatmap, fetchModels, fetchTopics } from '../api'
import type { Model, HeatmapEntry } from '../types'
import { useAppStore } from '../store'
import { CollapsibleSection } from './CollapsibleSection'
import { ResponseModal } from './ResponseModal'

const Plot = createPlotlyComponent(Plotly)

interface QuestionDef {
  key: keyof HeatmapEntry
  label: string
  colorscale: Plotly.ColorScale
  zmin: number
  zmax: number
}

const QUESTIONS: QuestionDef[] = [
  { key: 'q1', label: 'Q1 Relativism (0/1)', colorscale: 'RdYlGn', zmin: 0, zmax: 1 },
  { key: 'q2', label: 'Q2 Preference (-1/0/1)', colorscale: 'RdBu', zmin: -1, zmax: 1 },
  { key: 'q3', label: 'Q3 Evidence (-1/0/1)', colorscale: 'RdBu', zmin: -1, zmax: 1 },
  { key: 'q4', label: 'Q4 Justification (1-5)', colorscale: 'YlOrRd', zmin: 1, zmax: 5 },
  { key: 'q4_1', label: 'Q4.1 Factual Depth (0/1)', colorscale: 'RdYlGn', zmin: 0, zmax: 1 },
  { key: 'q4_2', label: 'Q4.2 Specificity (0/1)', colorscale: 'RdYlGn', zmin: 0, zmax: 1 },
  { key: 'q4_3', label: 'Q4.3 Synthesis (0/1)', colorscale: 'RdYlGn', zmin: 0, zmax: 1 },
  { key: 'q4_4', label: 'Q4.4 Consistency (0/1)', colorscale: 'RdYlGn', zmin: 0, zmax: 1 },
]

export function GradeExplorer() {
  const [allData, setAllData] = useState<HeatmapEntry[]>([])
  const [models, setModels] = useState<Model[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const { selectedModels, setSelectedModels, toggleModel } = useAppStore()
  const [selectedTopics, setSelectedTopics] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [modalEntry, setModalEntry] = useState<HeatmapEntry | null>(null)

  useEffect(() => {
    Promise.all([fetchGradesHeatmap(), fetchModels(), fetchTopics()]).then(
      ([heatmap, modelsResp, topicsResp]) => {
        setAllData(heatmap.data)
        setModels(modelsResp.models)
        setTopics(topicsResp.topics)
        if (selectedModels.length === 0) {
          setSelectedModels(modelsResp.models.map((m) => m.name))
        }
        setLoading(false)
      }
    )
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const handleModelToggle = (name: string) => {
    toggleModel(name)
  }

  const handleSelectAllModels = () => {
    if (selectedModels.length === models.length) {
      setSelectedModels([])
    } else {
      setSelectedModels(models.map((m) => m.name))
    }
  }

  const handleTopicToggle = (topic: string) => {
    setSelectedTopics((prev) =>
      prev.includes(topic) ? prev.filter((t) => t !== topic) : [...prev, topic]
    )
  }

  const handleSelectAllTopics = () => {
    setSelectedTopics((prev) =>
      prev.length === topics.length ? [] : [...topics]
    )
  }

  const filtered = useMemo(() => {
    return allData.filter((d) => {
      if (selectedModels.length > 0 && !selectedModels.includes(d.model)) return false
      if (selectedTopics.length > 0 && !selectedTopics.includes(d.topic)) return false
      return true
    })
  }, [allData, selectedModels, selectedTopics])

  // Stable prompt ordering: unique UIDs in original order
  const promptUids = useMemo(() => {
    const seen = new Set<number>()
    const uids: number[] = []
    for (const d of filtered) {
      if (!seen.has(d.uid)) {
        seen.add(d.uid)
        uids.push(d.uid)
      }
    }
    return uids
  }, [filtered])

  // Short labels for x-axis
  const promptLabels = useMemo(() => {
    const labelMap = new Map<number, string>()
    for (const d of filtered) {
      if (!labelMap.has(d.uid)) {
        const short = d.question.length > 30 ? d.question.slice(0, 30) + '...' : d.question
        labelMap.set(d.uid, `${d.uid}: ${short}`)
      }
    }
    return promptUids.map((uid) => labelMap.get(uid) ?? String(uid))
  }, [filtered, promptUids])

  const modelNames = useMemo(() => {
    return [...new Set(filtered.map((d) => d.model))].sort()
  }, [filtered])

  // Build lookup for click handler
  const entryLookup = useMemo(() => {
    const lookup = new Map<string, HeatmapEntry>()
    for (const d of filtered) {
      lookup.set(`${d.model}::${d.uid}`, d)
    }
    return lookup
  }, [filtered])

  const buildHeatmapData = useCallback(
    (qDef: QuestionDef) => {
      const uidIndex = new Map(promptUids.map((uid, i) => [uid, i]))
      const modelIndex = new Map(modelNames.map((m, i) => [m, i]))

      const z: (number | null)[][] = modelNames.map(() =>
        new Array(promptUids.length).fill(null)
      )

      for (const d of filtered) {
        const mi = modelIndex.get(d.model)
        const pi = uidIndex.get(d.uid)
        if (mi !== undefined && pi !== undefined) {
          z[mi][pi] = d[qDef.key] as number | null
        }
      }

      const trace: Partial<Plotly.PlotData> = {
        z,
        x: promptLabels,
        y: modelNames,
        type: 'heatmap' as Plotly.PlotType,
        colorscale: qDef.colorscale,
        zmin: qDef.zmin,
        zmax: qDef.zmax,
        hoverongaps: false,
        hovertemplate:
          'Model: %{y}<br>Prompt: %{x}<br>Grade: %{z}<extra></extra>',
      }

      return [trace]
    },
    [filtered, promptUids, promptLabels, modelNames]
  )

  const handlePlotClick = useCallback(
    (event: Plotly.PlotMouseEvent) => {
      const point = event.points[0]
      if (!point) return
      const model = point.y as string
      const xLabel = point.x as string
      const uidMatch = xLabel?.match(/^(\d+):/)
      if (uidMatch) {
        const entry = entryLookup.get(`${model}::${Number(uidMatch[1])}`)
        if (entry) setModalEntry(entry)
      }
    },
    [entryLookup]
  )

  const heatmapLayout: Partial<Plotly.Layout> = {
    height: Math.max(300, modelNames.length * 30 + 150),
    margin: { l: 200, r: 40, t: 30, b: 120 },
    xaxis: {
      tickangle: -45,
      tickfont: { size: 9 },
    },
    yaxis: {
      tickfont: { size: 11 },
    },
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Grade Explorer</h2>

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
            {models.map((model) => (
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

      {loading ? (
        <div className="flex items-center justify-center h-96">
          <div className="text-gray-500">Loading grade data...</div>
        </div>
      ) : selectedModels.length === 0 ? (
        <div className="flex items-center justify-center h-48">
          <div className="text-gray-500">Select at least one model</div>
        </div>
      ) : (
        QUESTIONS.map((qDef) => (
          <CollapsibleSection
            key={qDef.key}
            id={`grade-explorer-${qDef.key}`}
            title={qDef.label}
          >
            <Plot
              data={buildHeatmapData(qDef) as Plotly.Data[]}
              layout={heatmapLayout}
              config={{ responsive: true }}
              style={{ width: '100%' }}
              onClick={handlePlotClick}
            />
          </CollapsibleSection>
        ))
      )}

      {modalEntry && (
        <ResponseModal entry={modalEntry} onClose={() => setModalEntry(null)} />
      )}
    </div>
  )
}
