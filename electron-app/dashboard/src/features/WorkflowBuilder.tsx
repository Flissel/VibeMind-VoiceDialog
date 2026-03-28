import { useState, useCallback } from 'react'

/* ── Types ────────────────────────────────────────────────── */

interface N8nWorkflow {
  id: string
  name: string
  active: boolean
  created_at?: string
  updated_at?: string
}

interface N8nStatus {
  online: boolean
  url: string
  workflow_count?: number
  error?: string
}

const api = typeof window !== 'undefined' ? (window as any).vibemindDashboard : null

/* ── Hooks ────────────────────────────────────────────────── */

function useN8nStatus() {
  const [data, setData] = useState<N8nStatus | null>(null)
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!api?.n8nStatus) return
    setLoading(true)
    try {
      const result = await api.n8nStatus()
      setData(result)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  return { data, loading, refresh }
}

function useN8nWorkflows() {
  const [workflows, setWorkflows] = useState<N8nWorkflow[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!api?.n8nList) return
    setLoading(true)
    setError(null)
    try {
      const result = await api.n8nList()
      setWorkflows(result?.workflows ?? [])
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setLoading(false) }
  }, [])

  return { workflows, loading, error, refresh }
}

/* ── Status Colors ────────────────────────────────────────── */

const STATUS = {
  active: { color: 'var(--system-green)', label: 'Active' },
  inactive: { color: 'var(--system-orange)', label: 'Inactive' },
} as const

/* ── Component ────────────────────────────────────────────── */

