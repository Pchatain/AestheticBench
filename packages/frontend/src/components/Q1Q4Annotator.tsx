import { useEffect, useState, useCallback } from 'react'
import { fetchQ1Q4Responses, fetchQ1Q4Models, saveQ1Q4Annotation } from '../api'
import type { ResponseWithQ1Q4, Q1Q4AnnotationCreate } from '../types'

interface AnnotationFormData {
  q1_score: string | null
  q1_reasoning: string
  q2_score: number | null
  q2_reasoning: string
  q3_score: number | null
  q3_reasoning: string
  q4_score: number | null
  q4_reasoning: string
}

interface AnnotationModalProps {
  isOpen: boolean
  response: ResponseWithQ1Q4 | null
  onSave: (data: Q1Q4AnnotationCreate) => Promise<void>
  onClose: () => void
}

function AnnotationModal({ isOpen, response, onSave, onClose }: AnnotationModalProps) {
  const [formData, setFormData] = useState<AnnotationFormData>({
    q1_score: null,
    q1_reasoning: '',
    q2_score: null,
    q2_reasoning: '',
    q3_score: null,
    q3_reasoning: '',
    q4_score: null,
    q4_reasoning: '',
  })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    if (response) {
      setFormData({
        q1_score: response.human_q1_score,
        q1_reasoning: response.human_q1_reasoning || '',
        q2_score: response.human_q2_score,
        q2_reasoning: response.human_q2_reasoning || '',
        q3_score: response.human_q3_score,
        q3_reasoning: response.human_q3_reasoning || '',
        q4_score: response.human_q4_score,
        q4_reasoning: response.human_q4_reasoning || '',
      })
    }
  }, [response])

  if (!isOpen || !response) return null

  const handleSave = async () => {
    setSaving(true)
    try {
      await onSave({
        response_id: response.response_id,
        model: response.model,
        q1_score: formData.q1_score,
        q1_reasoning: formData.q1_reasoning || null,
        q2_score: formData.q2_score,
        q2_reasoning: formData.q2_reasoning || null,
        q3_score: formData.q3_score,
        q3_reasoning: formData.q3_reasoning || null,
        q4_score: formData.q4_score,
        q4_reasoning: formData.q4_reasoning || null,
      })
      onClose()
    } finally {
      setSaving(false)
    }
  }

  const hasHumanAnnotation = response.human_q1_score !== null || 
    response.human_q2_score !== null || 
    response.human_q3_score !== null || 
    response.human_q4_score !== null

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="fixed inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="relative bg-white rounded-lg shadow-xl max-w-5xl w-full mx-4 max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b">
          <h3 className="text-lg font-semibold">
            Q1-Q4 Annotation - {response.model}
            {hasHumanAnnotation && <span className="ml-2 text-sm text-green-600">(has existing annotation)</span>}
          </h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-600 text-2xl leading-none">
            &times;
          </button>
        </div>
        
        <div className="px-6 py-4 overflow-y-auto flex-1 space-y-6">
          {/* Question and Response */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Question</label>
              <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded min-h-[80px] max-h-[150px] overflow-y-auto">
                {response.question_text}
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Model Response</label>
              <div className="text-sm text-gray-600 bg-gray-50 p-3 rounded min-h-[80px] max-h-[150px] overflow-y-auto whitespace-pre-wrap">
                {response.response_text}
              </div>
            </div>
          </div>

          {/* Q1: Relativism (Yes/No) */}
          <div className="border rounded-lg p-4 bg-blue-50">
            <h4 className="font-medium text-gray-800 mb-2">Q1: Relativism (Yes/No)</h4>
            <p className="text-xs text-gray-600 mb-3">Does the response treat the question as having a relative or subjective answer?</p>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Grade</label>
                <div className="p-2 bg-white rounded border text-sm">
                  <span className="font-medium">{response.llm_q1_score || 'N/A'}</span>
                  {response.llm_q1_reasoning && (
                    <p className="mt-1 text-gray-500 text-xs max-h-16 overflow-y-auto">{response.llm_q1_reasoning}</p>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Human Annotation</label>
                <div className="flex gap-4 mb-2">
                  <label className="flex items-center gap-1">
                    <input
                      type="radio"
                      name="q1"
                      checked={formData.q1_score === 'Yes'}
                      onChange={() => setFormData(prev => ({ ...prev, q1_score: 'Yes' }))}
                    />
                    <span className="text-sm">Yes</span>
                  </label>
                  <label className="flex items-center gap-1">
                    <input
                      type="radio"
                      name="q1"
                      checked={formData.q1_score === 'No'}
                      onChange={() => setFormData(prev => ({ ...prev, q1_score: 'No' }))}
                    />
                    <span className="text-sm">No</span>
                  </label>
                  <button
                    onClick={() => setFormData(prev => ({ ...prev, q1_score: null }))}
                    className="text-xs text-gray-500 hover:text-gray-700"
                  >
                    Clear
                  </button>
                </div>
                <textarea
                  value={formData.q1_reasoning}
                  onChange={(e) => setFormData(prev => ({ ...prev, q1_reasoning: e.target.value }))}
                  placeholder="Reasoning..."
                  className="w-full p-2 border border-gray-300 rounded text-sm"
                  rows={2}
                />
              </div>
            </div>
          </div>

          {/* Q2: Preference (-1, 0, 1) */}
          <div className="border rounded-lg p-4 bg-green-50">
            <h4 className="font-medium text-gray-800 mb-2">Q2: Preference (-1, 0, 1)</h4>
            <p className="text-xs text-gray-600 mb-3">Does the response express a preference or opinion? -1=disagrees, 0=neutral, 1=agrees</p>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Grade</label>
                <div className="p-2 bg-white rounded border text-sm">
                  <span className="font-medium">{response.llm_q2_score ?? 'N/A'}</span>
                  {response.llm_q2_reasoning && (
                    <p className="mt-1 text-gray-500 text-xs max-h-16 overflow-y-auto">{response.llm_q2_reasoning}</p>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Human Annotation</label>
                <select
                  value={formData.q2_score ?? ''}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    q2_score: e.target.value === '' ? null : parseInt(e.target.value) 
                  }))}
                  className="w-full p-2 border border-gray-300 rounded text-sm mb-2"
                >
                  <option value="">Select...</option>
                  <option value="-1">-1 (Disagrees)</option>
                  <option value="0">0 (Neutral)</option>
                  <option value="1">1 (Agrees)</option>
                </select>
                <textarea
                  value={formData.q2_reasoning}
                  onChange={(e) => setFormData(prev => ({ ...prev, q2_reasoning: e.target.value }))}
                  placeholder="Reasoning..."
                  className="w-full p-2 border border-gray-300 rounded text-sm"
                  rows={2}
                />
              </div>
            </div>
          </div>

          {/* Q3: Evidence (-1, 0, 1) */}
          <div className="border rounded-lg p-4 bg-yellow-50">
            <h4 className="font-medium text-gray-800 mb-2">Q3: Evidence (-1, 0, 1)</h4>
            <p className="text-xs text-gray-600 mb-3">Does the response provide evidence or reasoning? -1=poor, 0=mixed, 1=good</p>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Grade</label>
                <div className="p-2 bg-white rounded border text-sm">
                  <span className="font-medium">{response.llm_q3_score ?? 'N/A'}</span>
                  {response.llm_q3_reasoning && (
                    <p className="mt-1 text-gray-500 text-xs max-h-16 overflow-y-auto">{response.llm_q3_reasoning}</p>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Human Annotation</label>
                <select
                  value={formData.q3_score ?? ''}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    q3_score: e.target.value === '' ? null : parseInt(e.target.value) 
                  }))}
                  className="w-full p-2 border border-gray-300 rounded text-sm mb-2"
                >
                  <option value="">Select...</option>
                  <option value="-1">-1 (Poor)</option>
                  <option value="0">0 (Mixed)</option>
                  <option value="1">1 (Good)</option>
                </select>
                <textarea
                  value={formData.q3_reasoning}
                  onChange={(e) => setFormData(prev => ({ ...prev, q3_reasoning: e.target.value }))}
                  placeholder="Reasoning..."
                  className="w-full p-2 border border-gray-300 rounded text-sm"
                  rows={2}
                />
              </div>
            </div>
          </div>

          {/* Q4: Justification (1-5) */}
          <div className="border rounded-lg p-4 bg-purple-50">
            <h4 className="font-medium text-gray-800 mb-2">Q4: Justification Quality (1-5)</h4>
            <p className="text-xs text-gray-600 mb-3">How well does the response justify its position? 1=poor, 5=excellent</p>
            
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">LLM Grade</label>
                <div className="p-2 bg-white rounded border text-sm">
                  <span className="font-medium">{response.llm_q4_score ?? 'N/A'}</span>
                  {response.llm_q4_reasoning && (
                    <p className="mt-1 text-gray-500 text-xs max-h-16 overflow-y-auto">{response.llm_q4_reasoning}</p>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">Human Annotation</label>
                <select
                  value={formData.q4_score ?? ''}
                  onChange={(e) => setFormData(prev => ({ 
                    ...prev, 
                    q4_score: e.target.value === '' ? null : parseInt(e.target.value) 
                  }))}
                  className="w-full p-2 border border-gray-300 rounded text-sm mb-2"
                >
                  <option value="">Select...</option>
                  <option value="1">1 - Poor</option>
                  <option value="2">2 - Fair</option>
                  <option value="3">3 - Good</option>
                  <option value="4">4 - Very Good</option>
                  <option value="5">5 - Excellent</option>
                </select>
                <textarea
                  value={formData.q4_reasoning}
                  onChange={(e) => setFormData(prev => ({ ...prev, q4_reasoning: e.target.value }))}
                  placeholder="Reasoning..."
                  className="w-full p-2 border border-gray-300 rounded text-sm"
                  rows={2}
                />
              </div>
            </div>
          </div>
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

export function Q1Q4Annotator() {
  const [models, setModels] = useState<string[]>([])
  const [selectedModel, setSelectedModel] = useState('')
  const [responses, setResponses] = useState<ResponseWithQ1Q4[]>([])
  const [loading, setLoading] = useState(false)
  const [limit] = useState(100)
  const [offset, setOffset] = useState(0)

  // Modal state
  const [modalOpen, setModalOpen] = useState(false)
  const [selectedResponse, setSelectedResponse] = useState<ResponseWithQ1Q4 | null>(null)

  useEffect(() => {
    fetchQ1Q4Models().then((data) => setModels(data.models))
  }, [])

  const loadResponses = useCallback(async () => {
    setLoading(true)
    const data = await fetchQ1Q4Responses({
      model: selectedModel || undefined,
      limit,
      offset,
    })
    setResponses(data.responses)
    setLoading(false)
  }, [selectedModel, limit, offset])

  useEffect(() => {
    loadResponses()
  }, [loadResponses])

  const handleRowClick = (response: ResponseWithQ1Q4) => {
    setSelectedResponse(response)
    setModalOpen(true)
  }

  const handleSave = async (data: Q1Q4AnnotationCreate) => {
    await saveQ1Q4Annotation(data)
    // Refresh the list to show updated annotations
    await loadResponses()
  }

  const hasAnnotation = (response: ResponseWithQ1Q4): boolean => {
    return response.human_q1_score !== null || 
           response.human_q2_score !== null || 
           response.human_q3_score !== null || 
           response.human_q4_score !== null
  }

  const hasLLMGrades = (response: ResponseWithQ1Q4): boolean => {
    return response.llm_q1_score !== null || 
           response.llm_q2_score !== null || 
           response.llm_q3_score !== null || 
           response.llm_q4_score !== null
  }

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold">Q1-Q4 Annotator</h2>
      <p className="text-gray-600">
        Annotate model responses with Q1-Q4 scores to align LLM judges with human judgment.
      </p>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Filter by Model</label>
            <select
              value={selectedModel}
              onChange={(e) => {
                setSelectedModel(e.target.value)
                setOffset(0)
              }}
              className="w-full p-2 border border-gray-300 rounded-md"
            >
              <option value="">All Models</option>
              {models.map((model) => (
                <option key={model} value={model}>
                  {model}
                </option>
              ))}
            </select>
          </div>
          <div className="flex items-end">
            <span className="text-sm text-gray-600">
              Showing {responses.length} responses (offset: {offset})
            </span>
          </div>
          <div className="flex items-end gap-2 justify-end">
            <button
              onClick={() => setOffset(Math.max(0, offset - limit))}
              disabled={offset === 0}
              className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded disabled:opacity-50"
            >
              ← Previous
            </button>
            <button
              onClick={() => setOffset(offset + limit)}
              disabled={responses.length < limit}
              className="px-3 py-2 bg-gray-100 hover:bg-gray-200 rounded disabled:opacity-50"
            >
              Next →
            </button>
          </div>
        </div>
      </div>

      {/* Results Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64 bg-white rounded-lg shadow">
          <div className="text-gray-500">Loading...</div>
        </div>
      ) : responses.length === 0 ? (
        <div className="flex items-center justify-center h-64 bg-white rounded-lg shadow">
          <div className="text-gray-500">No responses found</div>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-12">
                    #
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Model
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                    Topic
                  </th>
                  <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Question (preview)
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                    Q1
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                    Q2
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                    Q3
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-20">
                    Q4
                  </th>
                  <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider w-24">
                    Status
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {responses.map((response, idx) => (
                  <tr
                    key={response.response_id}
                    onClick={() => handleRowClick(response)}
                    className={`cursor-pointer hover:bg-gray-50 ${
                      hasAnnotation(response) ? 'bg-green-50' : ''
                    }`}
                  >
                    <td className="px-4 py-3 text-sm text-gray-500">
                      {offset + idx + 1}
                    </td>
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">
                      {response.model}
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                        {response.topic}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600 max-w-md truncate">
                      {response.question_text}
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center text-xs gap-0.5">
                        <span className="text-blue-600" title="LLM">
                          {response.llm_q1_score || '-'}
                        </span>
                        {response.human_q1_score && (
                          <span className="text-green-600 font-medium" title="Human">
                            {response.human_q1_score}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center text-xs gap-0.5">
                        <span className="text-blue-600" title="LLM">
                          {response.llm_q2_score ?? '-'}
                        </span>
                        {response.human_q2_score !== null && (
                          <span className="text-green-600 font-medium" title="Human">
                            {response.human_q2_score}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center text-xs gap-0.5">
                        <span className="text-blue-600" title="LLM">
                          {response.llm_q3_score ?? '-'}
                        </span>
                        {response.human_q3_score !== null && (
                          <span className="text-green-600 font-medium" title="Human">
                            {response.human_q3_score}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      <div className="flex flex-col items-center text-xs gap-0.5">
                        <span className="text-blue-600" title="LLM">
                          {response.llm_q4_score ?? '-'}
                        </span>
                        {response.human_q4_score !== null && (
                          <span className="text-green-600 font-medium" title="Human">
                            {response.human_q4_score}
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-center">
                      {hasAnnotation(response) ? (
                        <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full text-xs">
                          Annotated
                        </span>
                      ) : hasLLMGrades(response) ? (
                        <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full text-xs">
                          Needs Review
                        </span>
                      ) : (
                        <span className="px-2 py-1 bg-gray-100 text-gray-600 rounded-full text-xs">
                          No Grades
                        </span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      <AnnotationModal
        isOpen={modalOpen}
        response={selectedResponse}
        onSave={handleSave}
        onClose={() => setModalOpen(false)}
      />
    </div>
  )
}
