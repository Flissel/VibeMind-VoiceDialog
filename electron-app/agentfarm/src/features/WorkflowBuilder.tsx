import { useState, useCallback, useEffect } from 'react'
import { VibeCoderChat } from './VibeCoderChat'

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

const api = typeof window !== 'undefined' ? (window as any).vibemindAgentFarm : null

/* ── Hooks ────────────────────────────────────────────────── */

function useN8nStatus() {
  const [data, setData] = useState<N8nStatus | null>(null)
  const [loading, setLoading] = useState(false)
  const refresh = useCallback(async () => {
    if (!api?.n8nStatus) return
    setLoading(true)
    try { setData(await api.n8nStatus()) } catch { /* ignore */ }
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
    setLoading(true); setError(null)
    try {
      const result = await api.n8nList()
      setWorkflows(result?.workflows ?? [])
      if (result?.error) setError(result.error)
    }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setLoading(false) }
  }, [])
  return { workflows, loading, error, refresh }
}

const STATUS = {
  active: { color: 'var(--system-green)', label: 'Active' },
  inactive: { color: 'var(--system-orange)', label: 'Inactive' },
} as const

/* ── Main Component ──────────────────────────────────────── */

export function WorkflowBuilder() {
  const status = useN8nStatus()
  const { workflows, loading, error, refresh } = useN8nWorkflows()
  const [showVibeCoder, setShowVibeCoder] = useState(true)
  const [showEditor, setShowEditor] = useState(false)
  const [editorWorkflowId, setEditorWorkflowId] = useState<string | null>(null)
  const [actionLoading, setActionLoading] = useState<string | null>(null)
  const [authTick, setAuthTick] = useState(0)

  // n8n may run on another machine; the main process knows where (N8N_API_URL).
  const [n8nBaseUrl, setN8nBaseUrl] = useState('http://localhost:15678')

  useState(() => { status.refresh(); refresh() })

  useEffect(() => {
    const af = (window as any).vibemindAgentFarm
    if (af && typeof af.getN8nUrl === 'function') {
      af.getN8nUrl().then((url: string) => { if (url) setN8nBaseUrl(url) }).catch(() => {})
    }
    if (af && typeof af.onN8nAuthReady === 'function') {
      af.onN8nAuthReady(() => setAuthTick((t) => t + 1))
    }
  }, [])

  const handleActivate = async (id: string) => {
    if (!api?.n8nActivate) return
    setActionLoading(id)
    try { await api.n8nActivate(id); refresh() } catch { /* ignore */ }
    finally { setActionLoading(null) }
  }
  const handleDeactivate = async (id: string) => {
    if (!api?.n8nDeactivate) return
    setActionLoading(id)
    try { await api.n8nDeactivate(id); refresh() } catch { /* ignore */ }
    finally { setActionLoading(null) }
  }
  const handleDelete = async (id: string) => {
    if (!api?.n8nDelete) return
    setActionLoading(id)
    try { await api.n8nDelete(id); refresh() } catch { /* ignore */ }
    finally { setActionLoading(null) }
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Header */}
      <div className="flex items-center justify-between" style={{ marginBottom: 'var(--space-3)' }}>
        <h2 style={{ fontSize: 'var(--text-title3)', fontWeight: 'var(--weight-bold)', letterSpacing: 'var(--tracking-tight)' }}>
          Workflow Builder
        </h2>
        <div className="flex items-center gap-2">
          <span className="rounded-full" style={{
            width: 8, height: 8,
            background: status.data?.online ? 'var(--system-green)' : 'var(--system-red)',
          }} />
          <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
            {status.data?.online ? 'n8n online' : 'n8n offline'}
          </span>
          <button
            onClick={() => setShowVibeCoder(!showVibeCoder)}
            style={{
              padding: '4px 10px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--separator)',
              background: showVibeCoder ? 'var(--accent)' : 'transparent',
              color: showVibeCoder ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: 'var(--text-caption1)', fontWeight: 600,
            }}
          >
            VibeCoder
          </button>
          <button
            onClick={() => { setShowEditor(!showEditor); if (!showEditor) setEditorWorkflowId(null) }}
            style={{
              padding: '4px 10px', borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--separator)',
              background: showEditor ? 'var(--accent)' : 'transparent',
              color: showEditor ? '#fff' : 'var(--accent)',
              cursor: 'pointer', fontSize: 'var(--text-caption1)', fontWeight: 600,
            }}
          >
            n8n Editor
          </button>
          <button onClick={() => { status.refresh(); refresh() }} className="hover-bg" style={{
            padding: '6px 12px', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--separator)', background: 'transparent',
            color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 'var(--text-caption1)',
          }}>
            &#x21BB;
          </button>
        </div>
      </div>

      {/* Main: VibeCoder + Editor/Workflow List */}
      <div style={{ flex: 1, display: 'flex', gap: 'var(--space-3)', overflow: 'hidden' }}>
        {/* Left: VibeCoder Chat */}
        {showVibeCoder && (
          <div style={{ flex: showEditor ? '0 0 50%' : '0 0 50%', minHeight: 0 }}>
            <VibeCoderChat onWorkflowChanged={(wfId) => { refresh(); setEditorWorkflowId(wfId); setShowEditor(true) }} />
          </div>
        )}

        {/* Right: n8n Editor iframe OR Workflow List */}
        <div style={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
          {showEditor ? (
            /* ── Embedded n8n Editor ── */
            <div style={{
              flex: 1, display: 'flex', flexDirection: 'column',
              borderRadius: 'var(--radius-lg)', overflow: 'hidden',
              border: '1px solid var(--separator)', background: 'var(--bg-primary)',
            }}>
              {/* Mini toolbar above iframe */}
              <div style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '4px var(--space-3)',
                borderBottom: '1px solid var(--separator)',
                background: 'var(--material-regular)', backdropFilter: 'blur(20px)',
                flexShrink: 0,
              }}>
                <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
                  n8n Editor
                  {editorWorkflowId && (
                    <span style={{ marginLeft: 'var(--space-2)', color: 'var(--text-tertiary)', fontSize: 'var(--text-caption2)' }}>
                      Workflow {editorWorkflowId}
                    </span>
                  )}
                </span>
                <div className="flex items-center gap-1">
                  <button
                    onClick={() => { setEditorWorkflowId(null) }}
                    className="hover-bg"
                    title="n8n Home"
                    style={{
                      padding: '2px 8px', borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--separator)', background: 'transparent',
                      color: 'var(--text-secondary)', cursor: 'pointer', fontSize: 'var(--text-caption2)',
                    }}
                  >
                    Home
                  </button>
                  <button
                    onClick={() => api?.openN8nEditor?.(editorWorkflowId || undefined)}
                    className="hover-bg"
                    title="In eigenem Fenster oeffnen"
                    style={{
                      width: 24, height: 24, borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--separator)', background: 'transparent',
                      color: 'var(--text-secondary)', cursor: 'pointer',
                      display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12,
                    }}
                  >
                    &#x2197;
                  </button>
                </div>
              </div>
              {/* iframe */}
              <iframe
                key={`${editorWorkflowId || '__home__'}:${authTick}`}
                src={editorWorkflowId ? `${n8nBaseUrl}/workflow/${editorWorkflowId}` : n8nBaseUrl}
                style={{
                  flex: 1, width: '100%', border: 'none',
                  background: '#262626',
                }}
                allow="clipboard-read; clipboard-write"
              />
            </div>
          ) : (
            /* ── Workflow List (original) ── */
            <div style={{ flex: 1, overflowY: 'auto' }}>
              {error && (
                <div style={{ padding: 'var(--space-3)', color: 'var(--system-red)', fontSize: 'var(--text-footnote)' }}>{error}</div>
              )}
              {loading && workflows.length === 0 ? (
                <div>
                  {[1, 2, 3].map(i => (
                    <div key={i} style={{ height: 56, borderRadius: 'var(--radius-md)', background: 'var(--material-regular)', marginBottom: 'var(--space-2)' }} />
                  ))}
                </div>
              ) : workflows.length === 0 ? (
                <div className="flex flex-col items-center justify-center" style={{ height: 150, color: 'var(--text-secondary)', gap: 'var(--space-2)' }}>
                  <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>Keine Workflows</span>
                  <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)' }}>Nutze den VibeCoder links um einen Workflow zu bauen</span>
                </div>
              ) : (
                <div style={{ borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--material-regular)', backdropFilter: 'blur(20px)' }}>
                  {workflows.map((wf, idx) => (
                    <div key={wf.id}>
                      {idx > 0 && <div style={{ height: 1, background: 'var(--separator)', marginLeft: 'var(--space-4)', marginRight: 'var(--space-4)' }} />}
                      <div className="flex items-center" style={{ minHeight: 56, padding: '0 var(--space-4)', gap: 'var(--space-3)' }}>
                        <span className="flex-shrink-0 rounded-full" style={{ width: 8, height: 8, background: wf.active ? STATUS.active.color : STATUS.inactive.color }} />
                        <div className="flex-1 min-w-0">
                          <div className="truncate" style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-medium)', color: 'var(--text-primary)' }}>{wf.name}</div>
                          <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginTop: 1 }}>ID: {wf.id}</div>
                        </div>
                        <span className="flex-shrink-0" style={{
                          fontSize: 'var(--text-caption2)', fontWeight: 'var(--weight-medium)',
                          padding: '2px 8px', borderRadius: 4,
                          background: `color-mix(in srgb, ${wf.active ? STATUS.active.color : STATUS.inactive.color} 15%, transparent)`,
                          color: wf.active ? STATUS.active.color : STATUS.inactive.color,
                        }}>
                          {wf.active ? 'Active' : 'Inactive'}
                        </span>
                        <div className="flex-shrink-0 flex gap-1">
                          <button onClick={() => wf.active ? handleDeactivate(wf.id) : handleActivate(wf.id)} disabled={actionLoading === wf.id} className="hover-bg" title={wf.active ? 'Deaktivieren' : 'Aktivieren'} style={{ width: 28, height: 28, borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)', background: 'transparent', color: wf.active ? 'var(--system-orange)' : 'var(--system-green)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>
                            {wf.active ? '\u23F8' : '\u25B6'}
                          </button>
                          <button onClick={() => { setEditorWorkflowId(wf.id); setShowEditor(true) }} className="hover-bg" title="Im Editor oeffnen" style={{ width: 28, height: 28, borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)', background: 'transparent', color: 'var(--accent)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>
                            &#x2197;
                          </button>
                          <button onClick={() => handleDelete(wf.id)} disabled={actionLoading === wf.id} className="hover-bg" title="Loeschen" style={{ width: 28, height: 28, borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)', background: 'transparent', color: 'var(--system-red)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>
                            &#x2715;
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
