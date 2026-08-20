import { useEffect } from 'react'
import type { HeatmapEntry } from '../types'

interface ResponseModalProps {
  entry: HeatmapEntry
  onClose: () => void
}

const QUESTION_LABELS: Record<string, string> = {
  q1: 'Q1 Relativism',
  q2: 'Q2 Preference',
  q3: 'Q3 Evidence',
  q4: 'Q4 Justification',
  q4_1: 'Q4.1 Factual Depth',
  q4_2: 'Q4.2 Specificity',
  q4_3: 'Q4.3 Synthesis',
  q4_4: 'Q4.4 Consistency',
}

export function ResponseModal({ entry, onClose }: ResponseModalProps) {
  useEffect(() => {
    const handleEsc = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handleEsc)
    return () => window.removeEventListener('keydown', handleEsc)
  }, [onClose])

  const grades = (['q1', 'q2', 'q3', 'q4', 'q4_1', 'q4_2', 'q4_3', 'q4_4'] as const).map(
    (key) => ({
      label: QUESTION_LABELS[key],
      value: entry[key],
    })
  )

  return (
    <div
      className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-lg shadow-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="sticky top-0 bg-white border-b px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="text-lg font-bold">{entry.model}</h3>
            <span className="text-sm text-gray-500">
              UID {entry.uid} &middot; {entry.topic}
            </span>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-gray-600 text-2xl leading-none"
          >
            &times;
          </button>
        </div>

        <div className="px-6 py-4 space-y-4">
          <div>
            <h4 className="text-sm font-semibold text-gray-500 uppercase mb-1">Prompt</h4>
            <p className="text-sm bg-gray-50 p-3 rounded whitespace-pre-wrap">{entry.question}</p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-500 uppercase mb-1">Response</h4>
            <p className="text-sm bg-gray-50 p-3 rounded whitespace-pre-wrap max-h-64 overflow-y-auto">
              {entry.response}
            </p>
          </div>

          <div>
            <h4 className="text-sm font-semibold text-gray-500 uppercase mb-1">Grades</h4>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {grades.map((g) => (
                <div key={g.label} className="bg-gray-50 p-2 rounded text-center">
                  <div className="text-xs text-gray-500">{g.label}</div>
                  <div className="text-lg font-bold">
                    {g.value !== null && g.value !== undefined ? g.value : '-'}
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
