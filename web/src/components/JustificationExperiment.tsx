import { useEffect, useState, useCallback, useRef } from 'react'
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
import {
  fetchModels,
  fetchExperimentPrompts,
  fetchDefaultQuestions,
  fetchResults,
  gradeSinglePair,
  saveMultiExperimentResults,
} from '../api'
import type { Model, ExperimentPrompt, PromptResult, QuestionConfig } from '../types'
import { CollapsibleSection } from './CollapsibleSection'

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

const AVAILABLE_GRADER_MODELS = [
  'anthropic/claude-sonnet-4.5',
  'openai/gpt-5',
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
  'google/gemini-2.5-pro',
  'deepseek/deepseek-chat-v3.1',
  'meta-llama/llama-3.1-405b-instruct',
]

// Question metadata for display
const QUESTION_META: Record<string, { name: string; categories: string[] }> = {
  q1: { name: 'Q1: Relativism', categories: ['Yes', 'No'] },
  q2: { name: 'Q2: Preference', categories: ['-1', '0', '1'] },
  q3: { name: 'Q3: Evidence', categories: ['-1', '0', '1'] },
  q4: { name: 'Q4: Justification Quality', categories: ['1', '2', '3', '4', '5'] },
}

interface HistogramDataPoint {
  category: string
  [key: string]: string | number
}

interface PairToGrade {
  uid: number
  model: string
  question: string
  response: string
}

