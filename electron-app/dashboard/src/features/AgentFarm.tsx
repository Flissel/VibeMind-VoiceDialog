import { useState, useEffect, useCallback, useRef } from 'react'
import { WorkflowBuilder } from './WorkflowBuilder'
import {
  useAgentFarmTeams,
  runAgentTeam,
  stopAgentRun,
  usePythonMessages,
} from '../hooks/useIPC'

type SubTab = 'autogen' | 'n8n'

const SUB_TABS: { key: SubTab; label: string }[] = [
  { key: 'autogen', label: 'Autogen' },
  { key: 'n8n', label: 'n8n' },
]

/* ── Progress message from a running team ── */
interface ProgressStep {
  agent: string
  content: string
  timestamp: number
}

/* ── Team card in the sidebar ── */
function TeamCard({
  team,
  isSelected,
  onSelect,
  runStatus,
}: {
  team: any
  isSelected: boolean
  onSelect: () => void
  runStatus?: string
}) {
  const displayStatus = runStatus || team.status || 'idle'
  const statusColor =
    displayStatus === 'running' ? 'var(--system-yellow)'
    : displayStatus === 'done' || displayStatus === 'completed' ? 'var(--system-green)'
    : displayStatus === 'error' ? 'var(--system-red)'
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
        <span
          className="truncate"
          style={{
            fontSize: 'var(--text-footnote)',
            fontWeight: 'var(--weight-medium)' as any,
            color: 'var(--text-primary)',
            flex: 1,
            minWidth: 0,
          }}
        >
          {team.name || team.team_id || 'Unnamed Team'}
        </span>
        <span
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: statusColor,
            flexShrink: 0,
            marginLeft: 'var(--space-2)',
          }}
        />
      </div>
      <div className="flex items-center" style={{ gap: 'var(--space-2)' }}>
        {team.team_type && (
          <span
            style={{
              fontSize: 'var(--text-caption1)',
              padding: '1px 6px',
              background: 'var(--fill-quaternary)',
              borderRadius: 'var(--radius-sm)',
              color: 'var(--text-secondary)',
            }}
          >
            {team.team_type}
          </span>
        )}
        <span
          style={{
            fontSize: 'var(--text-caption1)',
            color: 'var(--text-tertiary)',
          }}
        >
          {team.agents?.length ?? team.agent_count ?? 0} agents
        </span>
      </div>
    </button>
  )
}

