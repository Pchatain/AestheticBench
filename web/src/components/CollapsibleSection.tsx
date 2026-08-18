import React from 'react'
import { useCollapsibleState } from '../hooks/useCollapsibleState'

interface CollapsibleSectionProps {
  id: string
  title: string
  subtitle?: string
  defaultExpanded?: boolean
  children: React.ReactNode
}

export const CollapsibleSection: React.FC<CollapsibleSectionProps> = ({
  id,
  title,
  subtitle,
  defaultExpanded = true,
  children,
}) => {
  const [isExpanded, toggleExpanded] = useCollapsibleState(id, defaultExpanded)

  return (
    <div className="bg-white rounded-lg shadow p-4 mb-4">
      <button
        onClick={toggleExpanded}
        className="w-full flex items-center justify-between text-left hover:bg-gray-50 p-2 rounded transition-colors duration-200"
        aria-expanded={isExpanded}
        aria-controls={`${id}-content`}
      >
        <div className="flex-1">
          <h3 className="text-lg font-semibold text-gray-900">{title}</h3>
          {subtitle && (
            <p className="text-sm text-gray-500 mt-1">{subtitle}</p>
          )}
        </div>
        <div className="ml-4 flex-shrink-0">
          <span
            className="inline-block transition-transform duration-300 ease-in-out text-gray-600"
            style={{
              transform: isExpanded ? 'rotate(0deg)' : 'rotate(-90deg)',
            }}
          >
            ▼
          </span>
        </div>
      </button>
      <div
        id={`${id}-content`}
        className="transition-all duration-300 ease-in-out overflow-hidden"
        style={{
          maxHeight: isExpanded ? '10000px' : '0',
          opacity: isExpanded ? 1 : 0,
        }}
      >
        <div className="pt-4">{children}</div>
      </div>
    </div>
  )
}
