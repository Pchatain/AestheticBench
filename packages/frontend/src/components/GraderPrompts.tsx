import { useEffect, useState } from 'react'
import { fetchGraderPrompts } from '../api'
import type { GraderPrompt } from '../types'

export function GraderPrompts() {
  const [prompts, setPrompts] = useState<GraderPrompt[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    fetchGraderPrompts()
      .then((res) => {
        setPrompts(res.prompts)
        setLoading(false)
      })
      .catch((err) => {
        setError(err.message || 'Failed to fetch grader prompts')
        setLoading(false)
      })
  }, [])

  if (loading) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-4">Grader Prompts</h2>
        <p className="text-gray-500">Loading prompts...</p>
      </div>
    )
  }

  if (error) {
    return (
      <div>
        <h2 className="text-2xl font-bold mb-4">Grader Prompts</h2>
        <p className="text-red-500">Error: {error}</p>
      </div>
    )
  }

  return (
    <div>
      <h2 className="text-2xl font-bold mb-4">Grader Prompts</h2>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {prompts.map((prompt) => (
          <div key={prompt.id} className="border rounded-lg p-4 bg-white shadow-sm">
            <h3 className="text-lg font-semibold mb-2">{prompt.title}</h3>
            <pre className="whitespace-pre-wrap text-sm text-gray-800">{prompt.prompt}</pre>
          </div>
        ))}
      </div>
    </div>
  )
}
