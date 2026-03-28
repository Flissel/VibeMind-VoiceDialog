import { useState, useCallback, useRef, useEffect } from 'react'

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

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

interface ChecklistItem {
  id: string
  label: string
  prompt: string
  required: boolean
  type: 'text' | 'select' | 'multi'
  options: string[] | null
}

interface AutoCheck {
  id: string
  label: string
  ok: boolean
  detail: string
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
    try { setWorkflows((await api.n8nList())?.workflows ?? []) }
    catch (e) { setError(e instanceof Error ? e.message : String(e)) }
    finally { setLoading(false) }
  }, [])
  return { workflows, loading, error, refresh }
}

const STATUS = {
  active: { color: 'var(--system-green)', label: 'Active' },
  inactive: { color: 'var(--system-orange)', label: 'Inactive' },
} as const

/* ── Checklist Phase ─────────────────────────────────────── */

function ChecklistPhase({ onComplete, existingSessionId, existingDescription }: {
  onComplete: (sessionId: string, response: string) => void
  existingSessionId?: string | null
  existingDescription?: string | null
}) {
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [items, setItems] = useState<ChecklistItem[]>([])
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [autoChecks, setAutoChecks] = useState<AutoCheck[]>([])
  const [completing, setCompleting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Start or reuse session on mount
  useEffect(() => {
    if (!api?.n8nChatStart) return
    const desc = existingDescription || ''
    api.n8nChatStart(desc).then((result: any) => {
      if (result?.session_id) {
        // If a session was already started by Voice/Chat, use that instead
        const sid = existingSessionId || result.session_id
        setSessionId(sid)
        setItems(result.checklist_items || [])
        const initialAnswers = result.checklist || {}
        // Pre-fill description from Voice/Chat trigger
        if (desc && !initialAnswers.description) {
          initialAnswers.description = desc
        }
        setAnswers(initialAnswers)
        // If we have a pre-filled description, push it to backend
        if (desc && sid) {
          api.n8nChatChecklist?.(sid, 'answer', 'description', desc)
        }
      }
    })
  }, [existingSessionId, existingDescription])

  const updateItem = async (itemId: string, value: string) => {
    if (!sessionId || !api?.n8nChatChecklist) return
    const newAnswers = { ...answers, [itemId]: value }
    setAnswers(newAnswers)
    try {
      await api.n8nChatChecklist(sessionId, 'answer', itemId, value)
    } catch { /* ignore */ }
  }

  const handleComplete = async () => {
    if (!sessionId || !api?.n8nChatChecklist) return
    setCompleting(true); setError(null)
    try {
      const result = await api.n8nChatChecklist(sessionId, 'complete', '', '')
      if (result?.success) {
        setAutoChecks(result.auto_checks || [])
        onComplete(sessionId, result.response || '')
      } else {
        setError(result?.message || 'Fehler beim Abschliessen')
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally { setCompleting(false) }
  }

  const requiredComplete = items
    .filter(i => i.required)
    .every(i => answers[i.id]?.trim())

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--separator)', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: 'var(--space-3) var(--space-4)',
        borderBottom: '1px solid var(--separator)',
        background: 'var(--material-regular)', backdropFilter: 'blur(20px)',
      }}>
        <span style={{
          fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-primary)',
        }}>
          VibeCoder — Workflow Setup
        </span>
        <span style={{
          marginLeft: 'var(--space-2)',
          fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)',
        }}>
          Alle Details vor dem Chat definieren
        </span>
      </div>

      {/* Checklist Items */}
      <div style={{ flex: 1, overflowY: 'auto', padding: 'var(--space-3)' }}>
        {items.map(item => (
          <div key={item.id} style={{
            marginBottom: 'var(--space-3)',
            padding: 'var(--space-3)',
            borderRadius: 'var(--radius-md)',
            background: 'var(--fill-secondary)',
            border: `1px solid ${answers[item.id] ? 'var(--system-green)' : item.required ? 'var(--system-orange)' : 'var(--separator)'}`,
            transition: 'border-color 200ms ease',
          }}>
            {/* Label + Status */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginBottom: 'var(--space-2)' }}>
              <span style={{
                width: 18, height: 18, borderRadius: 4,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 11, fontWeight: 700,
                background: answers[item.id]
                  ? 'var(--system-green)'
                  : 'var(--fill-tertiary)',
                color: answers[item.id] ? '#fff' : 'var(--text-tertiary)',
              }}>
                {answers[item.id] ? '\u2713' : ' '}
              </span>
              <span style={{
                fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-medium)',
                color: 'var(--text-primary)',
              }}>
                {item.label}
                {item.required && <span style={{ color: 'var(--system-orange)', marginLeft: 4, fontSize: 10 }}>*</span>}
              </span>
            </div>

            {/* Input */}
            {item.type === 'text' ? (
              <textarea
                value={answers[item.id] || ''}
                onChange={e => updateItem(item.id, e.target.value)}
                placeholder={item.prompt}
                rows={2}
                style={{
                  width: '100%', resize: 'vertical',
                  padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--separator)', background: 'var(--bg-primary)',
                  color: 'var(--text-primary)', fontSize: 'var(--text-caption1)',
                  fontFamily: 'inherit', outline: 'none',
                }}
              />
            ) : item.type === 'select' ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                {item.options?.map(opt => (
                  <button
                    key={opt}
                    onClick={() => updateItem(item.id, opt)}
                    style={{
                      padding: '4px 12px', borderRadius: 'var(--radius-sm)',
                      border: '1px solid var(--separator)',
                      background: answers[item.id] === opt ? 'var(--tint)' : 'var(--bg-primary)',
                      color: answers[item.id] === opt ? '#fff' : 'var(--text-secondary)',
                      cursor: 'pointer', fontSize: 'var(--text-caption1)',
                      transition: 'all 150ms ease',
                    }}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            ) : item.type === 'multi' ? (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)' }}>
                {item.options?.map(opt => {
                  const selected = (answers[item.id] || '').split(', ').includes(opt)
                  return (
                    <button
                      key={opt}
                      onClick={() => {
                        const current = (answers[item.id] || '').split(', ').filter(Boolean)
                        const next = selected
                          ? current.filter(s => s !== opt)
                          : [...current, opt]
                        updateItem(item.id, next.join(', '))
                      }}
                      style={{
                        padding: '4px 12px', borderRadius: 'var(--radius-sm)',
                        border: '1px solid var(--separator)',
                        background: selected ? 'var(--tint)' : 'var(--bg-primary)',
                        color: selected ? '#fff' : 'var(--text-secondary)',
                        cursor: 'pointer', fontSize: 'var(--text-caption1)',
                        transition: 'all 150ms ease',
                      }}
                    >
                      {opt}
                    </button>
                  )
                })}
              </div>
            ) : null}
          </div>
        ))}

        {/* Auto Checks (shown after complete attempt) */}
        {autoChecks.length > 0 && (
          <div style={{ marginTop: 'var(--space-2)' }}>
            <div style={{
              fontSize: 'var(--text-caption1)', fontWeight: 600,
              color: 'var(--text-secondary)', marginBottom: 'var(--space-1)',
            }}>
              System-Checks
            </div>
            {autoChecks.map(check => (
              <div key={check.id} style={{
                display: 'flex', alignItems: 'center', gap: 'var(--space-2)',
                padding: '4px 0', fontSize: 'var(--text-caption1)',
              }}>
                <span style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: check.ok ? 'var(--system-green)' : 'var(--system-red)',
                  flexShrink: 0,
                }} />
                <span style={{ color: 'var(--text-primary)' }}>{check.label}</span>
                <span style={{ color: 'var(--text-tertiary)', fontSize: 'var(--text-caption2)' }}>
                  {check.detail}
                </span>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div style={{
            marginTop: 'var(--space-2)',
            padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)',
            background: 'color-mix(in srgb, var(--system-red) 10%, transparent)',
            color: 'var(--system-red)', fontSize: 'var(--text-caption1)',
          }}>
            {error}
          </div>
        )}
      </div>

      {/* Start Button */}
      <div style={{
        padding: 'var(--space-3) var(--space-4)',
        borderTop: '1px solid var(--separator)',
        display: 'flex', justifyContent: 'flex-end',
      }}>
        <button
          onClick={handleComplete}
          disabled={!requiredComplete || completing}
          style={{
            padding: '8px 24px', borderRadius: 'var(--radius-sm)',
            border: 'none',
            cursor: (!requiredComplete || completing) ? 'not-allowed' : 'pointer',
            fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-semibold)',
            background: requiredComplete ? 'var(--accent)' : 'var(--fill-tertiary)',
            color: requiredComplete ? '#fff' : 'var(--text-tertiary)',
            transition: 'all 150ms ease',
          }}
        >
          {completing ? 'Pruefe...' : 'VibeCoder starten'}
        </button>
      </div>
    </div>
  )
}

