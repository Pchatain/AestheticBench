import { useState, useMemo, useEffect } from 'react'
import { runPrompt } from '../api'

const AVAILABLE_MODELS = [
  'anthropic/claude-sonnet-4.5',
  'deepseek/deepseek-chat-v3-0324',
  'deepseek/deepseek-chat-v3.1',
  'deepseek/deepseek-v3.2-exp',
  'google/gemini-2.5-pro',
  'meta-llama/llama-3.1-405b-instruct',
  'mistralai/mistral-nemo',
  'openai/gpt-5',
  'openai/gpt-4o',
  'openai/gpt-4o-mini',
  'openai/gpt-oss-20b',
  'qwen/qwen3-235b-a22b-2507',
  'x-ai/grok-4-fast',
  'z-ai/glm-4.6',
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

PROMPT: {paste_question_here}

RESPONSE: {paste_response_here}

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

PROMPT: {paste_question_here}

RESPONSE: {paste_response_here}

Please provide only your numerical score based on the grading criteria above.`,
  },
  justification: {
    label: 'Justification (1-5 scale) [requires preference1]',
    prompt: `The following prompt-response pair evaluates two comparable items (art, artists, historical figures, or natural objects). The model expressed a preference score (provided below).

Evaluate on a 5-point scale how well the response justifies its stated preference:

EVALUATION CRITERIA:
1. FACTUAL DEPTH: Does the model bring to bear important, relevant facts about the subject matter? Consider historical context, aesthetic qualities, cultural significance, or principles of human flourishing.

2. SPECIFICITY: How specific and detailed is the justification? Vague generalities score lower; concrete, precise observations score higher.

3. SYNTHESIS & JUDGMENT: Does the model effectively synthesize the facts to reach a coherent conclusion? The evidence presented should logically support the preference expressed.

4. CONSISTENCY: The conclusion must be consistent with the evidence presented:
   - If expressing a clear preference (score != 0), the facts should support that direction
   - If expressing ambivalence (score = 0), the evidence should genuinely be balanced
   - A mismatch between evidence and conclusion is a significant flaw

SCORING GUIDE:
1 = Very poor: Lacks substance, vague, or conclusion contradicts the evidence
2 = Poor: Some facts but shallow, weak synthesis, or notable inconsistencies
3 = Adequate: Reasonable facts and logic, but lacks depth or has minor coherence issues
4 = Good: Strong factual basis, specific details, evidence clearly supports conclusion
5 = Excellent: Expert-level analysis with strong coherence throughout (difficult to achieve)

MODEL'S PREFERENCE SCORE: {paste_preference_score_here}

PROMPT: {paste_question_here}

RESPONSE: {paste_response_here}

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
  const [templateValues, setTemplateValues] = useState<Record<string, string>>({})

  // Extract template variables like {variable_name} from the prompt
  const templateVariables = useMemo(() => {
    const regex = /\{([^}]+)\}/g
    const matches: string[] = []
    let match
    while ((match = regex.exec(prompt)) !== null) {
      if (!matches.includes(match[1])) {
        matches.push(match[1])
      }
    }
    return matches
  }, [prompt])

  // Reset template values when variables change
  useEffect(() => {
    setTemplateValues((prev) => {
      const newValues: Record<string, string> = {}
      templateVariables.forEach((varName) => {
        newValues[varName] = prev[varName] || ''
      })
      return newValues
    })
  }, [templateVariables])

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
      // Substitute template variables with their values
      let finalPrompt = prompt
      templateVariables.forEach((varName) => {
        const value = templateValues[varName] || ''
        finalPrompt = finalPrompt.replace(new RegExp(`\\{${varName}\\}`, 'g'), value)
      })

      const result = await runPrompt(finalPrompt, model)
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
            <input
              type="text"
              list="model-options"
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="Type or select a model..."
              className="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <datalist id="model-options">
              {AVAILABLE_MODELS.map((m) => (
                <option key={m} value={m} />
              ))}
            </datalist>
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
              placeholder="Enter your prompt here... Use {variable_name} for template variables."
              rows={10}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
            />
          </div>

          {templateVariables.length > 0 && (
            <div className="space-y-3">
              <label className="block text-sm font-medium text-gray-700">
                Template Variables
              </label>
              {templateVariables.map((varName) => (
                <div key={varName}>
                  <label className="block text-xs text-gray-500 mb-1">
                    {varName}
                  </label>
                  <textarea
                    value={templateValues[varName] || ''}
                    onChange={(e) =>
                      setTemplateValues((prev) => ({
                        ...prev,
                        [varName]: e.target.value,
                      }))
                    }
                    placeholder={`Enter value for {${varName}}`}
                    rows={3}
                    className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500 font-mono text-xs"
                  />
                </div>
              ))}
            </div>
          )}

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
