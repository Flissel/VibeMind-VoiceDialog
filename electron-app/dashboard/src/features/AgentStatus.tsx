import { useState } from 'react'
import type { AgentStatusInfo } from '../types'
import { useAgentStatus } from '../hooks/useIPC'

/* ── Helpers ───────────────────────────────────────────────── */

const AGENT_META: Record<string, { label: string; icon: string; color: string }> = {
  bubbles: { label: 'Bubbles', icon: '\u{1F4AD}', color: '#4488ff' },
  ideas: { label: 'Ideas', icon: '\u{1F4A1}', color: '#4488ff' },
  coding: { label: 'Coding', icon: '\u{1F9EC}', color: '#44ff88' },
  desktop: { label: 'Desktop', icon: '\u{1F5A5}', color: '#ff8844' },
  roarboot: { label: 'Rowboat', icon: '\u{1F6A3}', color: '#22ccaa' },
  zeroclaw: { label: 'Research', icon: '\u{1F50D}', color: '#ff6633' },
  minibook: { label: 'Minibook', icon: '\u{1F4D6}', color: '#ff66aa' },
  schedule: { label: 'Schedule', icon: '\u{23F0}', color: '#8866ff' },
}

const STATUS_DOT: Record<string, string> = {
  idle: 'var(--text-tertiary)',
  started: 'var(--system-orange)',
  completed: 'var(--system-green)',
  error: 'var(--system-red)',
}