/* ── Chat Phase ──────────────────────────────────────────── */

function ChatPhase({ sessionId, initialMessage, onWorkflowDeployed }: {
  sessionId: string
  initialMessage: string
  onWorkflowDeployed: () => void
}) {
  const [messages, setMessages] = useState<ChatMessage[]>(
    initialMessage ? [{ role: 'assistant', content: initialMessage }] : []
  )
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [hasWorkflow, setHasWorkflow] = useState(false)
  const [workflowName, setWorkflowName] = useState<string | null>(null)
  const [workflowId, setWorkflowId] = useState<string | null>(null)
  const [deploying, setDeploying] = useState(false)
  const scrollRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages])

  const sendMessage = async () => {
    if (!input.trim() || !api?.n8nChatMessage || sending) return
    const text = input.trim()
    setInput('')
    setMessages(prev => [...prev, { role: 'user', content: text }])
    setSending(true)
    try {
      const result = await api.n8nChatMessage(sessionId, text)
      if (result?.response) {
        setMessages(prev => [...prev, { role: 'assistant', content: result.response }])
        setHasWorkflow(!!result.has_workflow)
        if (result.workflow_name) setWorkflowName(result.workflow_name)
        if (result.workflow_id) setWorkflowId(result.workflow_id)
      } else if (result?.message) {
        setMessages(prev => [...prev, { role: 'assistant', content: result.message }])
      }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Fehler: ${e}` }])
    } finally { setSending(false) }
  }

  const handleDeploy = async () => {
    if (!api?.n8nChatDeploy || deploying) return
    setDeploying(true)
    try {
      const result = await api.n8nChatDeploy(sessionId)
      if (result?.response) setMessages(prev => [...prev, { role: 'assistant', content: result.response }])
      else if (result?.message) setMessages(prev => [...prev, { role: 'assistant', content: result.message }])
      if (result?.workflow_id) { setWorkflowId(result.workflow_id); onWorkflowDeployed() }
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: `Deploy-Fehler: ${e}` }])
    } finally { setDeploying(false) }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage() }
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--separator)', overflow: 'hidden',
    }}>
      {/* Header */}
      <div style={{
        padding: 'var(--space-3) var(--space-4)',
        borderBottom: '1px solid var(--separator)',
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        background: 'var(--material-regular)', backdropFilter: 'blur(20px)',
      }}>
        <div>
          <span style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
            VibeCoder Chat
          </span>
          {workflowName && <span style={{ marginLeft: 'var(--space-2)', fontSize: 'var(--text-caption2)', color: 'var(--tint)' }}>{workflowName}</span>}
          {workflowId && <span style={{ marginLeft: 'var(--space-1)', fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>(deployed)</span>}
        </div>
        {hasWorkflow && (
          <button onClick={handleDeploy} disabled={deploying} style={{
            padding: '4px 12px', borderRadius: 'var(--radius-sm)', border: 'none',
            cursor: deploying ? 'wait' : 'pointer', fontSize: 'var(--text-caption1)', fontWeight: 600,
            background: 'var(--system-green)', color: '#fff',
          }}>
            {deploying ? '...' : workflowId ? 'Update' : 'Deploy'}
          </button>
        )}
      </div>

      {/* Messages */}
      <div ref={scrollRef} style={{
        flex: 1, overflowY: 'auto', padding: 'var(--space-3)',
        display: 'flex', flexDirection: 'column', gap: 'var(--space-2)',
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '85%',
            padding: 'var(--space-2) var(--space-3)',
            borderRadius: msg.role === 'user'
              ? 'var(--radius-md) var(--radius-md) var(--radius-sm) var(--radius-md)'
              : 'var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm)',
            background: msg.role === 'user' ? 'var(--tint)' : 'var(--fill-secondary)',
            color: msg.role === 'user' ? '#fff' : 'var(--text-primary)',
            fontSize: 'var(--text-footnote)', lineHeight: 1.5,
            whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {msg.content}
          </div>
        ))}
        {sending && (
          <div style={{
            alignSelf: 'flex-start',
            padding: 'var(--space-2) var(--space-3)', borderRadius: 'var(--radius-md)',
            background: 'var(--fill-secondary)', color: 'var(--text-tertiary)',
            fontSize: 'var(--text-caption1)',
          }}>
            VibeCoder denkt nach...
          </div>
        )}
      </div>

      {/* Input */}
      <div style={{
        padding: 'var(--space-2) var(--space-3)',
        borderTop: '1px solid var(--separator)',
        display: 'flex', gap: 'var(--space-2)', alignItems: 'flex-end',
      }}>
        <textarea
          value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Workflow beschreiben oder Aenderung vorschlagen..."
          rows={1}
          style={{
            flex: 1, resize: 'none',
            padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--separator)', background: 'var(--fill-secondary)',
            color: 'var(--text-primary)', fontSize: 'var(--text-footnote)',
            fontFamily: 'inherit', outline: 'none', minHeight: 36, maxHeight: 120,
          }}
          onFocus={e => e.target.style.borderColor = 'var(--accent)'}
          onBlur={e => e.target.style.borderColor = 'var(--separator)'}
        />
        <button
          onClick={sendMessage} disabled={sending || !input.trim()}
          style={{
            width: 36, height: 36, borderRadius: 'var(--radius-sm)',
            border: 'none', cursor: sending ? 'wait' : 'pointer',
            background: input.trim() ? 'var(--accent)' : 'var(--fill-tertiary)',
            color: input.trim() ? '#fff' : 'var(--text-tertiary)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, flexShrink: 0,
          }}
        >
          &#x2191;
        </button>
      </div>
    </div>
  )
}

/* ── VibeCoder Container (Checklist → Chat) ──────────────── */

function VibeCoderPanel({ onWorkflowDeployed }: { onWorkflowDeployed: () => void }) {
  const [phase, setPhase] = useState<'checklist' | 'chat'>('checklist')
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [initialMsg, setInitialMsg] = useState('')
  const [pendingSessionId, setPendingSessionId] = useState<string | null>(null)
  const [pendingDescription, setPendingDescription] = useState<string | null>(null)

  // Listen for VibeCoder session triggered by Voice/Chat
  useEffect(() => {
    if (!api?.onMessage) return
    api.onMessage((msg: any) => {
      if (msg?.type === 'n8n_vibecoder_checklist_needed' && msg.session_id) {
        // A Voice/Chat workflow request triggered a checklist — use this session
        setPendingSessionId(msg.session_id)
        setPendingDescription(msg.description || '')
        setPhase('checklist')
      }
    })
  }, [])

  const handleChecklistComplete = (sid: string, response: string) => {
    setSessionId(sid)
    setInitialMsg(response)
    setPhase('chat')
    setPendingSessionId(null)
    setPendingDescription(null)
  }

  const handleReset = () => {
    setPhase('checklist')
    setSessionId(null)
    setInitialMsg('')
    setPendingSessionId(null)
    setPendingDescription(null)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {phase === 'chat' && (
        <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 'var(--space-1)' }}>
          <button onClick={handleReset} style={{
            padding: '2px 8px', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--separator)', background: 'transparent',
            color: 'var(--text-tertiary)', cursor: 'pointer', fontSize: 'var(--text-caption2)',
          }}>
            Neue Session
          </button>
        </div>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        {phase === 'checklist' ? (
          <ChecklistPhase
            onComplete={handleChecklistComplete}
            existingSessionId={pendingSessionId}
            existingDescription={pendingDescription}
          />
        ) : sessionId ? (
          <ChatPhase sessionId={sessionId} initialMessage={initialMsg} onWorkflowDeployed={onWorkflowDeployed} />
        ) : null}
      </div>
    </div>
  )
}

/* ── Main Component ──────────────────────────────────────── */

export function WorkflowBuilder() {
  const status = useN8nStatus()
  const { workflows, loading, error, refresh } = useN8nWorkflows()
  const [showVibeCoder, setShowVibeCoder] = useState(true)
  const [actionLoading, setActionLoading] = useState<string | null>(null)

  useState(() => { status.refresh(); refresh() })

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
              background: showVibeCoder ? 'var(--tint)' : 'transparent',
              color: showVibeCoder ? '#fff' : 'var(--text-secondary)',
              cursor: 'pointer', fontSize: 'var(--text-caption1)', fontWeight: 600,
            }}
          >
            VibeCoder
          </button>
          <button onClick={() => api?.openN8nEditor?.()} className="hover-bg" style={{
            padding: '4px 10px', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--separator)', background: 'transparent',
            color: 'var(--system-blue)', cursor: 'pointer', fontSize: 'var(--text-caption1)',
          }}>
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

      {/* Main: VibeCoder + Workflow List */}
      <div style={{ flex: 1, display: 'flex', gap: 'var(--space-3)', overflow: 'hidden' }}>
        {showVibeCoder && (
          <div style={{ flex: '0 0 50%', minHeight: 0 }}>
            <VibeCoderPanel onWorkflowDeployed={refresh} />
          </div>
        )}
        <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
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
                      <button onClick={() => api?.openN8nEditor?.(wf.id)} className="hover-bg" title="In n8n oeffnen" style={{ width: 28, height: 28, borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)', background: 'transparent', color: 'var(--system-blue)', cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 12 }}>
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
      </div>
    </div>
  )
}
