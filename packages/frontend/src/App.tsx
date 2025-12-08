import { useEffect, useState, useCallback } from 'react'
import { Sidebar } from './components/Sidebar'
import { FilterBar } from './components/FilterBar'
import { ResultsTable } from './components/ResultsTable'
import { ModelComparison } from './components/ModelComparison'
import { Playground } from './components/Playground'
import { fetchModels, fetchTopics, fetchResults, fetchHeaders } from './api'
import type { Model, Result } from './types'

function App() {
  const [currentPage, setCurrentPage] = useState('results')
  const [models, setModels] = useState<Model[]>([])
  const [topics, setTopics] = useState<string[]>([])
  const [results, setResults] = useState<Result[]>([])
  const [headers, setHeaders] = useState<string[]>([])
  const [loading, setLoading] = useState(true)

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
      <main className="flex-1 p-6">
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
        {currentPage === 'comparison' && <ModelComparison />}
        {currentPage === 'playground' && <Playground />}
      </main>
    </div>
  )
}

export default App
