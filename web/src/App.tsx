import { useEffect, useState, useCallback } from 'react'
import { Sidebar } from './components/Sidebar'
import { FilterBar } from './components/FilterBar'
import { ResultsTable } from './components/ResultsTable'
import { ModelComparison } from './components/ModelComparison'
import { Analytics } from './components/Analytics'
import { PlaygroundSidebar } from './components/Playground'
import { GraderPrompts } from './components/GraderPrompts'
import { Annotator } from './components/Annotator'
import { Q1Q4Annotator } from './components/Q1Q4Annotator'
import { CommandCenter } from './components/CommandCenter'
import { JustificationExperiment } from './components/JustificationExperiment'
import { GradeExplorer } from './components/GradeExplorer'
import { fetchModels, fetchTopics, fetchResults, fetchHeaders } from './api'
import type { Model, Result } from './types'

function App() {
  const [currentPage, setCurrentPage] = useState('results')
  const [models, setModels] = useState<Model[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const [results, setResults] = useState<Result[]>([])
  const [headers, setHeaders] = useState<string[]>([])
  const [loading, setLoading] = useState(true)
  const [isPlaygroundOpen, setIsPlaygroundOpen] = useState(false)

  const [selectedModel, setSelectedModel] = useState('')
  const [selectedTopic, setSelectedTopic] = useState('')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    fetchModels().then((data) => setModels(data.models))
    fetchHeaders().then((data) => setHeaders(data.headers))
  }, [])

  useEffect(() => {
    fetchTopics(selectedModel || undefined).then((data) => setTopics(data.topics))
  }, [selectedModel])

  const loadResults = useCallback(async () => {
    setLoading(true)
    const data = await fetchResults({
      model: selectedModel || undefined,
      topic: selectedTopic || undefined,
      search: searchQuery || undefined,
    })
    setResults(data.results)
    if (data.headers && data.headers.length > 0) {
      setHeaders(data.headers)
    }
    setLoading(false)
  }, [selectedModel, selectedTopic, searchQuery])

  useEffect(() => {
    const debounce = setTimeout(loadResults, 300)
    return () => clearTimeout(debounce)
  }, [loadResults])

  return (
    <div className="flex min-h-screen">
      <Sidebar currentPage={currentPage} onPageChange={setCurrentPage} />
      <main className={`flex-1 p-6 transition-all duration-300 ${isPlaygroundOpen ? 'mr-[400px]' : ''}`}>
        {currentPage === 'results' && (
          <>
            <h2 className="text-2xl font-bold mb-4">Sample Viewer</h2>
            <FilterBar
              models={models}
              topics={topics}
              selectedModel={selectedModel}
              selectedTopic={selectedTopic}
              searchQuery={searchQuery}
              onModelChange={setSelectedModel}
              onTopicChange={setSelectedTopic}
              onSearchChange={setSearchQuery}
            />
            <ResultsTable results={results} headers={headers} loading={loading} />
          </>
        )}
        {currentPage === 'command-center' && <CommandCenter />}
        {currentPage === 'annotator' && <Annotator />}
        {currentPage === 'q1q4-annotator' && <Q1Q4Annotator />}
        {currentPage === 'grade-explorer' && <GradeExplorer />}
        {currentPage === 'comparison' && <ModelComparison />}
        {currentPage === 'analytics' && <Analytics />}
        {currentPage === 'experiment' && <JustificationExperiment />}
        {currentPage === 'prompts' && <GraderPrompts />}
      </main>

      {/* Floating Playground Button */}
      {!isPlaygroundOpen && (
        <button
          onClick={() => setIsPlaygroundOpen(true)}
          className="fixed bottom-6 right-6 w-14 h-14 bg-blue-600 hover:bg-blue-700 text-white rounded-full shadow-lg flex items-center justify-center text-2xl transition-all hover:scale-110 z-40"
          title="Open Playground"
        >
          🧪
        </button>
      )}

      <PlaygroundSidebar
        isOpen={isPlaygroundOpen}
        onClose={() => setIsPlaygroundOpen(false)}
      />
    </div>
  )
}

export default App
