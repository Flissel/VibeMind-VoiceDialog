import { useState, useEffect, useCallback } from 'react'
import type { ProjectInfo } from '../types'
import { useProjects, usePythonMessages } from '../hooks/useIPC'

const api = typeof window !== 'undefined' ? (window as any).vibemindAgentFarm : null

/* ── Progress stage definitions (matching Coding Engine) ── */
const STAGES = [
  { name: 'Analyzing Requirements', threshold: 10 },
  { name: 'Generating Code', threshold: 40 },
  { name: 'Running Validators', threshold: 60 },
  { name: 'Building Project', threshold: 80 },
  { name: 'Running Tests', threshold: 95 },
  { name: 'Complete', threshold: 100 },
]

function getCurrentStage(progress: number) {
  return STAGES.find(s => progress < s.threshold) || STAGES[STAGES.length - 1]
}

/* ── Stage icon SVGs (inline to avoid dependency) ── */
function CheckIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="8" fill="var(--system-green)" opacity="0.15" />
      <path d="M4.5 8.5L7 11L11.5 5.5" stroke="var(--system-green)" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function SpinnerIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ animation: 'spin 1s linear infinite' }}>
      <circle cx="8" cy="8" r="6" stroke="var(--system-yellow)" strokeWidth="2" opacity="0.25" />
      <path d="M8 2a6 6 0 0 1 6 6" stroke="var(--system-yellow)" strokeWidth="2" strokeLinecap="round" />
    </svg>
  )
}

function EmptyCircle() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke="var(--fill-secondary)" strokeWidth="1.5" />
    </svg>
  )
}

/* ── Progress view for a single project ── */
function ProgressView({ progress, status }: { progress: number; status: string }) {
  const currentStage = getCurrentStage(progress)
  const isGenerating = status === 'generating'
  const isComplete = progress >= 100

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
      {/* Overall progress bar */}
      <div>
        <div className="flex justify-between items-center" style={{ marginBottom: 'var(--space-2)' }}>
          <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-secondary)' }}>
            Overall Progress
          </span>
          <span style={{
            fontSize: 'var(--text-footnote)',
            fontWeight: 'var(--weight-semibold)' as any,
            color: isComplete ? 'var(--system-green)' : 'var(--accent)',
          }}>
            {Math.round(progress)}%
          </span>
        </div>
        <div style={{
          height: 6,
          background: 'var(--fill-quaternary)',
          borderRadius: 3,
          overflow: 'hidden',
        }}>
          <div style={{
            height: '100%',
            width: `${Math.min(progress, 100)}%`,
            background: isComplete
              ? 'var(--system-green)'
              : 'linear-gradient(90deg, var(--accent), var(--system-teal))',
            borderRadius: 3,
            transition: 'width 500ms var(--ease-smooth)',
          }} />
        </div>
      </div>

      {/* Current stage card */}
      <div style={{
        display: 'flex',
        alignItems: 'center',
        gap: 'var(--space-3)',
        padding: 'var(--space-3) var(--space-4)',
        background: 'var(--bg-secondary)',
        borderRadius: 'var(--radius-md)',
        border: '1px solid var(--separator)',
      }}>
        {isGenerating ? (
          <SpinnerIcon />
        ) : isComplete ? (
          <CheckIcon />
        ) : (
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="6" stroke="var(--text-tertiary)" strokeWidth="1.5" />
            <path d="M8 5v3.5l2.5 1.5" stroke="var(--text-tertiary)" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        )}
        <div>
          <div style={{
            fontSize: 'var(--text-footnote)',
            fontWeight: 'var(--weight-semibold)' as any,
            color: 'var(--text-primary)',
          }}>
            {currentStage.name}
          </div>
          <div style={{
            fontSize: 'var(--text-caption1)',
            color: 'var(--text-tertiary)',
          }}>
            {isGenerating ? 'In progress...' : isComplete ? 'Completed' : 'Waiting to start'}
          </div>
        </div>
      </div>

      {/* Stage checklist */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
        {STAGES.slice(0, -1).map(stage => {
          const isStageComplete = progress >= stage.threshold
          const isCurrent = currentStage === stage

          return (
            <div
              key={stage.name}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 'var(--space-3)',
                padding: 'var(--space-2) var(--space-3)',
                borderRadius: 'var(--radius-sm)',
                background: isCurrent ? 'var(--accent-fill)' : 'transparent',
                transition: 'background 200ms var(--ease-smooth)',
              }}
            >
              {isStageComplete ? <CheckIcon /> : isCurrent && isGenerating ? <SpinnerIcon /> : <EmptyCircle />}
              <span style={{
                fontSize: 'var(--text-footnote)',
                color: isStageComplete ? 'var(--text-primary)' : 'var(--text-tertiary)',
                fontWeight: isCurrent ? 'var(--weight-medium)' as any : 'var(--weight-regular)' as any,
              }}>
                {stage.name}
              </span>
            </div>
          )
        })}
      </div>
    </div>
  )
}

