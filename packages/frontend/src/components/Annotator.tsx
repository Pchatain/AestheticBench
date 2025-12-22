import { useEffect, useState, useCallback } from 'react'
import { fetchModels, fetchTopics, fetchResults, fetchAnnotations, lookupAnnotation, saveAnnotation } from '../api'
import type { Model, Result, Annotation } from '../types'

interface AnnotationModalProps {
  isOpen: boolean
  result: Result | null
  model: string
  existingAnnotation: Annotation | null
  onSave: (notes: string) => void
  onClose: () => void
}

function AnnotationModal({ isOpen, result, model, existingAnnotation, onSave, onClose }: AnnotationModalProps) {
  const [notes, setNotes] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (existingAnnotation) {
      setNotes(existingAnnotation.notes)
    } else {
      setNotes('')
    }
  }, [existingAnnotation, isOpen])

  if (!isOpen || !result) return null

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave(notes)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-3xl w-full mx-4 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">
            Annotate Response - {model}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            &times;
          </button>
        </div>
        <div className="px-6 py-4 overflow-y-auto flex-1 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Question</label>
            <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded max-h-32 overflow-y-auto">
              {result.Question as string}
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Model Response</label>
            <p className="text-sm text-gray-600 bg-gray-50 p-3 rounded max-h-48 overflow-y-auto whitespace-pre-wrap">
              {result[`response_${model}`] as string || result['Model Response'] as string || 'N/A'}
            </p>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Annotation Notes</label>
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              placeholder="Enter your annotation notes here..."
              className="w-full h-40 p-3 border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
            />
          </div>
          {existingAnnotation && (
            <p className="text-xs text-gray-500">
              Last updated: {new Date(existingAnnotation.updated_at).toLocaleString()}
            </p>
          )}
        </div>
        <div className="px-6 py-4 border-t flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 bg-gray-100 hover:bg-gray-200 rounded-md text-sm font-medium"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-sm font-medium disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save Annotation'}
          </button>
        </div>
      </div>
    </div>
  )
}

