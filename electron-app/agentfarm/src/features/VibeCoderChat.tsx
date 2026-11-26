import { useEffect, useRef, useState } from 'react'
import { VIBECODER_NOT_CONNECTED } from '../vibecoder'

// VibeCoder steps 4 and 5: the field is a chat with the OpenFang agent brain-n8n. The main process
// (vibecoder-chat.js) talks to OpenFang and to n8n; this page only shows the answers, says when the n8n
// tools are still missing, and asks the person before a workflow is activated.

interface Proposal { id: string; workflowId: string; name: string; claimedName?: string }
interface Line { role: 'user' | 'assistant' | 'note'; content: string }
interface ChatState { n8nTools: boolean; notice: string | null }

const api = typeof window !== 'undefined' ? (window as any).vibemindAgentFarm : null

export function VibeCoderChat({ onWorkflowChanged }: { onWorkflowChanged: (workflowId: string) => void }) {
  const [lines, setLines] = useState<Line[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [state, setState] = useState<ChatState | null>(null)
  const [open, setOpen] = useState<Proposal[]>([])
  const scrollRef = useRef<HTMLDivElement>(null)
  const connected = !!(api?.vibecoderSend && api?.vibecoderDecide)

  useEffect(() => {
    if (!api?.vibecoderState) return
    api.vibecoderState().then((s: ChatState) => setState(s)).catch(() => {})
  }, [])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [lines, open])

  const add = (line: Line) => setLines(prev => [...prev, line])

  const send = async () => {
    const text = input.trim()
    if (!text || sending || !connected) return
    setInput('')
    add({ role: 'user', content: text })
    setSending(true)
    try {
      const result = await api.vibecoderSend(text)
      if (result) setState({ n8nTools: !!result.n8nTools, notice: result.notice ?? null })
      if (!result?.ok) { add({ role: 'note', content: result?.error || VIBECODER_NOT_CONNECTED }); return }
      if (result.reply) add({ role: 'assistant', content: result.reply })
      if (Array.isArray(result.proposals) && result.proposals.length) setOpen(prev => [...prev, ...result.proposals])
      const changed: string[] = Array.isArray(result.changed) ? result.changed : []
      if (changed.length) onWorkflowChanged(changed[changed.length - 1])
    } catch {
      add({ role: 'note', content: VIBECODER_NOT_CONNECTED })
    } finally { setSending(false) }
  }

  const decide = async (proposal: Proposal, yes: boolean) => {
    setOpen(prev => prev.filter(p => p.id !== proposal.id))
    try {
      const result = await api.vibecoderDecide(proposal.id, yes)
      if (!yes) add({ role: 'note', content: `„${proposal.name}" bleibt inaktiv.` })
      else if (result?.activated) { add({ role: 'note', content: `„${proposal.name}" ist aktiv.` }); onWorkflowChanged(proposal.workflowId) }
      else add({ role: 'note', content: result?.error || `„${proposal.name}" wurde nicht aktiviert.` })
    } catch {
      add({ role: 'note', content: `„${proposal.name}" wurde nicht aktiviert.` })
    }
  }

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--bg-primary)', borderRadius: 'var(--radius-lg)',
      border: '1px solid var(--separator)', overflow: 'hidden',
    }}>
      <div style={{
        padding: 'var(--space-3) var(--space-4)', borderBottom: '1px solid var(--separator)',
        background: 'var(--material-regular)',
      }}>
        <span style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
          VibeCoder
        </span>
        {!connected && (
          <p data-vibecoder-notice style={{ margin: 'var(--space-2) 0 0', fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
            {VIBECODER_NOT_CONNECTED}
          </p>
        )}
        {connected && state?.notice && (
          <p data-vibecoder-tools style={{ margin: 'var(--space-2) 0 0', fontSize: 'var(--text-caption1)', color: 'var(--system-orange)' }}>
            {state.notice}
          </p>
        )}
      </div>

      <div ref={scrollRef} style={{
        flex: 1, overflowY: 'auto', padding: 'var(--space-3)',
        display: 'flex', flexDirection: 'column', gap: 'var(--space-2)',
      }}>
        {lines.map((line, i) => (
          <div key={i} style={{
            alignSelf: line.role === 'user' ? 'flex-end' : 'flex-start', maxWidth: '85%',
            padding: 'var(--space-2) var(--space-3)', borderRadius: 'var(--radius-md)',
            background: line.role === 'user' ? 'var(--accent)' : line.role === 'note' ? 'transparent' : 'var(--fill-secondary)',
            color: line.role === 'user' ? '#fff' : line.role === 'note' ? 'var(--text-secondary)' : 'var(--text-primary)',
            fontSize: 'var(--text-footnote)', lineHeight: 1.5, whiteSpace: 'pre-wrap', wordBreak: 'break-word',
          }}>
            {line.content}
          </div>
        ))}
        {open.map(proposal => (
          <div key={proposal.id} data-vibecoder-proposal style={{
            alignSelf: 'flex-start', padding: 'var(--space-2) var(--space-3)', borderRadius: 'var(--radius-md)',
            border: '1px solid var(--accent)', fontSize: 'var(--text-footnote)', color: 'var(--text-primary)',
          }}>
            <div>Workflow „{proposal.name}" ({proposal.workflowId}) aktivieren?</div>
            {proposal.claimedName && (
              <div data-vibecoder-name-differs style={{ marginTop: 'var(--space-1)', fontSize: 'var(--text-caption1)', color: 'var(--system-orange)' }}>
                Der VibeCoder nannte ihn „{proposal.claimedName}"; in n8n heißt er anders.
              </div>
            )}
            <div style={{ display: 'flex', gap: 'var(--space-2)', marginTop: 'var(--space-2)' }}>
              <button onClick={() => decide(proposal, true)} style={{
                padding: '4px 12px', borderRadius: 'var(--radius-sm)', border: 'none', cursor: 'pointer',
                background: 'var(--system-green)', color: '#fff', fontWeight: 600,
              }}>Ja, aktivieren</button>
              <button onClick={() => decide(proposal, false)} style={{
                padding: '4px 12px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)',
                cursor: 'pointer', background: 'transparent', color: 'var(--text-secondary)',
              }}>Nein</button>
            </div>
          </div>
        ))}
        {sending && (
          <div style={{ alignSelf: 'flex-start', color: 'var(--text-tertiary)', fontSize: 'var(--text-caption1)' }}>
            VibeCoder denkt nach …
          </div>
        )}
      </div>

      <div style={{ padding: 'var(--space-2) var(--space-3)', borderTop: '1px solid var(--separator)', display: 'flex', gap: 'var(--space-2)' }}>
        <textarea
          value={input} onChange={e => setInput(e.target.value)} rows={1} disabled={!connected}
          onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send() } }}
          placeholder="Workflow beschreiben oder Änderung vorschlagen …"
          style={{
            flex: 1, resize: 'none', padding: 'var(--space-2)', borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--separator)', background: 'var(--fill-secondary)', color: 'var(--text-primary)',
            fontSize: 'var(--text-footnote)', fontFamily: 'inherit', outline: 'none', minHeight: 36, maxHeight: 120,
          }}
        />
        <button onClick={send} disabled={sending || !input.trim() || !connected} style={{
          width: 36, height: 36, borderRadius: 'var(--radius-sm)', border: 'none',
          cursor: sending ? 'wait' : 'pointer', background: input.trim() ? 'var(--accent)' : 'var(--fill-tertiary)',
          color: input.trim() ? '#fff' : 'var(--text-tertiary)', fontSize: 16, flexShrink: 0,
        }}>&#x2191;</button>
      </div>
    </div>
  )
}