/* ── Project card in the sidebar list ── */
function ProjectCard({
  project,
  isSelected,
  onSelect,
}: {
  project: ProjectInfo
  isSelected: boolean
  onSelect: () => void
}) {
  const progress = project.convergence_progress ?? 0
  const statusColor =
    project.status === 'completed' ? 'var(--system-green)'
    : project.status === 'generating' ? 'var(--system-yellow)'
    : project.status === 'error' ? 'var(--system-red)'
    : 'var(--text-tertiary)'

  return (
    <button
      onClick={onSelect}
      className="focus-ring"
      style={{
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-1)',
        width: '100%',
        padding: 'var(--space-3) var(--space-4)',
        background: isSelected ? 'var(--accent-fill)' : 'transparent',
        border: 'none',
        borderRadius: 'var(--radius-md)',
        cursor: 'pointer',
        textAlign: 'left',
        transition: 'background 150ms var(--ease-smooth)',
      }}
    >
      <div className="flex items-center justify-between w-full">
        <span className="truncate" style={{
          fontSize: 'var(--text-footnote)',
          fontWeight: 'var(--weight-medium)' as any,
          color: 'var(--text-primary)',
          flex: 1,
          minWidth: 0,
        }}>
          {project.name}
        </span>
        <span style={{
          width: 8,
          height: 8,
          borderRadius: '50%',
          background: statusColor,
          flexShrink: 0,
          marginLeft: 'var(--space-2)',
        }} />
      </div>
      {/* Mini progress bar */}
      <div style={{
        height: 3,
        background: 'var(--fill-quaternary)',
        borderRadius: 2,
        overflow: 'hidden',
        width: '100%',
      }}>
        <div style={{
          height: '100%',
          width: `${Math.min(progress, 100)}%`,
          background: progress >= 100 ? 'var(--system-green)' : 'var(--accent)',
          borderRadius: 2,
          transition: 'width 300ms var(--ease-smooth)',
        }} />
      </div>
    </button>
  )
}

/* ── Pipeline Runs from Minibook ── */
interface PipelineRun {
  id: string
  name: string
  post_count: number
  last_agent?: string
  last_title?: string
}