function formatTs(ts: string | null): string {
  if (!ts) return 'No Event Yet'
  const d = new Date(ts)
  const now = new Date()
  const diffMs = now.getTime() - d.getTime()

  if (diffMs < 60000) return 'Just Now'
  if (diffMs < 3600000) return `${Math.floor(diffMs / 60000)}m ago`
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`
  return d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
}

type FilterKey = 'all' | 'active' | 'error'

const PILLS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'error', label: 'Error' },
]

/* ── Component ─────────────────────────────────────────────── */

export function AgentStatus() {
  const { data, loading, error, refresh } = useAgentStatus()
  const [filter, setFilter] = useState<FilterKey>('all')
  const [expanded, setExpanded] = useState<string | null>(null)

  const agents: AgentStatusInfo[] = data?.agents ?? []

  // Filter
  const filtered = agents.filter(a => {
    if (filter === 'active') return a.status === 'started' || a.status === 'completed'
    if (filter === 'error') return a.status === 'error'
    return true
  })

  // Loading skeleton
  if (loading && agents.length === 0) {
    return (
      <div>
        <div className="flex gap-3" style={{ flexWrap: 'wrap', marginBottom: 'var(--space-4)' }}>
          {[1, 2, 3, 4, 5, 6, 7, 8].map(i => (
            <div key={i} style={{ width: 'calc(25% - 9px)', height: 80, borderRadius: 'var(--radius-md)', background: 'var(--material-regular)' }} />
          ))}
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ height: 300, color: 'var(--text-secondary)', gap: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-title3)' }}>&#x26A0;&#xFE0F;</span>
        <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>Error Loading</span>
        <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)' }}>{error}</span>
        <button onClick={refresh} style={{ marginTop: 'var(--space-2)', padding: '6px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)', background: 'var(--fill-secondary)', color: 'var(--text-primary)', cursor: 'pointer', fontSize: 'var(--text-footnote)' }}>
          Try Again
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-4)' }}>
        <h2 style={{ fontSize: 'var(--text-title3)', fontWeight: 'var(--weight-bold)', letterSpacing: 'var(--tracking-tight)' }}>
          Agent Status
        </h2>
        <button
          onClick={refresh}
          className="hover-bg"
          style={{
            padding: '6px 12px',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--separator)',
            background: 'transparent',
            color: 'var(--text-secondary)',
            cursor: 'pointer',
            fontSize: 'var(--text-caption1)',
          }}
        >
          &#x21BB; Refresh
        </button>
      </div>

      {/* Agent Grid (2x4) */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(4, 1fr)',
        gap: 'var(--space-3)',
        marginBottom: 'var(--space-4)',
      }}>
        {agents.map(agent => {
          const meta = AGENT_META[agent.name] ?? { label: agent.name, icon: '\u{1F916}', color: 'var(--text-secondary)' }
          const dotColor = STATUS_DOT[agent.status] ?? 'var(--text-tertiary)'

          return (
            <div
              key={agent.name}
              onClick={() => setExpanded(expanded === agent.name ? null : agent.name)}
              className="cursor-pointer hover-bg"
              style={{
                padding: 'var(--space-3)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--material-regular)',
                backdropFilter: 'blur(20px)',
                transition: 'all 150ms var(--ease-smooth)',
                border: expanded === agent.name ? `1px solid ${meta.color}` : '1px solid transparent',
              }}
            >
              <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-2)' }}>
                <span style={{ fontSize: 18 }}>{meta.icon}</span>
                <span style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                  {meta.label}
                </span>
                <span className="rounded-full" style={{
                  width: 8, height: 8,
                  background: dotColor,
                  marginLeft: 'auto',
                  boxShadow: agent.status === 'started' ? `0 0 6px ${dotColor}` : undefined,
                }} />
              </div>
              <div className="truncate" style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>
                {agent.last_event_type ?? 'No Event'}
              </div>
              <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-quaternary)', marginTop: 2 }}>
                {formatTs(agent.last_event_at)}
              </div>
            </div>
          )
        })}
      </div>

      {/* Expanded Detail */}
      {expanded && (() => {
        const agent = agents.find(a => a.name === expanded)
        if (!agent) return null
        const meta = AGENT_META[agent.name] ?? { label: agent.name, icon: '\u{1F916}', color: 'var(--text-secondary)' }

        return (
          <div className="animate-slide-down" style={{
            marginBottom: 'var(--space-4)',
            padding: 'var(--space-4)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--material-regular)',
            border: `1px solid ${meta.color}`,
          }}>
            <div className="flex items-center gap-3" style={{ marginBottom: 'var(--space-3)' }}>
              <span style={{ fontSize: 24 }}>{meta.icon}</span>
              <div>
                <div style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-bold)', color: 'var(--text-primary)' }}>
                  {meta.label} Agent
                </div>
                <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
                  Status: <span style={{ color: STATUS_DOT[agent.status], fontWeight: 'var(--weight-medium)', textTransform: 'capitalize' }}>{agent.status}</span>
                </div>
              </div>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: 'var(--space-1) var(--space-4)' }}>
              <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>Last Event</span>
              <span className="font-mono" style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>{agent.last_event_type ?? '--'}</span>

              <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>Timestamp</span>
              <span className="font-mono" style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
                {agent.last_event_at ? new Date(agent.last_event_at).toISOString() : '--'}
              </span>

              {agent.last_result && (
                <>
                  <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>Result</span>
                  <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
                    {agent.last_result}
                  </span>
                </>
              )}
            </div>
          </div>
        )
      })()}

      {/* Filter Pills */}
      <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-3)' }}>
        {PILLS.map(pill => {
          const isActive = filter === pill.key
          return (
            <button
              key={pill.key}
              onClick={() => setFilter(pill.key)}
              className="focus-ring"
              style={{
                borderRadius: 20,
                padding: '6px 14px',
                fontSize: 'var(--text-footnote)',
                fontWeight: 'var(--weight-medium)',
                border: 'none',
                cursor: 'pointer',
                transition: 'all 200ms var(--ease-smooth)',
                background: isActive ? 'var(--accent-fill)' : 'var(--fill-secondary)',
                color: isActive ? 'var(--accent)' : 'var(--text-primary)',
              }}
            >
              {pill.label}
            </button>
          )
        })}
        <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
          {filtered.length} of {agents.length} Agents
        </span>
      </div>

      {/* Agent List (LogBrowser style) */}
      {filtered.length > 0 && (
        <div style={{ borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--material-regular)', backdropFilter: 'blur(20px)' }}>
          {filtered.map((agent, idx) => {
            const meta = AGENT_META[agent.name] ?? { label: agent.name, icon: '\u{1F916}', color: 'var(--text-secondary)' }
            return (
              <div key={agent.name}>
                {idx > 0 && <div style={{ height: 1, background: 'var(--separator)', marginLeft: 'var(--space-4)', marginRight: 'var(--space-4)' }} />}
                <div
                  className="flex items-center hover-bg"
                  style={{
                    minHeight: 44,
                    padding: '0 var(--space-4)',
                    background: agent.status === 'error' ? 'rgba(255,69,58,0.06)' : undefined,
                  }}
                >
                  <span className="flex-shrink-0 rounded-full" style={{ width: 8, height: 8, background: STATUS_DOT[agent.status] ?? 'var(--text-tertiary)' }} />
                  <span className="flex-shrink-0" style={{ fontSize: 'var(--text-footnote)', color: meta.color, marginLeft: 'var(--space-3)', fontWeight: 'var(--weight-semibold)', minWidth: 80 }}>
                    {meta.label}
                  </span>
                  <span className="font-mono flex-shrink-0" style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginLeft: 'var(--space-3)', minWidth: 120 }}>
                    {agent.last_event_type ?? '--'}
                  </span>
                  <span className="truncate" style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)', marginLeft: 'var(--space-3)', flex: 1, minWidth: 0 }}>
                    {agent.last_result ?? ''}
                  </span>
                  <span className="flex-shrink-0" style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginLeft: 'var(--space-3)' }}>
                    {formatTs(agent.last_event_at)}
                  </span>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
