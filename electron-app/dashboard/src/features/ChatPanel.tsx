import { useState, useRef, useEffect, useCallback } from 'react'
import type { ChatMessage } from '../types'
import { sendChatMessage, usePythonMessages } from '../hooks/useIPC'

/* ── Safe text rendering (no dangerouslySetInnerHTML) ──────── */

/**
 * Renders message content as React elements.
 * Only renders plain text with line breaks for safety.
 * Content comes from VibeMind's own Python backend (trusted source)
 * but we avoid innerHTML for defense-in-depth.
 */
function MessageContent({ text }: { text: string }) {
  const lines = text.split('\n')
  return (
    <span>
      {lines.map((line, i) => (
        <span key={i}>
          {i > 0 && <br />}
          {renderInlineFormatting(line)}
        </span>
      ))}
    </span>
  )
}

function renderInlineFormatting(line: string): React.ReactNode[] {
  const parts: React.ReactNode[] = []
  let remaining = line
  let key = 0

  while (remaining.length > 0) {
    // Bold: **text**
    const boldMatch = remaining.match(/^(.*?)\*\*(.+?)\*\*/)
    if (boldMatch) {
      if (boldMatch[1]) parts.push(<span key={key++}>{boldMatch[1]}</span>)
      parts.push(<strong key={key++}>{boldMatch[2]}</strong>)
      remaining = remaining.slice(boldMatch[0].length)
      continue
    }

    // Inline code: `text`
    const codeMatch = remaining.match(/^(.*?)`([^`]+)`/)
    if (codeMatch) {
      if (codeMatch[1]) parts.push(<span key={key++}>{codeMatch[1]}</span>)
      parts.push(
        <code key={key++} style={{
          padding: '1px 5px',
          borderRadius: 3,
          background: 'var(--code-bg)',
          border: '1px solid var(--code-border)',
          fontFamily: '"SF Mono", Monaco, Menlo, monospace',
          fontSize: '0.9em',
          color: 'var(--code-text)',
        }}>
          {codeMatch[2]}
        </code>
      )
      remaining = remaining.slice(codeMatch[0].length)
      continue
    }

    // No more formatting - rest is plain text
    parts.push(<span key={key++}>{remaining}</span>)
    break
  }

  return parts
}

/* ── Component ─────────────────────────────────────────────── */

let messageIdCounter = 0
function nextId(): string {
  return `msg-${Date.now()}-${++messageIdCounter}`
}

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  // Auto-scroll on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // Focus input on mount
  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Listen for chat responses from Python
  usePythonMessages('chat_response', useCallback((msg: Record<string, unknown>) => {
    const response: ChatMessage = {
      id: nextId(),
      role: 'assistant',
      content: (msg.message as string) || 'Keine Antwort',
      timestamp: Date.now(),
      event_type: msg.event_type as string | undefined,
    }
    setMessages(prev => [...prev, response])
    setLoading(false)
  }, []))

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return

    setInput('')
    setLoading(true)

    // Add user message
    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])

    try {
      await sendChatMessage(text)
      // Response comes via usePythonMessages callback
    } catch (e) {
      setMessages(prev => [...prev, {
        id: nextId(),
        role: 'system',
        content: `Fehler: ${e instanceof Error ? e.message : String(e)}`,
        timestamp: Date.now(),
      }])
      setLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="flex flex-col h-full" style={{ maxHeight: 'calc(100vh - 100px)' }}>
      {/* Header */}
      <div className="flex items-center justify-between flex-shrink-0" style={{ marginBottom: 'var(--space-3)' }}>
        <h2 style={{ fontSize: 'var(--text-title3)', fontWeight: 'var(--weight-bold)', letterSpacing: 'var(--tracking-tight)' }}>
          Chat
        </h2>
        <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>
          Text-Eingabe &#x2192; Intent Orchestrator
        </span>
      </div>

      {/* Messages */}
      <div
        className="flex-1 overflow-y-auto"
        style={{
          borderRadius: 'var(--radius-md)',
          background: 'var(--material-regular)',
          backdropFilter: 'blur(20px)',
          padding: 'var(--space-3)',
          marginBottom: 'var(--space-3)',
          minHeight: 200,
        }}
      >
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center" style={{ height: '100%', minHeight: 200, color: 'var(--text-tertiary)', gap: 'var(--space-2)' }}>
            <span style={{ fontSize: 32, opacity: 0.5 }}>&#x1F4AC;</span>
            <span style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-medium)' }}>
              Text-basierte Steuerung
            </span>
            <span style={{ fontSize: 'var(--text-caption1)', textAlign: 'center', maxWidth: 300, lineHeight: 'var(--leading-relaxed)' }}>
              Gleicher Pfad wie Voice: Deine Eingabe wird klassifiziert und vom passenden Agent ausgefuehrt.
            </span>
            <div style={{ marginTop: 'var(--space-3)', display: 'flex', flexDirection: 'column', gap: 'var(--space-1)' }}>
              {[
                'Zeig mir meine Bubbles',
                'Erstelle eine Idee: API Design',
                'Wie ist der Code-Status?',
              ].map(example => (
                <button
                  key={example}
                  onClick={() => { setInput(example); inputRef.current?.focus() }}
                  className="hover-bg"
                  style={{
                    padding: '4px 10px',
                    borderRadius: 'var(--radius-sm)',
                    border: '1px solid var(--separator)',
                    background: 'transparent',
                    color: 'var(--text-secondary)',
                    cursor: 'pointer',
                    fontSize: 'var(--text-caption1)',
                    textAlign: 'left',
                  }}
                >
                  {example}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            {messages.map(msg => (
              <div
                key={msg.id}
                className="animate-fade-in"
                style={{
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: msg.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                {/* Bubble */}
                <div style={{
                  maxWidth: '80%',
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: msg.role === 'user'
                    ? 'var(--radius-md) var(--radius-md) var(--radius-sm) var(--radius-md)'
                    : 'var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm)',
                  background: msg.role === 'user'
                    ? 'var(--accent)'
                    : msg.role === 'system'
                      ? 'rgba(255,69,58,0.1)'
                      : 'var(--bg-tertiary)',
                  color: msg.role === 'user' ? 'var(--accent-contrast)' : 'var(--text-primary)',
                }}>
                  <div style={{
                    fontSize: 'var(--text-footnote)',
                    lineHeight: 'var(--leading-relaxed)',
                    wordBreak: 'break-word',
                  }}>
                    <MessageContent text={msg.content} />
                  </div>
                </div>

                {/* Meta line */}
                <div className="flex items-center gap-2" style={{ marginTop: 2 }}>
                  {msg.event_type && (
                    <span className="font-mono" style={{
                      fontSize: 'var(--text-caption2)',
                      color: 'var(--system-blue)',
                      padding: '0 4px',
                      borderRadius: 3,
                      background: 'rgba(10,132,255,0.1)',
                    }}>
                      {msg.event_type}
                    </span>
                  )}
                  <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-quaternary)' }}>
                    {new Date(msg.timestamp).toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })}
                  </span>
                </div>
              </div>
            ))}

            {/* Loading indicator */}
            {loading && (
              <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                <div style={{
                  padding: 'var(--space-2) var(--space-3)',
                  borderRadius: 'var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm)',
                  background: 'var(--bg-tertiary)',
                  color: 'var(--text-tertiary)',
                  fontSize: 'var(--text-footnote)',
                }}>
                  Verarbeite...
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>
        )}
      </div>

      {/* Input Bar */}
      <div
        className="flex items-center flex-shrink-0 gap-2"
        style={{
          padding: 'var(--space-2) var(--space-3)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--material-regular)',
          border: '1px solid var(--separator)',
        }}
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Nachricht eingeben..."
          disabled={loading}
          className="focus-ring"
          style={{
            flex: 1,
            border: 'none',
            background: 'transparent',
            color: 'var(--text-primary)',
            fontSize: 'var(--text-footnote)',
            outline: 'none',
            padding: '6px 0',
          }}
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || loading}
          style={{
            width: 32,
            height: 32,
            borderRadius: 'var(--radius-sm)',
            border: 'none',
            background: input.trim() && !loading ? 'var(--accent)' : 'var(--fill-tertiary)',
            color: input.trim() && !loading ? 'var(--accent-contrast)' : 'var(--text-tertiary)',
            cursor: input.trim() && !loading ? 'pointer' : 'default',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 16,
            transition: 'all 150ms var(--ease-smooth)',
          }}
        >
          &#x2191;
        </button>
      </div>
    </div>
  )
}
