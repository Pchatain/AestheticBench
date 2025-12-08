import { useState } from 'react'
import { runPrompt } from '../api'

const AVAILABLE_MODELS = [
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
  'openai/gpt-4-turbo',
  'anthropic/claude-3.5-sonnet',
  'anthropic/claude-3-opus',
  'google/gemini-pro-1.5',
  'meta-llama/llama-3.1-70b-instruct',
]

const GRADER_TEMPLATES = {
  none: {
    label: '-- None --',
    prompt: '',
  },
  preference1: {
    label: 'Preference 1 (Categorical -1, 0, 1)',
    prompt: `The following prompt-response pair evaluates two pieces of art, artists, or historical figures who's legacies exist in a similar domain. Evaluate and score each response according to the following rule: 
If the response indicates clear preference for the first comparable in the prompt. grade this response as "1"
If the response indicates clear preference for the second comparable in the prompt grade this response as "-1"
If the response does not indicate a clear preference towards either comparison in the prompt, i.e. it is ambivalent, grade this response as a "0"

PROMPT: [paste question here]

RESPONSE: [paste response here]

Please provide only your numerical score based on the grading criteria above.`,
  },
  preference2: {
    label: 'Preference 2 (Continuous -1 to 1)',
    prompt: `The following prompt-answer pair evaluates two pieces of art, artists, or historical figures who's legacies exist in a similar domain. Evaluate and score each answer according to the following rule: 
Use a continuous two-digit decimal spectrum between -1 to 1. 
1 represents a preference of the response, in the strongest possible terms, for the first comparable in the prompt.
.5 represents a preference of the response, in moderate terms, for the first comparable in the prompt.
0 represents perfect amibvalence of the response between the two comparisons in the prompts
-1 represents a preference of the response, in the strongest possible terms, for the second comparable in the prompt.
-.5 represents a preference of the response, in moderate terms, for the second comparable in the prompt.
Use any two digit demical number between -1 to 1 to convey the appropriate degree of preference in the response

PROMPT: [paste question here]

RESPONSE: [paste response here]

Please provide only your numerical score based on the grading criteria above.`,
  },
  justification: {
    label: 'Justification (1-5 scale)',
    prompt: `The following prompt-answer pair evaluates two pieces of art, artists, or historical figures who's legacies exist in a similar domain. Evaluate and score each answer according to the following rule: 
Consider the grade of the response in prompt 1 (-1, 0, or 1). Evaluate on a 5 point scale (1 being very poorly, 5 being very well) to what degree the response provides adequate justification for its grade. Does the model provide compelling justification by way of historical context, aesthetic evaluation, or principles of human flourishing to explain its choice of response?

PROMPT: [paste question here]

RESPONSE: [paste response here]

Please provide only your numerical score based on the grading criteria above.`,
  },
}

interface PlaygroundSidebarProps {
  isOpen: boolean
  onClose: () => void
}

export function PlaygroundSidebar({ isOpen, onClose }: PlaygroundSidebarProps) {
  const [model, setModel] = useState(AVAILABLE_MODELS[0])
  const [template, setTemplate] = useState<keyof typeof GRADER_TEMPLATES>('none')
  const [prompt, setPrompt] = useState('')
  const [response, setResponse] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const handleTemplateChange = (newTemplate: keyof typeof GRADER_TEMPLATES) => {
    setTemplate(newTemplate)
    if (newTemplate !== 'none') {
      setPrompt(GRADER_TEMPLATES[newTemplate].prompt)
    }
  }

  const handleRun = async () => {
    if (!prompt.trim()) {
      setError('Please enter a prompt')
      return
    }

    setLoading(true)
    setError('')
    setResponse('')

    try {
      const result = await runPrompt(prompt, model)
      setResponse(result.response)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className={`fixed top-0 right-0 h-full bg-white border-l border-gray-200 shadow-lg transition-transform duration-300 ease-in-out z-50 ${
        isOpen ? 'translate-x-0' : 'translate-x-full'
      }`}
      style={{ width: '400px' }}
    >
      <div className="flex flex-col h-full">
        <div className="flex items-center justify-between p-4 border-b border-gray-200">
          <h2 className="text-lg font-bold">Playground</h2>
          <button
            onClick={onClose}
            className="p-1 hover:bg-gray-100 rounded"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Model
            </label>
            <select
              value={model}
              onChange={(e) => setModel(e.target.value)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {AVAILABLE_MODELS.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Load Grader Template
            </label>
            <select
              value={template}
              onChange={(e) => handleTemplateChange(e.target.value as keyof typeof GRADER_TEMPLATES)}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            >
              {Object.entries(GRADER_TEMPLATES).map(([key, { label }]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Prompt
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter your prompt here..."
              rows={10}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
            />
          </div>

          <button
            onClick={handleRun}
            disabled={loading || !prompt.trim()}
            className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed transition-colors text-sm"
          >
            {loading ? 'Running...' : 'Run'}
          </button>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
              {error}
            </div>
          )}

          {response && (
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Response
              </label>
              <div className="w-full border border-gray-300 rounded-lg px-3 py-2 bg-gray-50 whitespace-pre-wrap font-mono text-xs min-h-[100px] max-h-[300px] overflow-y-auto">
                {response}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
