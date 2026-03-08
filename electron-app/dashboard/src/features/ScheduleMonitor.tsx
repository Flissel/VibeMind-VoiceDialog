import { useState } from 'react'
import type { ScheduledTask } from '../types'
import { useScheduledTasks, updateTaskStatus } from '../hooks/useIPC'

/* ── Helpers ───────────────────────────────────────────────── */

function formatTs(ts: string | null): string {
  if (!ts) return '--'
  const d = new Date(ts)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function parseTriggerConfig(task: ScheduledTask): string {
  try {
    const cfg = typeof task.trigger_config === 'string'
      ? JSON.parse(task.trigger_config)
      : task.trigger_config
    if (task.trigger_type === 'cron') {
      const parts = [cfg.minute ?? '*', cfg.hour ?? '*', cfg.day ?? '*', cfg.month ?? '*', cfg.day_of_week ?? '*']
      return parts.join(' ')
    }
    if (task.trigger_type === 'interval') {
      if (cfg.hours) return `Every ${cfg.hours}h`
      if (cfg.minutes) return `Every ${cfg.minutes}m`
      if (cfg.seconds) return `Every ${cfg.seconds}s`
      return 'Interval'
    }
    if (task.trigger_type === 'date') return 'One-shot'
    return task.trigger_type
  } catch {
    return task.trigger_type
  }
}

const STATUS_COLORS: Record<string, string> = {
  active: 'var(--system-green)',
  paused: 'var(--system-orange)',
  completed: 'var(--system-blue)',
  cancelled: 'var(--text-tertiary)',
  failed: 'var(--system-red)',
}

const FILTER_PILLS = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'paused', label: 'Paused' },
  { key: 'failed', label: 'Failed' },
] as const

type FilterKey = typeof FILTER_PILLS[number]['key']

/* ── Component ─────────────────────────────────────────────── */

