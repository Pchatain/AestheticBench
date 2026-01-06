import { useState, useEffect } from 'react'
import {
  fetchVersions,
  fetchVersionFiles,
  fetchPromptsFiles,
  fetchGraders,
  validateGraders,
  estimateRun,
  estimateGrading,
  startRun,
  startGrading,
  getJobStatus,
  cancelJob,
} from '../api'
import type {
  VersionInfo,
  ResponseFileInfo,
  PromptsFileInfo,
  GraderInfo,
  DryRunEstimateResponse,
  GradingEstimateResponse,
  JobStatus,
} from '../types'
import { ModelPicker } from './ModelPicker'

type Step = 'mode' | 'configure' | 'dry-run' | 'execute'
type Mode = 'run' | 'grade' | null

export function CommandCenter() {
  const [step, setStep] = useState<Step>('mode')
  const [mode, setMode] = useState<Mode>(null)

  // Discovery data
  const [versions, setVersions] = useState<VersionInfo[]>([])
  const [promptsFiles, setPromptsFiles] = useState<PromptsFileInfo[]>([])
  const [graders, setGraders] = useState<GraderInfo[]>([])
  const [versionFiles, setVersionFiles] = useState<ResponseFileInfo[]>([])

  // Run config
  const [selectedPromptsFile, setSelectedPromptsFile] = useState('')
  const [selectedModels, setSelectedModels] = useState<string[]>([])

  // Grade config
  const [selectedVersion, setSelectedVersion] = useState('')
  const [selectedFiles, setSelectedFiles] = useState<string[]>([])
  const [selectedGraders, setSelectedGraders] = useState<string[]>([])
  const [graderModel, setGraderModel] = useState('openai/gpt-4o')

  // Estimates
  const [runEstimate, setRunEstimate] = useState<DryRunEstimateResponse | null>(null)
  const [gradeEstimate, setGradeEstimate] = useState<GradingEstimateResponse | null>(null)

  // Job state
  const [jobId, setJobId] = useState<string | null>(null)
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null)

  // UI state
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [warnings, setWarnings] = useState<string[]>([])

  // Load initial data
  useEffect(() => {
    Promise.all([
      fetchVersions(),
      fetchPromptsFiles(),
      fetchGraders(),
    ]).then(([versionsRes, promptsRes, gradersRes]) => {
      setVersions(versionsRes.versions)
      setPromptsFiles(promptsRes.files)
      setGraders(gradersRes.graders)
    }).catch(err => setError(err.message))
  }, [])

  // Load version files when version selected
  useEffect(() => {
    if (selectedVersion) {
      fetchVersionFiles(selectedVersion)
        .then(res => setVersionFiles(res.files))
        .catch(err => setError(err.message))
    } else {
      setVersionFiles([])
    }
  }, [selectedVersion])

  const handleModeSelect = (m: Mode) => {
    setMode(m)
    setStep('configure')
    setError(null)
    setWarnings([])
  }

  const handleBack = () => {
    if (step === 'configure') {
      setStep('mode')
      setMode(null)
    } else if (step === 'dry-run') {
      setStep('configure')
      setRunEstimate(null)
      setGradeEstimate(null)
    } else if (step === 'execute') {
      setStep('dry-run')
    }
  }

  const handleDryRun = async () => {
    setLoading(true)
    setError(null)
    setWarnings([])

    try {
      if (mode === 'run') {
        if (!selectedModels.length) {
          throw new Error('Please select at least one model')
        }
        if (!selectedPromptsFile) {
          throw new Error('Please select a prompts file')
        }
        const estimate = await estimateRun(selectedModels, selectedPromptsFile)
        setRunEstimate(estimate)
        if (estimate.invalid_models.length > 0) {
          setWarnings([`Unavailable models: ${estimate.invalid_models.join(', ')}`])
        }
      } else if (mode === 'grade') {
        if (!selectedFiles.length) {
          throw new Error('Please select at least one file to grade')
        }
        if (!selectedGraders.length) {
          throw new Error('Please select at least one grader')
        }
        // Validate graders first
        const validation = await validateGraders(selectedGraders)
        if (!validation.valid) {
          throw new Error(validation.errors.join(', '))
        }
        if (validation.warnings.length) {
          setWarnings(validation.warnings)
        }
        const estimate = await estimateGrading(
          selectedFiles,
          validation.grader_ids,
          graderModel
        )
        setGradeEstimate(estimate)
      }
      setStep('dry-run')
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setLoading(false)
    }
  }

  const handleExecute = async () => {
    setLoading(true)
    setError(null)
    setStep('execute')

    try {
      let response
      if (mode === 'run') {
        response = await startRun(selectedModels, selectedPromptsFile)
      } else {
        response = await startGrading(
          selectedFiles,
          selectedGraders,
          graderModel
        )
      }

      setJobId(response.job_id)
      // Start polling for status
      pollJobStatus(response.job_id)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setLoading(false)
    }
  }

  const pollJobStatus = async (id: string) => {
    try {
      const status = await getJobStatus(id)
      setJobStatus(status)

      if (status.status === 'pending' || status.status === 'running') {
        // Continue polling
        setTimeout(() => pollJobStatus(id), 1000)
      } else {
        setLoading(false)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
      setLoading(false)
    }
  }

  const handleCancelJob = async () => {
    if (!jobId) return
    try {
      await cancelJob(jobId)
      setJobStatus(prev => prev ? { ...prev, status: 'failed', error: 'Cancelled by user' } : null)
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    }
  }

  const toggleFileSelection = (path: string) => {
    setSelectedFiles(prev =>
      prev.includes(path)
        ? prev.filter(p => p !== path)
        : [...prev, path]
    )
  }

  const toggleGraderSelection = (id: string) => {
    setSelectedGraders(prev =>
      prev.includes(id)
        ? prev.filter(g => g !== id)
        : [...prev, id]
    )
  }

  const selectAllFiles = () => {
    setSelectedFiles(versionFiles.map(f => f.path))
  }

  const deselectAllFiles = () => {
    setSelectedFiles([])
  }

  return (
    <div className="max-w-4xl mx-auto">
      <h2 className="text-2xl font-bold mb-6">Command Center</h2>

      {/* Progress indicator */}
      <div className="flex items-center gap-2 mb-8">
        {(['mode', 'configure', 'dry-run', 'execute'] as Step[]).map((s, i) => (
          <div key={s} className="flex items-center">
            <div
              className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${
                step === s
                  ? 'bg-blue-600 text-white'
                  : i < ['mode', 'configure', 'dry-run', 'execute'].indexOf(step)
                  ? 'bg-green-600 text-white'
                  : 'bg-gray-300 text-gray-600'
              }`}
            >
              {i + 1}
            </div>
            {i < 3 && <div className="w-12 h-0.5 bg-gray-300" />}
          </div>
        ))}
      </div>

      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-4">
          {error}
        </div>
      )}

      {warnings.length > 0 && (
        <div className="bg-yellow-100 border border-yellow-400 text-yellow-700 px-4 py-3 rounded mb-4">
          {warnings.map((w, i) => <div key={i}>{w}</div>)}
        </div>
      )}

      {/* Step 1: Mode Selection */}
      {step === 'mode' && (
        <div className="space-y-4">
          <h3 className="text-lg font-semibold">Select Operation</h3>
          <div className="grid grid-cols-2 gap-4">
            <button
              onClick={() => handleModeSelect('run')}
              className="p-6 border-2 border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors text-left"
            >
              <div className="text-3xl mb-2">&#9654;</div>
              <div className="font-semibold text-lg">Run Inference</div>
              <div className="text-gray-600 text-sm mt-1">
                Send prompts to LLMs and collect responses
              </div>
            </button>
            <button
              onClick={() => handleModeSelect('grade')}
              className="p-6 border-2 border-gray-300 rounded-lg hover:border-blue-500 hover:bg-blue-50 transition-colors text-left"
            >
              <div className="text-3xl mb-2">&#9733;</div>
              <div className="font-semibold text-lg">Grade Responses</div>
              <div className="text-gray-600 text-sm mt-1">
                Evaluate LLM responses with graders
              </div>
            </button>
          </div>
        </div>
      )}

      {/* Step 2: Configuration */}
      {step === 'configure' && mode === 'run' && (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold">Configure Inference Run</h3>

          <div>
            <label className="block text-sm font-medium mb-2">Prompts File</label>
            <select
              value={selectedPromptsFile}
              onChange={(e) => setSelectedPromptsFile(e.target.value)}
              className="w-full p-2 border rounded"
            >
              <option value="">Select a prompts file...</option>
              {promptsFiles.map(f => (
                <option key={f.path} value={f.path}>
                  {f.filename} ({f.prompt_count} prompts)
                </option>
              ))}
            </select>
          </div>

          <ModelPicker
            selectedModels={selectedModels}
            onModelsChange={setSelectedModels}
          />

          <div className="flex gap-2">
            <button
              onClick={handleBack}
              className="px-4 py-2 border rounded hover:bg-gray-100"
            >
              Back
            </button>
            <button
              onClick={handleDryRun}
              disabled={loading || !selectedPromptsFile || !selectedModels.length}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Estimating...' : 'Estimate Costs'}
            </button>
          </div>
        </div>
      )}

      {step === 'configure' && mode === 'grade' && (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold">Configure Grading Run</h3>

          <div>
            <label className="block text-sm font-medium mb-2">Results Version</label>
            <select
              value={selectedVersion}
              onChange={(e) => {
                setSelectedVersion(e.target.value)
                setSelectedFiles([])
              }}
              className="w-full p-2 border rounded"
            >
              <option value="">Select a version...</option>
              {versions.map(v => (
                <option key={v.name} value={v.name}>
                  {v.name} ({v.response_count} responses, {v.grade_count} grades)
                </option>
              ))}
            </select>
          </div>

          {selectedVersion && versionFiles.length > 0 && (
            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="block text-sm font-medium">Response Files</label>
                <div className="space-x-2">
                  <button
                    onClick={selectAllFiles}
                    className="text-sm text-blue-600 hover:underline"
                  >
                    Select All
                  </button>
                  <button
                    onClick={deselectAllFiles}
                    className="text-sm text-gray-600 hover:underline"
                  >
                    Deselect All
                  </button>
                </div>
              </div>
              <div className="border rounded max-h-48 overflow-y-auto">
                {versionFiles.map(f => (
                  <label
                    key={f.path}
                    className="flex items-center p-2 hover:bg-gray-50 cursor-pointer"
                  >
                    <input
                      type="checkbox"
                      checked={selectedFiles.includes(f.path)}
                      onChange={() => toggleFileSelection(f.path)}
                      className="mr-3"
                    />
                    <div className="flex-1">
                      <div className="text-sm font-medium">{f.model}</div>
                      <div className="text-xs text-gray-500">
                        {f.response_count} responses - {f.date} - {f.size}
                      </div>
                    </div>
                  </label>
                ))}
              </div>
            </div>
          )}

          <div>
            <label className="block text-sm font-medium mb-2">Graders</label>
            <div className="space-y-2">
              {graders.map(g => (
                <label
                  key={g.id}
                  className="flex items-start p-3 border rounded hover:bg-gray-50 cursor-pointer"
                >
                  <input
                    type="checkbox"
                    checked={selectedGraders.includes(g.id)}
                    onChange={() => toggleGraderSelection(g.id)}
                    className="mr-3 mt-1"
                  />
                  <div>
                    <div className="font-medium">{g.name}</div>
                    <div className="text-sm text-gray-600">{g.description}</div>
                    <div className="text-xs text-gray-400">Score range: {g.score_range}</div>
                    {g.dependencies.length > 0 && (
                      <div className="text-xs text-yellow-600">
                        Requires: {g.dependencies.join(', ')}
                      </div>
                    )}
                  </div>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="block text-sm font-medium mb-2">Grader Model</label>
            <input
              type="text"
              value={graderModel}
              onChange={(e) => setGraderModel(e.target.value)}
              className="w-full p-2 border rounded font-mono text-sm"
              placeholder="openai/gpt-4o"
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleBack}
              className="px-4 py-2 border rounded hover:bg-gray-100"
            >
              Back
            </button>
            <button
              onClick={handleDryRun}
              disabled={loading || !selectedFiles.length || !selectedGraders.length}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {loading ? 'Estimating...' : 'Estimate Costs'}
            </button>
          </div>
        </div>
      )}

      {/* Step 3: Dry Run Results */}
      {step === 'dry-run' && mode === 'run' && runEstimate && (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold">Inference Cost Estimate</h3>

          <div className="bg-gray-50 p-4 rounded">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Prompts:</span>
                <span className="ml-2 font-medium">{runEstimate.prompts_count}</span>
              </div>
              <div>
                <span className="text-gray-600">Input Tokens:</span>
                <span className="ml-2 font-medium">{runEstimate.total_input_tokens.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-600">Valid Models:</span>
                <span className="ml-2 font-medium">{runEstimate.valid_models.length}</span>
              </div>
              <div>
                <span className="text-gray-600">Invalid Models:</span>
                <span className="ml-2 font-medium text-red-600">{runEstimate.invalid_models.length}</span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium mb-2">Model Breakdown</h4>
            <div className="border rounded overflow-hidden">
              <table className="w-full text-sm">
                <thead className="bg-gray-100">
                  <tr>
                    <th className="text-left p-2">Model</th>
                    <th className="text-right p-2">Input $/M</th>
                    <th className="text-right p-2">Output $/M</th>
                    <th className="text-right p-2">Est. Cost</th>
                  </tr>
                </thead>
                <tbody>
                  {runEstimate.models.map(m => (
                    <tr key={m.model} className={m.available ? '' : 'bg-red-50'}>
                      <td className="p-2">
                        {m.model}
                        {!m.available && <span className="text-red-500 ml-2">(unavailable)</span>}
                      </td>
                      <td className="text-right p-2">{m.input_cost_per_m?.toFixed(2) ?? '-'}</td>
                      <td className="text-right p-2">{m.output_cost_per_m?.toFixed(2) ?? '-'}</td>
                      <td className="text-right p-2">
                        {m.estimated_min_cost != null
                          ? `$${m.estimated_min_cost.toFixed(4)} - $${m.estimated_max_cost?.toFixed(4)}`
                          : '-'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="bg-blue-50 p-4 rounded text-center">
            <div className="text-sm text-gray-600">Estimated Total Cost</div>
            <div className="text-2xl font-bold text-blue-700">
              ${runEstimate.total_min_cost.toFixed(4)} - ${runEstimate.total_max_cost.toFixed(4)}
            </div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleBack}
              className="px-4 py-2 border rounded hover:bg-gray-100"
            >
              Back
            </button>
            <button
              onClick={handleExecute}
              disabled={runEstimate.valid_models.length === 0}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50"
            >
              Start Inference
            </button>
          </div>
        </div>
      )}

      {step === 'dry-run' && mode === 'grade' && gradeEstimate && (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold">Grading Cost Estimate</h3>

          <div className="bg-gray-50 p-4 rounded">
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Files:</span>
                <span className="ml-2 font-medium">{gradeEstimate.files.length}</span>
              </div>
              <div>
                <span className="text-gray-600">Total Responses:</span>
                <span className="ml-2 font-medium">{gradeEstimate.total_responses}</span>
              </div>
              <div>
                <span className="text-gray-600">Graders:</span>
                <span className="ml-2 font-medium">{gradeEstimate.graders.join(', ')}</span>
              </div>
              <div>
                <span className="text-gray-600">Total Grading Calls:</span>
                <span className="ml-2 font-medium">{gradeEstimate.total_grading_calls}</span>
              </div>
              <div>
                <span className="text-gray-600">Est. Input Tokens:</span>
                <span className="ml-2 font-medium">{gradeEstimate.estimated_input_tokens.toLocaleString()}</span>
              </div>
              <div>
                <span className="text-gray-600">Est. Output Tokens:</span>
                <span className="ml-2 font-medium">{gradeEstimate.estimated_output_tokens.toLocaleString()}</span>
              </div>
            </div>
          </div>

          <div>
            <h4 className="font-medium mb-2">Files to Grade</h4>
            <div className="border rounded max-h-32 overflow-y-auto">
              {gradeEstimate.files.map(f => (
                <div key={f.path} className="p-2 border-b last:border-b-0 text-sm">
                  <span className="font-medium">{f.filename}</span>
                  <span className="text-gray-500 ml-2">({f.response_count} responses)</span>
                </div>
              ))}
            </div>
          </div>

          <div className="bg-blue-50 p-4 rounded text-center">
            <div className="text-sm text-gray-600">Grader Model</div>
            <div className="font-medium">{gradeEstimate.grader_model}</div>
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleBack}
              className="px-4 py-2 border rounded hover:bg-gray-100"
            >
              Back
            </button>
            <button
              onClick={handleExecute}
              className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700"
            >
              Start Grading
            </button>
          </div>
        </div>
      )}

      {/* Step 4: Execute */}
      {step === 'execute' && (
        <div className="space-y-6">
          <h3 className="text-lg font-semibold">
            {mode === 'run' ? 'Running Inference' : 'Running Grading'}
          </h3>

          {/* Job Progress */}
          {jobStatus && (
            <div className="space-y-4">
              {/* Status Badge */}
              <div className="flex items-center gap-3">
                <span className="text-sm text-gray-600">Status:</span>
                <span
                  className={`px-3 py-1 rounded-full text-sm font-medium ${
                    jobStatus.status === 'completed'
                      ? 'bg-green-100 text-green-800'
                      : jobStatus.status === 'failed'
                      ? 'bg-red-100 text-red-800'
                      : jobStatus.status === 'running'
                      ? 'bg-blue-100 text-blue-800'
                      : 'bg-gray-100 text-gray-800'
                  }`}
                >
                  {jobStatus.status.charAt(0).toUpperCase() + jobStatus.status.slice(1)}
                </span>
                {jobId && (
                  <span className="text-xs text-gray-400">Job ID: {jobId}</span>
                )}
              </div>

              {/* Progress Bar */}
              {(jobStatus.status === 'running' || jobStatus.status === 'pending') && (
                <div>
                  <div className="flex justify-between text-sm mb-1">
                    <span>{jobStatus.current_step || 'Starting...'}</span>
                    <span>{Math.round(jobStatus.progress * 100)}%</span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className="bg-blue-600 h-3 rounded-full transition-all duration-300"
                      style={{ width: `${jobStatus.progress * 100}%` }}
                    />
                  </div>
                  {jobStatus.total_steps && (
                    <div className="text-xs text-gray-500 mt-1">
                      Step {(jobStatus.current_step_index ?? 0) + 1} of {jobStatus.total_steps}
                    </div>
                  )}
                </div>
              )}

              {/* Error Display */}
              {jobStatus.status === 'failed' && jobStatus.error && (
                <div className="bg-red-50 border border-red-300 p-4 rounded">
                  <div className="font-medium text-red-800">Error:</div>
                  <div className="text-red-700 text-sm mt-1">{jobStatus.error}</div>
                </div>
              )}

              {/* Success Display */}
              {jobStatus.status === 'completed' && jobStatus.result && (
                <div className="bg-green-50 border border-green-300 p-4 rounded">
                  <div className="font-medium text-green-800 mb-2">Completed Successfully!</div>
                  {jobStatus.result.outputs && Array.isArray(jobStatus.result.outputs) && (
                    <div className="text-sm text-green-700">
                      <div className="font-medium">Output files:</div>
                      <ul className="mt-1 space-y-1">
                        {(jobStatus.result.outputs as Array<{model?: string; output_file?: string; input_file?: string}>).map((output, i) => (
                          <li key={i} className="font-mono text-xs">
                            {output.model || output.input_file}: {output.output_file}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* Loading state before job starts */}
          {!jobStatus && loading && (
            <div className="text-center py-8">
              <div className="animate-spin w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4" />
              <div className="text-gray-600">Starting job...</div>
            </div>
          )}

          <div className="flex gap-2">
            {(jobStatus?.status === 'running' || jobStatus?.status === 'pending') && (
              <button
                onClick={handleCancelJob}
                className="px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
              >
                Cancel Job
              </button>
            )}
            <button
              onClick={() => {
                setStep('mode')
                setMode(null)
                setRunEstimate(null)
                setGradeEstimate(null)
                setSelectedFiles([])
                setSelectedGraders([])
                setSelectedModels([])
                setSelectedPromptsFile('')
                setSelectedVersion('')
                setJobId(null)
                setJobStatus(null)
              }}
              className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-700"
              disabled={loading && (jobStatus?.status === 'running' || jobStatus?.status === 'pending')}
            >
              Start Over
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