export function Annotator() {
  const [models, setModels] = useState<Model[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const [selectedModels, setSelectedModels] = useState<string[]>([])
  const [selectedTopic, setSelectedTopic] = useState('')
  const [searchQuery, setSearchQuery] = useState('')
  const [results, setResults] = useState<Result[]>([])
  const [loading, setLoading] = useState(false)
  const [annotationsCache, setAnnotationsCache] = useState<Record<string, Annotation>>({})

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [modalResult, setModalResult] = useState<Result | null>(null)
  const [modalModel, setModalModel] = useState('')
  const [modalAnnotation, setModalAnnotation] = useState<Annotation | null>(null)

  useEffect(() => {
    fetchModels().then((data) => setModels(data.models))
    fetchTopics().then((data) => setTopics(data.topics))
  }, [])

  const getCacheKey = (uid: number, model: string) => `${uid}:${model}`

  const loadResults = useCallback(async () => {
    if (selectedModels.length === 0) {
      setResults([])
      return
    }
    setLoading(true)

    // Fetch results for all selected models and merge by Question
    const allResultsByQuestion: Record<string, Result> = {}

    for (const model of selectedModels) {
      const data = await fetchResults({
        model,
        topic: selectedTopic || undefined,
        search: searchQuery || undefined,
      })

      for (const result of data.results) {
        const question = result.Question as string
        if (!allResultsByQuestion[question]) {
          allResultsByQuestion[question] = {
            uid: result.uid,
            Question: question,
            Topic: result.Topic,
          }
        }
        allResultsByQuestion[question][`response_${model}`] = result['Model Response']
        allResultsByQuestion[question][`uid_${model}`] = result.uid
      }
    }

    setResults(Object.values(allResultsByQuestion))

    // Fetch existing annotations to populate cache
    const annotationsData = await fetchAnnotations()
    const cache: Record<string, Annotation> = {}
    for (const ann of annotationsData.annotations) {
      const key = getCacheKey(ann.result_uid, ann.model)
      cache[key] = ann
    }
    setAnnotationsCache(cache)

    setLoading(false)
  }, [selectedModels, selectedTopic, searchQuery])

  useEffect(() => {
    const debounce = setTimeout(loadResults, 300)
    return () => clearTimeout(debounce)
  }, [loadResults])

  const handleModelToggle = (modelName: string) => {
    setSelectedModels((prev) =>
      prev.includes(modelName)
        ? prev.filter((m) => m !== modelName)
        : [...prev, modelName]
    )
  }

  const handleCellClick = async (result: Result, model: string) => {
    const uid = result[`uid_${model}`] as number
    if (!uid) return

    setModalResult(result)
    setModalModel(model)

    const cacheKey = getCacheKey(uid, model)
    if (annotationsCache[cacheKey]) {
      setModalAnnotation(annotationsCache[cacheKey])
    } else {
      const response = await lookupAnnotation(uid, model)
      if (response.found && response.annotation) {
        setAnnotationsCache((prev) => ({ ...prev, [cacheKey]: response.annotation! }))
        setModalAnnotation(response.annotation)
      } else {
        setModalAnnotation(null)
      }
    }

    setModalOpen(true)
  }

  const handleSaveAnnotation = async (notes: string) => {
    if (!modalResult || !modalModel) return

    const uid = modalResult[`uid_${modalModel}`] as number
    const response = await saveAnnotation({
      result_uid: uid,
      model: modalModel,
      notes,
    })

    const cacheKey = getCacheKey(uid, modalModel)
    setAnnotationsCache((prev) => ({ ...prev, [cacheKey]: response.annotation }))
    setModalOpen(false)
  }

  const hasAnnotation = (result: Result, model: string): boolean => {
    const uid = result[`uid_${model}`] as number
    if (!uid) return false
    const cacheKey = getCacheKey(uid, model)
    return cacheKey in annotationsCache && annotationsCache[cacheKey].notes.length > 0
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Annotator</h2>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Model Selection */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Select Models (Columns)</h3>
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

        {/* Topic Filter */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Filter by Topic</h3>
          <select
            value={selectedTopic}
            onChange={(e) => setSelectedTopic(e.target.value)}
            className="w-full p-2 border border-gray-300 rounded-md"
          >
            <option value="">All Topics</option>
            {topics.map((topic) => (
              <option key={topic} value={topic}>
                {topic}
              </option>
            ))}
          </select>
        </div>

        {/* Search */}
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-semibold text-gray-700 mb-3">Search Questions</h3>
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search..."
            className="w-full p-2 border border-gray-300 rounded-md"
          />
        </div>
      </div>

      {/* Results Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64 bg-white rounded-lg shadow">
          <div className="text-gray-500">Loading...</div>
        </div>
      ) : selectedModels.length === 0 ? (
        <div className="flex items-center justify-center h-64 bg-white rounded-lg shadow">
          <div className="text-gray-500">Select at least one model to start annotating</div>
        </div>
      ) : results.length === 0 ? (
        <div className="flex items-center justify-center h-64 bg-white rounded-lg shadow">
          <div className="text-gray-500">No results found</div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200">
            <span className="text-sm text-gray-700">{results.length} questions</span>
          </div>
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                    #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Question
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                    Topic
                  </th>
                  {selectedModels.map((model) => (
                    <th
                      key={model}
                      className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider min-w-[200px]"
                    >
                      {model}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {results.slice(0, 50).map((result, idx) => (
                  <tr key={idx} className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm text-gray-500">{idx + 1}</td>
                    <td className="px-4 py-3 text-sm max-w-md">
                      <span className="line-clamp-2">{result.Question as string}</span>
                    </td>
                    <td className="px-4 py-3">
                      {result.Topic && (
                        <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                          {result.Topic as string}
                        </span>
                      )}
                    </td>
                    {selectedModels.map((model) => (
                      <td key={model} className="px-4 py-3">
                        <button
                          onClick={() => handleCellClick(result, model)}
                          className={`w-full text-left p-2 rounded border text-sm hover:bg-gray-100 ${
                            hasAnnotation(result, model)
                              ? 'border-green-500 bg-green-50'
                              : 'border-gray-200'
                          }`}
                          title="Click to annotate"
                        >
                          <span className="line-clamp-3 text-gray-700">
                            {(result[`response_${model}`] as string)?.slice(0, 150) || 'N/A'}
                            {(result[`response_${model}`] as string)?.length > 150 && '...'}
                          </span>
                          {hasAnnotation(result, model) && (
                            <span className="block mt-1 text-xs text-green-600">Annotated</span>
                          )}
                        </button>
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {results.length > 50 && (
            <div className="px-4 py-3 border-t border-gray-200 text-sm text-gray-500">
              Showing first 50 of {results.length} results
            </div>
          )}
        </div>
      )}

      <AnnotationModal
        isOpen={modalOpen}
        result={modalResult}
        model={modalModel}
        existingAnnotation={modalAnnotation}
        onSave={handleSaveAnnotation}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}