export function ScheduleMonitor() {
  const [filter, setFilter] = useState<FilterKey>('all')
  const statusFilter = filter === 'all' ? undefined : filter
  const { data, loading, error, refresh } = useScheduledTasks(statusFilter)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  const tasks: ScheduledTask[] = data?.tasks ?? []

  const handleStatusChange = async (taskId: string, newStatus: string) => {
    setActionLoading(taskId)
    try {
      await updateTaskStatus(taskId, newStatus)
      refresh()
    } catch (e) {
      console.error('Failed to update task status:', e)
    } finally {
      setActionLoading(null)
    }
  }

  // Loading skeleton
  if (loading && tasks.length === 0) {
    return (
      <div>
        <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-4)' }}>
          {[1, 2, 3, 4].map(i => (
            <div key={i} style={{ width: 70, height: 32, borderRadius: 20, background: 'var(--fill-tertiary)' }} />
          ))}
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} style={{ height: 72, borderRadius: 'var(--radius-md)', background: 'var(--material-regular)', marginBottom: 'var(--space-2)' }} />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ height: 300, color: 'var(--text-secondary)', gap: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-title3)' }}>&#x26A0;&#xFE0F;</span>
        <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>Fehler beim Laden</span>
        <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)' }}>{error}</span>
        <button onClick={refresh} style={{ marginTop: 'var(--space-2)', padding: '6px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)', background: 'var(--fill-secondary)', color: 'var(--text-primary)', cursor: 'pointer', fontSize: 'var(--text-footnote)' }}>
          Erneut versuchen
        </button>
      </div>
    )
  }

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-4)' }}>
        <h2 style={{ fontSize: 'var(--text-title3)', fontWeight: 'var(--weight-bold)', letterSpacing: 'var(--tracking-tight)' }}>
          Schedule Monitor
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

      {/* Summary Cards */}
      <div className="flex gap-3" style={{ marginBottom: 'var(--space-4)' }}>
        {[
          { label: 'Gesamt', value: tasks.length, color: 'var(--text-primary)' },
          { label: 'Aktiv', value: tasks.filter(t => t.status === 'active').length, color: 'var(--system-green)' },
          { label: 'Pausiert', value: tasks.filter(t => t.status === 'paused').length, color: 'var(--system-orange)' },
          { label: 'Fehler', value: tasks.filter(t => t.status === 'failed' || t.last_error).length, color: 'var(--system-red)' },
        ].map(card => (
          <div key={card.label} style={{
            flex: 1,
            padding: 'var(--space-3) var(--space-4)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--material-regular)',
            backdropFilter: 'blur(20px)',
          }}>
            <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginBottom: 'var(--space-1)' }}>{card.label}</div>
            <div style={{ fontSize: 'var(--text-title2)', fontWeight: 'var(--weight-bold)', color: card.color }}>{card.value}</div>
          </div>
        ))}
      </div>

      {/* Filter Pills */}
      <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-3)' }}>
        {FILTER_PILLS.map(pill => {
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
      </div>

      {/* Task List */}
      {tasks.length === 0 ? (
        <div className="flex flex-col items-center justify-center" style={{ height: 200, color: 'var(--text-secondary)', gap: 'var(--space-2)' }}>
          <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>
            Keine geplanten Tasks
          </span>
          <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)' }}>
            Erstelle Tasks via Voice: "Erinnere mich morgen um 9 Uhr..."
          </span>
        </div>
      ) : (
        <div style={{ borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--material-regular)', backdropFilter: 'blur(20px)' }}>
          {tasks.map((task, idx) => (
            <div key={task.id}>
              {idx > 0 && <div style={{ height: 1, background: 'var(--separator)', marginLeft: 'var(--space-4)', marginRight: 'var(--space-4)' }} />}
              <div className="flex items-center" style={{ minHeight: 56, padding: '0 var(--space-4)', gap: 'var(--space-3)' }}>
                {/* Status dot */}
                <span className="flex-shrink-0 rounded-full" style={{
                  width: 8,
                  height: 8,
                  background: STATUS_COLORS[task.status] ?? 'var(--text-tertiary)',
                }} />

                {/* Title + action_text */}
                <div className="flex-1 min-w-0">
                  <div className="truncate" style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-medium)', color: 'var(--text-primary)' }}>
                    {task.title}
                  </div>
                  <div className="truncate" style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginTop: 2 }}>
                    {task.action_text}
                  </div>
                </div>

                {/* Trigger type badge */}
                <span className="flex-shrink-0" style={{
                  fontSize: 'var(--text-caption2)',
                  fontWeight: 'var(--weight-semibold)',
                  padding: '1px 6px',
                  borderRadius: 4,
                  background: 'rgba(0,122,255,0.1)',
                  color: 'var(--system-blue)',
                  letterSpacing: '0.04em',
                  textTransform: 'uppercase',
                }}>
                  {parseTriggerConfig(task)}
                </span>

                {/* Next run */}
                <div className="flex-shrink-0" style={{ textAlign: 'right', minWidth: 100 }}>
                  <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
                    {task.next_run_at ? formatTs(task.next_run_at) : '--'}
                  </div>
                  <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginTop: 1 }}>
                    Runs: {task.run_count}
                  </div>
                </div>

                {/* Status badge */}
                <span className="flex-shrink-0" style={{
                  fontSize: 'var(--text-caption2)',
                  fontWeight: 'var(--weight-medium)',
                  padding: '2px 8px',
                  borderRadius: 4,
                  background: `color-mix(in srgb, ${STATUS_COLORS[task.status] ?? 'var(--text-tertiary)'} 15%, transparent)`,
                  color: STATUS_COLORS[task.status] ?? 'var(--text-tertiary)',
                  textTransform: 'capitalize',
                }}>
                  {task.status}
                </span>

                {/* Actions */}
                <div className="flex-shrink-0 flex gap-1">
                  {task.status === 'active' && (
                    <button
                      onClick={() => handleStatusChange(task.id, 'paused')}
                      disabled={actionLoading === task.id}
                      className="hover-bg"
                      title="Pausieren"
                      style={{
                        width: 28, height: 28, borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--separator)', background: 'transparent',
                        color: 'var(--system-orange)', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 12,
                      }}
                    >
                      &#x23F8;
                    </button>
                  )}
                  {task.status === 'paused' && (
                    <button
                      onClick={() => handleStatusChange(task.id, 'active')}
                      disabled={actionLoading === task.id}
                      className="hover-bg"
                      title="Fortsetzen"
                      style={{
                        width: 28, height: 28, borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--separator)', background: 'transparent',
                        color: 'var(--system-green)', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 12,
                      }}
                    >
                      &#x25B6;
                    </button>
                  )}
                  {(task.status === 'active' || task.status === 'paused') && (
                    <button
                      onClick={() => handleStatusChange(task.id, 'cancelled')}
                      disabled={actionLoading === task.id}
                      className="hover-bg"
                      title="Abbrechen"
                      style={{
                        width: 28, height: 28, borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--separator)', background: 'transparent',
                        color: 'var(--system-red)', cursor: 'pointer',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 12,
                      }}
                    >
                      &#x2715;
                    </button>
                  )}
                </div>
              </div>

              {/* Error detail */}
              {task.last_error && (
                <div style={{
                  padding: '0 var(--space-4) var(--space-3) var(--space-4)',
                  marginLeft: 'var(--space-8)',
                }}>
                  <div style={{
                    fontSize: 'var(--text-caption1)',
                    color: 'var(--system-red)',
                    padding: 'var(--space-2) var(--space-3)',
                    borderRadius: 'var(--radius-sm)',
                    background: 'rgba(255,69,58,0.08)',
                    fontFamily: '"SF Mono", Monaco, Menlo, monospace',
                    whiteSpace: 'pre-wrap',
                    wordBreak: 'break-word',
                    maxHeight: 80,
                    overflow: 'auto',
                  }}>
                    {task.last_error}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