/* ── Autogen Panel ── */
function AutogenPanel() {
  const { data, loading, error, refresh } = useAgentFarmTeams()
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [taskInput, setTaskInput] = useState('')
  const [currentRunId, setCurrentRunId] = useState<string | null>(null)
  const [runStatuses, setRunStatuses] = useState<Record<string, string>>({})
  const [steps, setSteps] = useState<ProgressStep[]>([])
  const [runMeta, setRunMeta] = useState<{ stepCount: number; duration: number } | null>(null)
  const stepsEndRef = useRef<HTMLDivElement>(null)

  const teams: any[] = data?.teams ?? []

  // Listen for live progress messages
  usePythonMessages(
    'agentfarm_progress',
    useCallback((msg: any) => {
      if (msg.run_id === currentRunId) {
        setSteps(prev => [
          ...prev,
          {
            agent: msg.agent ?? 'System',
            content: msg.content ?? msg.message ?? '',
            timestamp: Date.now(),
          },
        ])
      }
    }, [currentRunId])
  )

  // Listen for run completion
  usePythonMessages(
    'agentfarm_run_complete',
    useCallback((msg: any) => {
      if (msg.run_id === currentRunId) {
        setRunStatuses(prev => ({ ...prev, [selectedId!]: 'done' }))
        setRunMeta({
          stepCount: msg.step_count ?? steps.length,
          duration: msg.duration ?? 0,
        })
        setCurrentRunId(null)
      }
    }, [currentRunId, selectedId, steps.length])
  )

  // Auto-scroll steps
  useEffect(() => {
    stepsEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [steps])

  // Auto-select first team
  useEffect(() => {
    if (!selectedId && teams.length > 0) {
      setSelectedId(teams[0].team_id ?? teams[0].id)
    }
  }, [teams, selectedId])

  const selectedTeam = teams.find(
    t => (t.team_id ?? t.id) === selectedId
  )
  const isRunning = selectedId ? runStatuses[selectedId] === 'running' : false
  const isDone = selectedId ? runStatuses[selectedId] === 'done' : false

  async function handleRun() {
    if (!selectedId || !taskInput.trim()) return
    setSteps([])
    setRunMeta(null)
    setRunStatuses(prev => ({ ...prev, [selectedId]: 'running' }))
    try {
      const result = await runAgentTeam(selectedId, taskInput.trim())
      if (result?.run_id) {
        setCurrentRunId(result.run_id)
      }
    } catch {
      setRunStatuses(prev => ({ ...prev, [selectedId]: 'error' }))
    }
  }

  async function handleStop() {
    if (!currentRunId) return
    try {
      await stopAgentRun(currentRunId)
      setRunStatuses(prev => ({ ...prev, [selectedId!]: 'done' }))
      setCurrentRunId(null)
    } catch {
      // ignore
    }
  }

  if (loading && teams.length === 0) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ color: 'var(--text-tertiary)' }}
      >
        Loading teams...
      </div>
    )
  }

  if (error) {
    return (
      <div
        className="flex items-center justify-center h-full"
        style={{ color: 'var(--system-red)' }}
      >
        Error: {error}
      </div>
    )
  }

  if (teams.length === 0) {
    return (
      <div
        className="flex flex-col items-center justify-center h-full gap-2"
        style={{ color: 'var(--text-tertiary)' }}
      >
        <span style={{ fontSize: 32 }}>&#129302;</span>
        <span style={{ fontSize: 'var(--text-footnote)' }}>No teams configured</span>
      </div>
    )
  }

  return (
    <div className="flex h-full" style={{ gap: 'var(--space-4)' }}>
      {/* Team list sidebar */}
      <div
        style={{
          width: 220,
          flexShrink: 0,
          display: 'flex',
          flexDirection: 'column',
          gap: 'var(--space-1)',
          overflowY: 'auto',
          paddingRight: 'var(--space-2)',
        }}
      >
        <div
          className="flex items-center justify-between"
          style={{
            padding: '0 var(--space-3)',
            marginBottom: 'var(--space-2)',
          }}
        >
          <span
            style={{
              fontSize: 'var(--text-caption1)',
              fontWeight: 'var(--weight-semibold)' as any,
              color: 'var(--text-secondary)',
              textTransform: 'uppercase',
              letterSpacing: 'var(--tracking-wide)',
            }}
          >
            Teams ({teams.length})
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
        {teams.map((t: any) => {
          const tid = t.team_id ?? t.id
          return (
            <TeamCard
              key={tid}
              team={t}
              isSelected={tid === selectedId}
              onSelect={() => {
                setSelectedId(tid)
                setSteps([])
                setRunMeta(null)
                setCurrentRunId(null)
              }}
              runStatus={runStatuses[tid]}
            />
          )
        })}
      </div>

      {/* Separator */}
      <div style={{ width: 1, background: 'var(--separator)', flexShrink: 0 }} />

      {/* Detail panel */}
      <div style={{ flex: 1, overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        {selectedTeam ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)', flex: 1 }}>
            {/* Team header */}
            <div>
              <h2
                style={{
                  fontSize: 'var(--text-title3)',
                  fontWeight: 'var(--weight-semibold)' as any,
                  color: 'var(--text-primary)',
                  marginBottom: 'var(--space-1)',
                }}
              >
                {selectedTeam.name || selectedTeam.team_id || 'Unnamed Team'}
              </h2>
              <div className="flex items-center" style={{ gap: 'var(--space-2)', flexWrap: 'wrap' }}>
                {(selectedTeam.agents ?? []).map((agent: any, i: number) => (
                  <span
                    key={i}
                    style={{
                      fontSize: 'var(--text-caption1)',
                      padding: '2px 8px',
                      background: 'var(--fill-quaternary)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--text-secondary)',
                    }}
                  >
                    {typeof agent === 'string' ? agent : agent.name ?? `Agent ${i + 1}`}
                  </span>
                ))}
                {selectedTeam.team_type && (
                  <span
                    style={{
                      fontSize: 'var(--text-caption1)',
                      padding: '2px 8px',
                      background: 'rgba(10,132,255,0.12)',
                      borderRadius: 'var(--radius-sm)',
                      color: 'var(--accent)',
                    }}
                  >
                    {selectedTeam.team_type}
                  </span>
                )}
              </div>
            </div>

            {/* Task input */}
            <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
              <input
                type="text"
                value={taskInput}
                onChange={e => setTaskInput(e.target.value)}
                onKeyDown={e => {
                  if (e.key === 'Enter' && !isRunning) handleRun()
                }}
                placeholder="Describe the task for this team..."
                className="focus-ring"
                disabled={isRunning}
                style={{
                  flex: 1,
                  padding: 'var(--space-2) var(--space-3)',
                  background: 'var(--fill-quaternary)',
                  border: '1px solid var(--separator)',
                  borderRadius: 'var(--radius-md)',
                  color: 'var(--text-primary)',
                  fontSize: 'var(--text-footnote)',
                  outline: 'none',
                }}
              />
              {isRunning ? (
                <button
                  onClick={handleStop}
                  className="focus-ring"
                  style={{
                    padding: 'var(--space-2) var(--space-4)',
                    background: 'rgba(255,69,58,0.15)',
                    color: 'var(--system-red)',
                    border: '1px solid rgba(255,69,58,0.3)',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--text-footnote)',
                    fontWeight: 'var(--weight-semibold)' as any,
                    cursor: 'pointer',
                    whiteSpace: 'nowrap',
                  }}
                >
                  Stop
                </button>
              ) : (
                <button
                  onClick={handleRun}
                  className="focus-ring"
                  disabled={!taskInput.trim()}
                  style={{
                    padding: 'var(--space-2) var(--space-4)',
                    background: taskInput.trim() ? 'var(--accent)' : 'var(--fill-quaternary)',
                    color: taskInput.trim() ? '#fff' : 'var(--text-tertiary)',
                    border: 'none',
                    borderRadius: 'var(--radius-md)',
                    fontSize: 'var(--text-footnote)',
                    fontWeight: 'var(--weight-semibold)' as any,
                    cursor: taskInput.trim() ? 'pointer' : 'default',
                    whiteSpace: 'nowrap',
                    opacity: taskInput.trim() ? 1 : 0.5,
                  }}
                >
                  Run
                </button>
              )}
            </div>

            {/* Live message stream */}
            {(steps.length > 0 || isRunning) && (
              <div
                style={{
                  flex: 1,
                  minHeight: 120,
                  maxHeight: 400,
                  overflowY: 'auto',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 'var(--space-2)',
                  padding: 'var(--space-3)',
                  background: 'var(--bg-secondary)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid var(--separator)',
                }}
              >
                {steps.map((step, i) => (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      gap: 'var(--space-3)',
                      padding: 'var(--space-2) var(--space-3)',
                      borderRadius: 'var(--radius-sm)',
                      background: 'var(--fill-quaternary)',
                    }}
                  >
                    <span
                      style={{
                        fontSize: 'var(--text-caption1)',
                        fontWeight: 'var(--weight-semibold)' as any,
                        color: 'var(--accent)',
                        whiteSpace: 'nowrap',
                        minWidth: 80,
                      }}
                    >
                      {step.agent}
                    </span>
                    <span
                      style={{
                        fontSize: 'var(--text-caption1)',
                        color: 'var(--text-primary)',
                        whiteSpace: 'pre-wrap',
                        wordBreak: 'break-word',
                      }}
                    >
                      {step.content}
                    </span>
                  </div>
                ))}
                {isRunning && steps.length === 0 && (
                  <div
                    style={{
                      fontSize: 'var(--text-caption1)',
                      color: 'var(--text-tertiary)',
                      fontStyle: 'italic',
                    }}
                  >
                    Waiting for agent responses...
                  </div>
                )}
                <div ref={stepsEndRef} />
              </div>
            )}

            {/* Completion summary */}
            {isDone && runMeta && (
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 'var(--space-4)',
                  padding: 'var(--space-3) var(--space-4)',
                  background: 'rgba(48,209,88,0.08)',
                  borderRadius: 'var(--radius-md)',
                  border: '1px solid rgba(48,209,88,0.2)',
                }}
              >
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="8" fill="var(--system-green)" opacity="0.15" />
                  <path
                    d="M4.5 8.5L7 11L11.5 5.5"
                    stroke="var(--system-green)"
                    strokeWidth="1.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
                <div>
                  <span
                    style={{
                      fontSize: 'var(--text-footnote)',
                      fontWeight: 'var(--weight-semibold)' as any,
                      color: 'var(--system-green)',
                    }}
                  >
                    Completed
                  </span>
                  <span
                    style={{
                      fontSize: 'var(--text-caption1)',
                      color: 'var(--text-secondary)',
                      marginLeft: 'var(--space-3)',
                    }}
                  >
                    {runMeta.stepCount} steps
                    {runMeta.duration > 0 && ` \u00B7 ${(runMeta.duration / 1000).toFixed(1)}s`}
                  </span>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div
            className="flex items-center justify-center h-full"
            style={{ color: 'var(--text-tertiary)' }}
          >
            Select a team
          </div>
        )}
      </div>
    </div>
  )
}