function PipelineRunsSection() {
  const [runs, setRuns] = useState<PipelineRun[]>([])
  const [loading, setLoading] = useState(false)
  const [expanded, setExpanded] = useState(false)

  const refresh = useCallback(async () => {
    if (!api?.getPipelineRuns) return
    setLoading(true)
    try {
      const result = await api.getPipelineRuns()
      if (result?.success && result.runs) {
        setRuns(result.runs)
      }
    } catch { /* minibook not reachable */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return (
    <div style={{
      marginBottom: 'var(--space-4)',
      background: 'var(--bg-secondary)',
      border: '1px solid var(--separator)',
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-3)',
    }}>
      <div
        onClick={() => { setExpanded(!expanded); if (!expanded) refresh() }}
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', cursor: 'pointer' }}
      >
        <span style={{
          fontSize: 'var(--text-footnote)',
          fontWeight: 600,
          color: 'var(--text-primary)',
        }}>
          Pipeline Runs {loading ? '...' : `(${runs.length})`}
        </span>
        <span style={{ fontSize: 12, color: 'var(--text-tertiary)' }}>
          {expanded ? '▲' : '▼'}
        </span>
      </div>
      {expanded && (
        <div style={{ marginTop: 'var(--space-2)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
          {loading && <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>Lade Pipeline Runs von Minibook...</span>}
          {!loading && runs.length === 0 && (
            <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>
              Keine Pipeline Runs gefunden. Minibook auf localhost:3480 erreichbar?
            </span>
          )}
          {runs.map(run => (
            <div key={run.id} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: 'var(--space-2) var(--space-3)',
              borderRadius: 'var(--radius-sm)',
              background: run.post_count > 5 ? 'var(--accent-fill)' : 'transparent',
            }}>
              <div>
                <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-primary)' }}>
                  {run.name}
                </span>
                {run.last_agent && (
                  <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginLeft: 8 }}>
                    [{run.last_agent}] {run.last_title}
                  </span>
                )}
              </div>
              <span style={{
                fontSize: 'var(--text-caption2)',
                color: run.post_count > 5 ? 'var(--system-green)' : 'var(--text-tertiary)',
                fontWeight: 600,
              }}>
                {run.post_count} posts
              </span>
            </div>
          ))}
          <button
            onClick={() => window.open('http://localhost:3481/dashboard', '_blank')}
            style={{
              marginTop: 'var(--space-2)',
              border: '1px solid var(--separator)',
              background: 'var(--fill-tertiary)',
              color: 'var(--text-secondary)',
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              fontSize: 'var(--text-caption1)',
            }}
          >
            Open Minibook Dashboard
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Main component ── */
export function ProjectProgress() {
  const { data, loading, error, refresh } = useProjects()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [liveStatus, setLiveStatus] = useState<Record<string, { progress: number; status: string }>>({})

  const projects = data?.projects ?? []

  // Listen for live progress updates from Python
  usePythonMessages('project_status_update', useCallback((msg: any) => {
    if (msg.project_id) {
      setLiveStatus(prev => ({
        ...prev,
        [msg.project_id]: {
          progress: msg.progress ?? prev[msg.project_id]?.progress ?? 0,
          status: msg.status ?? prev[msg.project_id]?.status ?? 'idle',
        },
      }))
    }
  }, []))

  // Auto-refresh every 10 seconds
  useEffect(() => {
    const iv = setInterval(refresh, 10000)
    return () => clearInterval(iv)
  }, [refresh])

  // Auto-select first project if none selected
  useEffect(() => {
    if (!selectedId && projects.length > 0) {
      setSelectedId(projects[0].id)
    }
  }, [projects, selectedId])

  const selectedProject = projects.find(p => p.id === selectedId)
  const live = selectedId ? liveStatus[selectedId] : undefined
  const progress = live?.progress ?? selectedProject?.convergence_progress ?? 0
  const status = live?.status ?? selectedProject?.status ?? 'idle'

  if (loading && projects.length === 0) {
    return (
      <div className="flex items-center justify-center h-full" style={{ color: 'var(--text-tertiary)' }}>
        Loading projects...
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-full" style={{ color: 'var(--system-red)' }}>
        Error: {error}
      </div>
    )
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Pipeline Runs from Minibook */}
      <PipelineRunsSection />

    {projects.length === 0 ? (
      <div className="flex flex-col items-center justify-center" style={{ flex: 1, color: 'var(--text-tertiary)' }}>
        <span style={{ fontSize: 32 }}>&#128187;</span>
        <span style={{ fontSize: 'var(--text-footnote)' }}>No Coding Engine projects yet</span>
      </div>
    ) : (
    <div className="flex" style={{ gap: 'var(--space-4)', flex: 1, overflow: 'hidden' }}>
      {/* Project list sidebar */}
      <div style={{
        width: 220,
        flexShrink: 0,
        display: 'flex',
        flexDirection: 'column',
        gap: 'var(--space-1)',
        overflowY: 'auto',
        paddingRight: 'var(--space-2)',
      }}>
        <div className="flex items-center justify-between" style={{ padding: '0 var(--space-3)', marginBottom: 'var(--space-2)' }}>
          <span style={{
            fontSize: 'var(--text-caption1)',
            fontWeight: 'var(--weight-semibold)' as any,
            color: 'var(--text-secondary)',
            textTransform: 'uppercase',
            letterSpacing: 'var(--tracking-wide)',
          }}>
            Projects ({projects.length})
          </span>
          <button
            onClick={refresh}
            className="focus-ring"
            title="Refresh"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              color: 'var(--text-tertiary)',
              fontSize: 14,
              padding: 2,
              borderRadius: 'var(--radius-sm)',
            }}
          >
            &#8635;
          </button>
        </div>
        {projects.map(p => (
          <ProjectCard
            key={p.id}
            project={{
              ...p,
              convergence_progress: liveStatus[p.id]?.progress ?? p.convergence_progress,
              status: liveStatus[p.id]?.status ?? p.status,
            }}
            isSelected={p.id === selectedId}
            onSelect={() => setSelectedId(p.id)}
          />
        ))}
      </div>

      {/* Separator */}
      <div style={{ width: 1, background: 'var(--separator)', flexShrink: 0 }} />

      {/* Progress detail */}
      <div style={{ flex: 1, overflowY: 'auto' }}>
        {selectedProject ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
            {/* Project header */}
            <div>
              <h2 style={{
                fontSize: 'var(--text-title3)',
                fontWeight: 'var(--weight-semibold)' as any,
                color: 'var(--text-primary)',
                marginBottom: 'var(--space-1)',
              }}>
                {selectedProject.name}
              </h2>
              {selectedProject.description && (
                <p style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-secondary)' }}>
                  {selectedProject.description}
                </p>
              )}
              <div className="flex items-center gap-3" style={{ marginTop: 'var(--space-2)' }}>
                {selectedProject.tech_stack && (
                  <span style={{
                    fontSize: 'var(--text-caption1)',
                    padding: '2px 8px',
                    background: 'var(--fill-quaternary)',
                    borderRadius: 'var(--radius-sm)',
                    color: 'var(--text-secondary)',
                  }}>
                    {selectedProject.tech_stack}
                  </span>
                )}
                <span style={{
                  fontSize: 'var(--text-caption1)',
                  padding: '2px 8px',
                  background: status === 'generating' ? 'rgba(255,214,10,0.12)' : status === 'completed' ? 'rgba(48,209,88,0.12)' : 'var(--fill-quaternary)',
                  color: status === 'generating' ? 'var(--system-yellow)' : status === 'completed' ? 'var(--system-green)' : 'var(--text-secondary)',
                  borderRadius: 'var(--radius-sm)',
                  textTransform: 'capitalize',
                }}>
                  {status}
                </span>
              </div>
            </div>

            {/* Progress stages */}
            <ProgressView progress={progress} status={status} />

            {/* Error message */}
            {selectedProject.error_message && (
              <div style={{
                padding: 'var(--space-3) var(--space-4)',
                background: 'rgba(255,69,58,0.08)',
                borderRadius: 'var(--radius-md)',
                border: '1px solid rgba(255,69,58,0.2)',
                fontSize: 'var(--text-caption1)',
                color: 'var(--system-red)',
              }}>
                {selectedProject.error_message}
              </div>
            )}
          </div>
        ) : (
          <div className="flex items-center justify-center h-full" style={{ color: 'var(--text-tertiary)' }}>
            Select a project
          </div>
        )}
      </div>
    </div>
    )}
    </div>
  )
}