export function JustificationExperiment() {
  // Models and prompts data
  const [models, setModels] = useState<Model[]>([])
  const [prompts, setPrompts] = useState<ExperimentPrompt[]>([])
  
  // Selection state
  const [selectedResponseModels, setSelectedResponseModels] = useState<string[]>([])
  const [selectedGraderModel, setSelectedGraderModel] = useState(AVAILABLE_GRADER_MODELS[0])
  const [selectedPromptUids, setSelectedPromptUids] = useState<number[]>([])
  
  // Question configurations
  const [questions, setQuestions] = useState<QuestionConfig[]>([
    { id: 'q1', prompt: '', enabled: true },
    { id: 'q2', prompt: '', enabled: true },
    { id: 'q3', prompt: '', enabled: true },
    { id: 'q4', prompt: '', enabled: true },
  ])
  
  // Results state
  const [results, setResults] = useState<PromptResult[]>([])
  const [experimentId, setExperimentId] = useState('')
  
  // Progress state
  const [loading, setLoading] = useState(false)
  const [progress, setProgress] = useState({ current: 0, total: 0 })
  const [currentPair, setCurrentPair] = useState<string>('')
  const abortRef = useRef(false)
  
  // UI state
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')

  // Load models and default questions on mount
  useEffect(() => {
    fetchModels().then((data) => setModels(data.models))
    fetchDefaultQuestions().then((data) => {
      setQuestions([
        { id: 'q1', prompt: data.questions.q1?.prompt || '', enabled: true },
        { id: 'q2', prompt: data.questions.q2?.prompt || '', enabled: true },
        { id: 'q3', prompt: data.questions.q3?.prompt || '', enabled: true },
        { id: 'q4', prompt: data.questions.q4?.prompt || '', enabled: true },
      ])
    })
  }, [])

  // Load prompts when response models change
  const loadPrompts = useCallback(async () => {
    if (selectedResponseModels.length === 0) {
      setPrompts([])
      return
    }
    const data = await fetchExperimentPrompts(selectedResponseModels)
    setPrompts(data.prompts)
  }, [selectedResponseModels])

  useEffect(() => {
    loadPrompts()
  }, [loadPrompts])

  // Model selection handlers
  const handleResponseModelToggle = (modelName: string) => {
    setSelectedResponseModels((prev) =>
      prev.includes(modelName)
        ? prev.filter((m) => m !== modelName)
        : [...prev, modelName]
    )
  }

  const handleSelectAllResponseModels = () => {
    if (selectedResponseModels.length === models.length) {
      setSelectedResponseModels([])
    } else {
      setSelectedResponseModels(models.map((m) => m.name))
    }
  }

  // Prompt selection handlers
  const handlePromptToggle = (uid: number) => {
    setSelectedPromptUids((prev) =>
      prev.includes(uid)
        ? prev.filter((u) => u !== uid)
        : [...prev, uid]
    )
  }

  const handleSelectAllPrompts = () => {
    if (selectedPromptUids.length === prompts.length) {
      setSelectedPromptUids([])
    } else {
      setSelectedPromptUids(prompts.map((p) => p.uid))
    }
  }

  // Question handlers
  const handleQuestionToggle = (qId: string) => {
    setQuestions((prev) =>
      prev.map((q) =>
        q.id === qId ? { ...q, enabled: !q.enabled } : q
      )
    )
  }

  const handleQuestionPromptChange = (qId: string, prompt: string) => {
    setQuestions((prev) =>
      prev.map((q) =>
        q.id === qId ? { ...q, prompt } : q
      )
    )
  }

  // Run experiment with progress tracking
  const handleRunExperiment = async () => {
    if (selectedResponseModels.length === 0) {
      setError('Please select at least one response model')
      return
    }
    if (selectedPromptUids.length === 0) {
      setError('Please select at least one prompt')
      return
    }
    const enabledQuestions = questions.filter((q) => q.enabled)
    if (enabledQuestions.length === 0) {
      setError('Please enable at least one question')
      return
    }

    setLoading(true)
    setError('')
    setSuccessMessage('')
    abortRef.current = false

    try {
      // First, fetch the actual responses for selected models and prompts
      const pairsToGrade: PairToGrade[] = []
      
      for (const modelName of selectedResponseModels) {
        const data = await fetchResults({ model: modelName })
        for (const row of data.results) {
          const uid = Number(row.uid)
          if (selectedPromptUids.includes(uid)) {
            pairsToGrade.push({
              uid,
              model: modelName,
              question: String(row.Question || ''),
              response: String(row['Model Response'] || ''),
            })
          }
        }
      }

      const total = pairsToGrade.length
      setProgress({ current: 0, total })

      // Process each pair incrementally
      const newResults: PromptResult[] = []
      
      for (let i = 0; i < pairsToGrade.length; i++) {
        if (abortRef.current) {
          setError('Experiment cancelled')
          break
        }

        const pair = pairsToGrade[i]
        setCurrentPair(`${pair.model} - UID ${pair.uid}`)
        setProgress({ current: i + 1, total })

        try {
          const result = await gradeSinglePair({
            model_name: pair.model,
            uid: pair.uid,
            original_question: pair.question,
            model_response: pair.response,
            grader_model: selectedGraderModel,
            questions: questions,
          })
          newResults.push(result)
          
          // Update results incrementally so user can see progress
          setResults([...newResults])
        } catch (err) {
          // Add error result but continue
          newResults.push({
            uid: pair.uid,
            model: pair.model,
            question: pair.question,
            response: pair.response,
            q1_score: null,
            q1_response: '',
            q1_error: err instanceof Error ? err.message : 'Error',
            q2_score: null,
            q2_response: '',
            q2_error: err instanceof Error ? err.message : 'Error',
            q3_score: null,
            q3_response: '',
            q3_error: err instanceof Error ? err.message : 'Error',
            q4_score: null,
            q4_response: '',
            q4_error: err instanceof Error ? err.message : 'Error',
          })
          setResults([...newResults])
        }
      }

      setExperimentId(new Date().toISOString().replace(/[:.]/g, '-'))
      if (!abortRef.current) {
        setSuccessMessage(`Completed grading ${newResults.length} prompt-response pairs`)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
      setCurrentPair('')
    }
  }

  // Cancel experiment
  const handleCancelExperiment = () => {
    abortRef.current = true
  }

  // Save results
  const handleSaveResults = async () => {
    if (results.length === 0) {
      setError('No results to save')
      return
    }

    setSaving(true)
    setError('')

    try {
      const response = await saveMultiExperimentResults({
        experiment_id: experimentId,
        results: results,
        questions: questions,
        grader_model: selectedGraderModel,
      })
      setSuccessMessage(`Results saved to: ${response.filepath}`)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save results')
    } finally {
      setSaving(false)
    }
  }

  // Build histogram data for a specific question
  const buildHistogramData = (questionId: string): HistogramDataPoint[] => {
    const categories = QUESTION_META[questionId]?.categories || []
    const data: HistogramDataPoint[] = categories.map((cat) => ({
      category: cat,
    }))

    selectedResponseModels.forEach((modelName) => {
      const modelResults = results.filter((r) => r.model === modelName)

      categories.forEach((cat, idx) => {
        const scoreKey = `${questionId}_score` as keyof PromptResult
        const count = modelResults.filter((r) => r[scoreKey] === cat).length
        data[idx][modelName] = count
      })
    })

    return data
  }

  // Calculate summary stats for a question
  const getSummaryStats = (questionId: string) => {
    const stats: { model: string; count: number; distribution: Record<string, number> }[] = []
    const categories = QUESTION_META[questionId]?.categories || []
    
    selectedResponseModels.forEach((modelName) => {
      const modelResults = results.filter((r) => r.model === modelName)
      const scoreKey = `${questionId}_score` as keyof PromptResult
      const validResults = modelResults.filter((r) => r[scoreKey] !== null)
      
      const distribution: Record<string, number> = {}
      categories.forEach((cat) => {
        distribution[cat] = modelResults.filter((r) => r[scoreKey] === cat).length
      })
      
      stats.push({
        model: modelName,
        count: validResults.length,
        distribution,
      })
    })
    
    return stats
  }

  const enabledQuestionsCount = questions.filter((q) => q.enabled).length
  const progressPercent = progress.total > 0 ? Math.round((progress.current / progress.total) * 100) : 0

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Justification Lab</h2>
      <p className="text-gray-600">
        Run multi-question grading experiments on model responses.
      </p>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Step 1: Select Response Models */}
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-3">
            <h3 className="font-semibold text-gray-700">
              1. Select Response Models
            </h3>
            <button
              onClick={handleSelectAllResponseModels}
              className="text-sm text-blue-600 hover:text-blue-800"
            >
              {selectedResponseModels.length === models.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>
          <p className="text-xs text-gray-500 mb-2">
            Models whose responses will be evaluated
          </p>
          <div className="max-h-48 overflow-y-auto space-y-2">
            {models.map((model, idx) => (
              <label
                key={model.filename}
                className="flex items-center gap-2 cursor-pointer hover:bg-gray-50 p-1 rounded"
              >
                <input
                  type="checkbox"
                  checked={selectedResponseModels.includes(model.name)}
                  onChange={() => handleResponseModelToggle(model.name)}
                  className="rounded border-gray-300"
                />
                <span
                  className="w-3 h-3 rounded-full"
                  style={{
                    backgroundColor: selectedResponseModels.includes(model.name)
                      ? COLORS[idx % COLORS.length]
                      : '#ccc',
                  }}
                />
                <span className="text-sm">{model.name}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Step 2: Select Grader Model */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold text-gray-700 mb-3">
            2. Select Grader Model
          </h3>
          <p className="text-xs text-gray-500 mb-2">
            Model that will judge the responses
          </p>
          <input
            type="text"
            list="grader-model-options"
            value={selectedGraderModel}
            onChange={(e) => setSelectedGraderModel(e.target.value)}
            placeholder="Type or select a model..."
            className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <datalist id="grader-model-options">
            {AVAILABLE_GRADER_MODELS.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </div>
      </div>

      {/* Step 3: Configure Questions */}
      <div className="bg-white rounded-lg shadow p-4">
        <h3 className="font-semibold text-gray-700 mb-3">
          3. Configure Questions ({enabledQuestionsCount} enabled)
        </h3>
        <p className="text-xs text-gray-500 mb-4">
          Toggle and customize each question. Disabled questions will preserve previous results.
        </p>
        
        <div className="space-y-6">
          {questions.map((q) => (
            <div key={q.id} className={`border rounded-lg p-4 ${q.enabled ? 'border-blue-300 bg-blue-50' : 'border-gray-200 bg-gray-50'}`}>
              <div className="flex items-center justify-between mb-2">
                <label className="flex items-center gap-2 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={q.enabled}
                    onChange={() => handleQuestionToggle(q.id)}
                    className="rounded border-gray-300"
                  />
                  <span className="font-medium text-gray-700">
                    {QUESTION_META[q.id]?.name || q.id}
                  </span>
                </label>
                <span className="text-xs text-gray-500">
                  Output: {QUESTION_META[q.id]?.categories.join(', ')}
                </span>
              </div>
              <textarea
                value={q.prompt}
                onChange={(e) => handleQuestionPromptChange(q.id, e.target.value)}
                disabled={!q.enabled}
                rows={4}
                className={`w-full border rounded-lg px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 ${
                  q.enabled ? 'border-gray-300 bg-white' : 'border-gray-200 bg-gray-100 text-gray-500'
                }`}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Step 4: Select Prompts */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="font-semibold text-gray-700">
            4. Select Prompts to Evaluate
          </h3>
          <div className="flex gap-4 items-center">
            <span className="text-sm text-gray-500">
              {selectedPromptUids.length} / {prompts.length} selected
            </span>
            <button
              onClick={handleSelectAllPrompts}
              disabled={prompts.length === 0}
              className="text-sm text-blue-600 hover:text-blue-800 disabled:text-gray-400"
            >
              {selectedPromptUids.length === prompts.length ? 'Deselect All' : 'Select All'}
            </button>
          </div>
        </div>
        {selectedResponseModels.length === 0 ? (
          <p className="text-gray-500 text-sm">Select response models first to see available prompts</p>
        ) : prompts.length === 0 ? (
          <p className="text-gray-500 text-sm">Loading prompts...</p>
        ) : (
          <div className="max-h-64 overflow-y-auto border border-gray-200 rounded-lg">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 sticky top-0">
                <tr>
                  <th className="px-3 py-2 text-left w-10">
                    <input
                      type="checkbox"
                      checked={selectedPromptUids.length === prompts.length && prompts.length > 0}
                      onChange={handleSelectAllPrompts}
                      className="rounded border-gray-300"
                    />
                  </th>
                  <th className="px-3 py-2 text-left w-16">UID</th>
                  <th className="px-3 py-2 text-left w-32">Topic</th>
                  <th className="px-3 py-2 text-left">Question</th>
                </tr>
              </thead>
              <tbody>
                {prompts.map((prompt) => (
                  <tr
                    key={prompt.uid}
                    className="border-t border-gray-100 hover:bg-gray-50 cursor-pointer"
                    onClick={() => handlePromptToggle(prompt.uid)}
                  >
                    <td className="px-3 py-2">
                      <input
                        type="checkbox"
                        checked={selectedPromptUids.includes(prompt.uid)}
                        onChange={() => handlePromptToggle(prompt.uid)}
                        onClick={(e) => e.stopPropagation()}
                        className="rounded border-gray-300"
                      />
                    </td>
                    <td className="px-3 py-2 text-gray-600">{prompt.uid}</td>
                    <td className="px-3 py-2 text-gray-600">{prompt.topic}</td>
                    <td className="px-3 py-2 text-gray-800 truncate max-w-md">
                      {prompt.question}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Progress Bar */}
      {loading && (
        <div className="bg-white rounded-lg shadow p-4">
          <div className="flex items-center justify-between mb-2">
            <h3 className="font-semibold text-gray-700">Progress</h3>
            <span className="text-sm text-gray-600">
              {progress.current} / {progress.total} ({progressPercent}%)
            </span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 mb-2">
            <div
              className="bg-blue-600 h-4 rounded-full transition-all duration-300"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
          <div className="flex items-center justify-between">
            <p className="text-sm text-gray-500">
              Currently grading: <span className="font-medium">{currentPair}</span>
            </p>
            <button
              onClick={handleCancelExperiment}
              className="px-4 py-1 bg-red-500 text-white rounded hover:bg-red-600 text-sm"
            >
              Cancel
            </button>
          </div>
        </div>
      )}

      {/* Run Button */}
      {!loading && (
        <div className="flex gap-4 items-center">
          <button
            onClick={handleRunExperiment}
            disabled={loading || selectedResponseModels.length === 0 || selectedPromptUids.length === 0 || enabledQuestionsCount === 0}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
          >
            Run Experiment ({selectedPromptUids.length * selectedResponseModels.length} pairs × {enabledQuestionsCount} questions)
          </button>
          
          {results.length > 0 && (
            <button
              onClick={handleSaveResults}
              disabled={saving}
              className="px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors font-medium"
            >
              {saving ? 'Saving...' : 'Save Results'}
            </button>
          )}
        </div>
      )}

      {/* Error/Success Messages */}
      {error && (
        <div className="p-4 bg-red-50 border border-red-200 rounded-lg text-red-700">
          {error}
        </div>
      )}

      {successMessage && (
        <div className="p-4 bg-green-50 border border-green-200 rounded-lg text-green-700">
          {successMessage}
        </div>
      )}

      {/* Results Section - 4 Histograms */}
      {results.length > 0 && (
        <div className="space-y-6">
          <h3 className="text-xl font-bold">Results ({results.length} pairs graded)</h3>
          
          {/* Histogram for each question */}
          {['q1', 'q2', 'q3', 'q4'].map((qId) => {
            const histogramData = buildHistogramData(qId)
            const stats = getSummaryStats(qId)
            const meta = QUESTION_META[qId]

            return (
              <CollapsibleSection
                key={qId}
                id={`experiment-${qId}-hist`}
                title={meta?.name || `Question ${qId.toUpperCase()}`}
              >
                {/* Summary stats */}
                <div className="flex gap-4 mb-4 flex-wrap">
                  {stats.map((stat) => (
                    <div key={stat.model} className="flex items-center gap-2 text-sm">
                      <span
                        className="w-3 h-3 rounded-full"
                        style={{ backgroundColor: COLORS[models.findIndex((m) => m.name === stat.model) % COLORS.length] }}
                      />
                      <span className="text-gray-600">{stat.model}:</span>
                      <span className="font-medium">{stat.count} scored</span>
                    </div>
                  ))}
                </div>

                {/* Histogram */}
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={histogramData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="category"
                        label={{ value: meta?.name.split(':')[1]?.trim() || 'Score', position: 'insideBottom', offset: -5 }}
                      />
                      <YAxis label={{ value: 'Count', angle: -90, position: 'insideLeft' }} />
                      <Tooltip />
                      <Legend />
                      {selectedResponseModels.map((modelName) => (
                        <Bar
                          key={modelName}
                          dataKey={modelName}
                          fill={COLORS[models.findIndex((m) => m.name === modelName) % COLORS.length]}
                        />
                      ))}
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CollapsibleSection>
            )
          })}

          {/* Detailed Results Table */}
          <CollapsibleSection id="experiment-results-table" title="Detailed Results Table">
            <div className="max-h-96 overflow-auto border border-gray-200 rounded-lg">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 sticky top-0">
                  <tr>
                    <th className="px-3 py-2 text-left w-16">UID</th>
                    <th className="px-3 py-2 text-left w-40">Model</th>
                    <th className="px-3 py-2 text-left w-16">Q1</th>
                    <th className="px-3 py-2 text-left w-16">Q2</th>
                    <th className="px-3 py-2 text-left w-16">Q3</th>
                    <th className="px-3 py-2 text-left w-16">Q4</th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((result, idx) => (
                    <tr key={`${result.uid}-${result.model}-${idx}`} className="border-t border-gray-100">
                      <td className="px-3 py-2 text-gray-600">{result.uid}</td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-2">
                          <span
                            className="w-3 h-3 rounded-full"
                            style={{ backgroundColor: COLORS[models.findIndex((m) => m.name === result.model) % COLORS.length] }}
                          />
                          <span className="text-gray-800 truncate">{result.model}</span>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        {result.q1_error ? (
                          <span className="text-red-600" title={result.q1_error}>⚠</span>
                        ) : result.q1_score !== null ? (
                          <span className="font-medium">{result.q1_score}</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {result.q2_error ? (
                          <span className="text-red-600" title={result.q2_error}>⚠</span>
                        ) : result.q2_score !== null ? (
                          <span className="font-medium">{result.q2_score}</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {result.q3_error ? (
                          <span className="text-red-600" title={result.q3_error}>⚠</span>
                        ) : result.q3_score !== null ? (
                          <span className="font-medium">{result.q3_score}</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-3 py-2">
                        {result.q4_error ? (
                          <span className="text-red-600" title={result.q4_error}>⚠</span>
                        ) : result.q4_score !== null ? (
                          <span className="font-medium">{result.q4_score}</span>
                        ) : (
                          <span className="text-gray-400">-</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CollapsibleSection>
        </div>
      )}
    </div>
  )
}