/* ── Main AgentFarm component with sub-tabs ── */
export function AgentFarm() {
  const [activeSubTab, setActiveSubTab] = useState<SubTab>('autogen')

  return (
    <div className="flex flex-col h-full" style={{ gap: 'var(--space-4)' }}>
      {/* Sub-Tab Pills */}
      <div
        className="flex items-center flex-shrink-0"
        style={{
          gap: 'var(--space-2)',
          padding: '2px',
          background: 'var(--fill-tertiary)',
          borderRadius: 'var(--radius-md)',
          width: 'fit-content',
        }}
      >
        {SUB_TABS.map(tab => {
          const isActive = activeSubTab === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => setActiveSubTab(tab.key)}
              style={{
                border: 'none',
                cursor: 'pointer',
                padding: '6px 20px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--text-footnote)',
                fontWeight: isActive ? 600 : 500,
                transition: 'all 150ms var(--ease-smooth)',
                background: isActive ? 'var(--bg-secondary)' : 'transparent',
                color: isActive ? 'var(--text-primary)' : 'var(--text-tertiary)',
                boxShadow: isActive
                  ? '0 1px 3px rgba(0,0,0,0.2), 0 0 0 0.5px rgba(255,255,255,0.05)'
                  : 'none',
              }}
            >
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden" style={{ minHeight: 0 }}>
        {activeSubTab === 'autogen' && <AutogenPanel />}
        {activeSubTab === 'n8n' && <WorkflowBuilder />}
      </div>
    </div>
  )
}