export function WorkflowBuilder() {
  const status = useN8nStatus()
  const { workflows, loading, error, refresh } = useN8nWorkflows()
  const [description, setDescription] = useState('')
  const [generating, setGenerating] = useState(false)
  const [genResult, setGenResult] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  // Initial load
  useState(() => {
    status.refresh()
    refresh()
  })

  const handleGenerate = async () => {
    if (!description.trim() || !api?.n8nGenerate) return
    setGenerating(true)
    setGenResult(null)
    try {
      const result = await api.n8nGenerate(description)
      setGenResult(result?.message ?? 'Workflow created')
      setDescription('')
      refresh() // Reload list
    } catch (e) {
      setGenResult(`Error: ${e instanceof Error ? e.message : String(e)}`)
    } finally { setGenerating(false) }
  }

  const handleActivate = async (id: string) => {
    if (!api?.n8nActivate) return
    setActionLoading(id)
    try {
      await api.n8nActivate(id)
      refresh()
    } catch { /* ignore */ }
    finally { setActionLoading(null) }
  }

  const handleDeactivate = async (id: string) => {
    if (!api?.n8nDeactivate) return
    setActionLoading(id)
    try {
      await api.n8nDeactivate(id)
      refresh()
    } catch { /* ignore */ }
    finally { setActionLoading(null) }
  }

  const handleDelete = async (id: string) => {
    if (!api?.n8nDelete) return
    setActionLoading(id)
    try {
      await api.n8nDelete(id)
      refresh()
    } catch { /* ignore */ }
    finally { setActionLoading(null) }
  }

  const n8nUrl = status.data?.url ?? 'http://localhost:15678'

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-4)' }}>
        <h2 style={{ fontSize: 'var(--text-title3)', fontWeight: 'var(--weight-bold)', letterSpacing: 'var(--tracking-tight)' }}>
          Workflow Builder
        </h2>
        <div className="flex items-center gap-2">
          {/* n8n status dot */}
          <span
            className="rounded-full"
            style={{
              width: 8, height: 8,
              background: status.data?.online ? 'var(--system-green)' : 'var(--system-red)',
            }}
          />
          <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
            {status.data?.online ? 'n8n online' : 'n8n offline'}
          </span>
          <button
            onClick={() => api?.openN8nEditor?.()}
            className="hover-bg"
            style={{
              padding: '4px 10px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--separator)', background: 'transparent',
              color: 'var(--system-blue)', cursor: 'pointer',
              fontSize: 'var(--text-caption1)',
            }}
          >
            n8n Editor
          </button>
          <button
            onClick={() => { status.refresh(); refresh() }}
            className="hover-bg"
            style={{
              padding: '6px 12px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--separator)', background: 'transparent',
              color: 'var(--text-secondary)', cursor: 'pointer',
              fontSize: 'var(--text-caption1)',
            }}
          >
            &#x21BB; Refresh
          </button>
        </div>
      </div>

      {/* Generate Section */}
      <div style={{
        padding: 'var(--space-4)', borderRadius: 'var(--radius-md)',
        background: 'var(--material-regular)', backdropFilter: 'blur(20px)',
        marginBottom: 'var(--space-4)',
      }}>
        <label style={{
          display: 'block', fontSize: 'var(--text-footnote)',
          fontWeight: 'var(--weight-medium)', color: 'var(--text-secondary)',
          marginBottom: 'var(--space-2)',
        }}>
          Describe Workflow
        </label>
        <textarea
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="e.g.: AI Agent with webhook trigger, PostgreSQL DB, and think tool that reads Datev data..."
          rows={3}
          style={{
            width: '100%', resize: 'vertical',
            padding: 'var(--space-3)', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--separator)', background: 'var(--fill-secondary)',
            color: 'var(--text-primary)', fontSize: 'var(--text-footnote)',
            fontFamily: 'inherit', outline: 'none',
          }}
          onFocus={(e) => e.target.style.borderColor = 'var(--accent)'}
          onBlur={(e) => e.target.style.borderColor = 'var(--separator)'}
        />
        <div className="flex items-center gap-3" style={{ marginTop: 'var(--space-3)' }}>
          <button
            onClick={handleGenerate}
            disabled={generating || !description.trim()}
            style={{
              padding: '8px 20px', borderRadius: 'var(--radius-sm)',
              border: 'none', cursor: generating ? 'wait' : 'pointer',
              fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-semibold)',
              background: generating ? 'var(--fill-tertiary)' : 'var(--accent)',
              color: generating ? 'var(--text-tertiary)' : '#fff',
              transition: 'all 150ms var(--ease-smooth)',
            }}
          >
            {generating ? 'Generating...' : 'Generate Workflow'}
          </button>
          {genResult && (
            <span style={{
              fontSize: 'var(--text-caption1)',
              color: genResult.startsWith('Error') ? 'var(--system-red)' : 'var(--system-green)',
            }}>
              {genResult}
            </span>
          )}
        </div>
      </div>

      {/* Workflow List */}
      {error && (
        <div style={{ padding: 'var(--space-3)', color: 'var(--system-red)', fontSize: 'var(--text-footnote)' }}>
          {error}
        </div>
      )}

      {loading && workflows.length === 0 ? (
        <div>
          {[1, 2, 3].map(i => (
            <div key={i} style={{
              height: 56, borderRadius: 'var(--radius-md)',
              background: 'var(--material-regular)', marginBottom: 'var(--space-2)',
            }} />
          ))}
        </div>
      ) : workflows.length === 0 ? (
        <div className="flex flex-col items-center justify-center" style={{
          height: 150, color: 'var(--text-secondary)', gap: 'var(--space-2)',
        }}>
          <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>
            No Workflows
          </span>
          <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)' }}>
            Describe a workflow above or say: "Create a workflow for..."
          </span>
        </div>
      ) : (
        <div style={{
          borderRadius: 'var(--radius-md)', overflow: 'hidden',
          background: 'var(--material-regular)', backdropFilter: 'blur(20px)',
        }}>
          {workflows.map((wf, idx) => (
            <div key={wf.id}>
              {idx > 0 && <div style={{
                height: 1, background: 'var(--separator)',
                marginLeft: 'var(--space-4)', marginRight: 'var(--space-4)',
              }} />}
              <div className="flex items-center" style={{
                minHeight: 56, padding: '0 var(--space-4)', gap: 'var(--space-3)',
              }}>
                {/* Status dot */}
                <span className="flex-shrink-0 rounded-full" style={{
                  width: 8, height: 8,
                  background: wf.active ? STATUS.active.color : STATUS.inactive.color,
                }} />

                {/* Name */}
                <div className="flex-1 min-w-0">
                  <div className="truncate" style={{
                    fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-medium)',
                    color: 'var(--text-primary)',
                  }}>
                    {wf.name}
                  </div>
                  <div style={{
                    fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginTop: 1,
                  }}>
                    ID: {wf.id}
                  </div>
                </div>

                {/* Status badge */}
                <span className="flex-shrink-0" style={{
                  fontSize: 'var(--text-caption2)', fontWeight: 'var(--weight-medium)',
                  padding: '2px 8px', borderRadius: 4,
                  background: `color-mix(in srgb, ${wf.active ? STATUS.active.color : STATUS.inactive.color} 15%, transparent)`,
                  color: wf.active ? STATUS.active.color : STATUS.inactive.color,
                }}>
                  {wf.active ? 'Active' : 'Inactive'}
                </span>

                {/* Actions */}
                <div className="flex-shrink-0 flex gap-1">
                  {/* Toggle active */}
                  <button
                    onClick={() => wf.active ? handleDeactivate(wf.id) : handleActivate(wf.id)}
                    disabled={actionLoading === wf.id}
                    className="hover-bg"
                    title={wf.active ? 'Deactivate' : 'Activate'}
                    style={{
                      width: 28, height: 28, borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--separator)', background: 'transparent',
                      color: wf.active ? 'var(--system-orange)' : 'var(--system-green)',
                      cursor: 'pointer', display: 'flex', alignItems: 'center',
                      justifyContent: 'center', fontSize: 12,
                    }}
                  >
                    {wf.active ? '\u23F8' : '\u25B6'}
                  </button>

                  {/* Open in n8n */}
                  <button
                    onClick={() => api?.openN8nEditor?.(wf.id)}
                    className="hover-bg flex items-center justify-center"
                    title="In n8n oeffnen"
                    style={{
                      width: 28, height: 28, borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--separator)', background: 'transparent',
                      color: 'var(--system-blue)', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 12,
                    }}
                  >
                    &#x2197;
                  </button>

                  {/* Delete */}
                  <button
                    onClick={() => handleDelete(wf.id)}
                    disabled={actionLoading === wf.id}
                    className="hover-bg"
                    title="Delete"
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
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
