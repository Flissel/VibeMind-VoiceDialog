import { useState, useRef, useEffect, useCallback } from 'react'
import type { ChatMessage } from '../types'
import { sendChatMessage, usePythonMessages } from '../hooks/useIPC'

/* ── Event Manual Data ─────────────────────────────────────── */

interface EventEntry {
  label: string
  text: string
}

interface EventCategory {
  name: string
  color: string
  events: EventEntry[]
}

const EVENT_CATEGORIES: EventCategory[] = [
  {
    name: 'Bubbles',
    color: 'var(--system-blue)',
    events: [
      { label: 'list', text: 'Zeig mir meine Bubbles' },
      { label: 'create', text: 'Erstelle Bubble Marketing' },
      { label: 'enter', text: 'Geh in Marketing' },
      { label: 'find', text: 'Finde Bubble mit Design' },
      { label: 'exit', text: 'Zurück' },
      { label: 'delete', text: 'Lösche Bubble Marketing' },
      { label: 'stats', text: 'Bubble Statistiken' },
    ],
  },
  {
    name: 'Ideas',
    color: 'var(--system-purple)',
    events: [
      { label: 'list', text: 'Zeig alle Ideen' },
      { label: 'create', text: 'Notiere: API Design Konzept' },
      { label: 'find', text: 'Finde Idee API' },
      { label: 'auto_link', text: 'Verlinke die Ideen sinnvoll' },
      { label: 'expand', text: 'Erweitere die Ideen' },
      { label: 'summarize', text: 'Fasse die Ideen zusammen' },
      { label: 'format action', text: 'Formatiere in Aktionslisten' },
      { label: 'format pros/cons', text: 'Formatiere als Pro/Contra' },
      { label: 'format hierarchy', text: 'Formatiere als Hierarchie' },
      { label: 'format specs', text: 'Formatiere als technische Spezifikation' },
      { label: 'whitepaper', text: 'Erstelle ein Whitepaper' },
      { label: 'explore start', text: 'Starte tiefe Exploration' },
      { label: 'explore stop', text: 'Stoppe Exploration' },
      { label: 'explore status', text: 'Explorationsstatus' },
    ],
  },
  {
    name: 'Code',
    color: 'var(--system-green)',
    events: [
      { label: 'generate', text: 'Erstelle eine Hello World App' },
      { label: 'status', text: 'Code Status' },
      { label: 'list', text: 'Zeig alle Code-Projekte' },
      { label: 'preview start', text: 'Starte Code Preview' },
      { label: 'preview stop', text: 'Stoppe Code Preview' },
      { label: 'cancel', text: 'Code Generation abbrechen' },
    ],
  },
  {
    name: 'Desktop',
    color: 'var(--system-orange)',
    events: [
      { label: 'open Chrome', text: 'Öffne Chrome' },
      { label: 'screenshot', text: 'Screenshot' },
      { label: 'click OK', text: 'Klick auf OK' },
      { label: 'type hello', text: 'Tippe hello' },
      { label: 'scroll up', text: 'Scroll hoch' },
      { label: 'scroll down', text: 'Scroll runter' },
      { label: 'press Enter', text: 'Drücke Enter' },
    ],
  },
  {
    name: 'Research',
    color: 'var(--system-teal)',
    events: [
      { label: 'web search', text: 'Recherchiere AI Trends 2026' },
      { label: 'scrape URL', text: 'Scrape https://example.com' },
      { label: 'summarize URL', text: 'Fasse https://example.com zusammen' },
      { label: 'to idea', text: 'Recherchiere AI Trends und speichere als Idee' },
    ],
  },
  {
    name: 'Rowboat',
    color: '#ff8855',
    events: [
      { label: 'search', text: 'Rowboat suche nach Test' },
      { label: 'status', text: 'Rowboat Status' },
      { label: 'open', text: 'Öffne Rowboat' },
      { label: 'docker start', text: 'Starte Rowboat Docker' },
      { label: 'docker stop', text: 'Stoppe Rowboat Docker' },
      { label: 'docker status', text: 'Rowboat Docker Status' },
    ],
  },
  {
    name: 'N8n',
    color: '#ff6d5a',
    events: [
      { label: 'list', text: 'Zeig alle Workflows' },
      { label: 'status', text: 'N8n Status' },
      { label: 'generate', text: 'Erstelle einen Email Workflow' },
      { label: 'activate', text: 'Aktiviere Workflow Test' },
      { label: 'deactivate', text: 'Deaktiviere Workflow Test' },
      { label: 'execute', text: 'Führe Workflow Test aus' },
    ],
  },
  {
    name: 'AgentFarm',
    color: 'var(--system-yellow)',
    events: [
      { label: 'status', text: 'Agent Farm Status' },
      { label: 'list teams', text: 'Welche Teams gibt es?' },
      { label: 'list templates', text: 'Zeig Agent Templates' },
      { label: 'open', text: 'Öffne AgentFarm' },
      { label: 'pipeline start', text: 'Starte Code Pipeline für Test App' },
      { label: 'pipeline status', text: 'Pipeline Status' },
    ],
  },
  {
    name: 'Schedule',
    color: '#88aaff',
    events: [
      { label: 'list', text: 'Zeig geplante Aufgaben' },
      { label: 'status', text: 'Schedule Status' },
      { label: 'create', text: 'Erinnere mich morgen um 9 an Meeting' },
    ],
  },
  {
    name: 'Minibook',
    color: '#aa88ff',
    events: [
      { label: 'status', text: 'Minibook Status' },
      { label: 'list projects', text: 'Zeig Minibook Projekte' },
      { label: 'collaborate', text: 'Recherchiere AI Trends und erstelle Ideen dazu' },
    ],
  },
  {
    name: 'MiroFish',
    color: '#55ddcc',
    events: [
      { label: 'status', text: 'MiroFish Status' },
      { label: 'list projects', text: 'MiroFish Projekte' },
      { label: 'predict', text: 'MiroFish Vorhersage für Marketing Kampagne' },
      { label: 'docker start', text: 'Starte MiroFish Docker' },
      { label: 'docker stop', text: 'Stoppe MiroFish Docker' },
      { label: 'docker status', text: 'MiroFish Docker Status' },
    ],
  },
  {
    name: 'Messaging',
    color: '#66dd88',
    events: [
      { label: 'send WhatsApp', text: 'Sende WhatsApp an Max: Hallo!' },
      { label: 'send Telegram', text: 'Sende Telegram an Max: Hallo!' },
      { label: 'read messages', text: 'Zeig neue Nachrichten' },
      { label: 'web search', text: 'Suche im Web nach Claude API' },
    ],
  },
  {
    name: 'System',
    color: 'var(--text-secondary)',
    events: [
      { label: 'greeting', text: 'Hallo!' },
      { label: 'help', text: 'Hilfe' },
      { label: 'eval stats', text: 'Zeig Klassifizierungsgenauigkeit' },
    ],
  },
]

/* ── Event Manual Sidebar ──────────────────────────────────── */

function EventManual({ onFire, disabled }: { onFire: (text: string) => void; disabled: boolean }) {
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  const toggle = (name: string) => {
    setExpanded(prev => ({ ...prev, [name]: !prev[name] }))
  }

  return (
    <div style={{
      width: 260,
      flexShrink: 0,
      overflowY: 'auto',
      borderRight: '1px solid var(--separator)',
      padding: 'var(--space-2)',
      display: 'flex',
      flexDirection: 'column',
      gap: 2,
    }}>
      {EVENT_CATEGORIES.map(cat => {
        const isOpen = expanded[cat.name] ?? false
        return (
          <div key={cat.name}>
            {/* Category header */}
            <button
              onClick={() => toggle(cat.name)}
              style={{
                width: '100%',
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '5px 6px',
                border: 'none',
                borderRadius: 'var(--radius-sm)',
                background: 'transparent',
                color: 'var(--text-primary)',
                cursor: 'pointer',
                fontSize: 'var(--text-caption1)',
                fontWeight: 'var(--weight-semibold)',
                textAlign: 'left',
                letterSpacing: 'var(--tracking-wide)',
                textTransform: 'uppercase' as const,
              }}
            >
              <span style={{
                display: 'inline-block',
                width: 8,
                height: 8,
                borderRadius: '50%',
                background: cat.color,
                flexShrink: 0,
              }} />
              <span style={{ flex: 1 }}>{cat.name}</span>
              <span style={{
                fontSize: 10,
                color: 'var(--text-tertiary)',
                transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)',
                transition: 'transform 150ms ease',
              }}>
                {'\u25B6'}
              </span>
            </button>

            {/* Event buttons */}
            {isOpen && (
              <div style={{
                display: 'flex',
                flexWrap: 'wrap',
                gap: 3,
                padding: '3px 0 6px 14px',
              }}>
                {cat.events.map(ev => (
                  <button
                    key={ev.label}
                    onClick={() => onFire(ev.text)}
                    disabled={disabled}
                    title={ev.text}
                    style={{
                      padding: '2px 7px',
                      borderRadius: 'var(--radius-sm)',
                      border: `1px solid color-mix(in srgb, ${cat.color} 20%, transparent)`,
                      background: `color-mix(in srgb, ${cat.color} 7%, transparent)`,
                      color: cat.color,
                      cursor: disabled ? 'default' : 'pointer',
                      fontSize: 'var(--text-caption2)',
                      fontWeight: 'var(--weight-medium)',
                      opacity: disabled ? 0.5 : 1,
                      transition: 'all 100ms ease',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {ev.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

/* ── Safe text rendering ───────────────────────────────────── */

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
    const boldMatch = remaining.match(/^(.*?)\*\*(.+?)\*\*/)
    if (boldMatch) {
      if (boldMatch[1]) parts.push(<span key={key++}>{boldMatch[1]}</span>)
      parts.push(<strong key={key++}>{boldMatch[2]}</strong>)
      remaining = remaining.slice(boldMatch[0].length)
      continue
    }

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
  const [showManual, setShowManual] = useState(true)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  usePythonMessages('chat_response', useCallback((msg: Record<string, unknown>) => {
    const response: ChatMessage = {
      id: nextId(),
      role: 'assistant',
      content: (msg.message as string) || 'No Response',
      timestamp: Date.now(),
      event_type: msg.event_type as string | undefined,
    }
    setMessages(prev => [...prev, response])
    setLoading(false)
  }, []))

  const fireEvent = async (text: string) => {
    if (loading) return
    setLoading(true)

    const userMsg: ChatMessage = {
      id: nextId(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }
    setMessages(prev => [...prev, userMsg])

    try {
      await sendChatMessage(text)
    } catch (e) {
      setMessages(prev => [...prev, {
        id: nextId(),
        role: 'system',
        content: `Error: ${e instanceof Error ? e.message : String(e)}`,
        timestamp: Date.now(),
      }])
      setLoading(false)
    }
  }

  const handleSend = async () => {
    const text = input.trim()
    if (!text || loading) return
    setInput('')
    fireEvent(text)
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
        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowManual(prev => !prev)}
            style={{
              padding: '3px 10px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--separator)',
              background: showManual ? 'var(--accent-fill)' : 'transparent',
              color: showManual ? 'var(--accent)' : 'var(--text-tertiary)',
              cursor: 'pointer',
              fontSize: 'var(--text-caption1)',
              fontWeight: 'var(--weight-medium)',
              transition: 'all 150ms ease',
            }}
          >
            Manual
          </button>
          <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>
            Text Input {'\u2192'} Intent Orchestrator
          </span>
        </div>
      </div>

      {/* Main area: Manual + Chat side by side */}
      <div className="flex flex-1" style={{ overflow: 'hidden', gap: 0, minHeight: 0 }}>
        {/* Event Manual sidebar */}
        {showManual && (
          <div style={{
            borderRadius: 'var(--radius-md) 0 0 var(--radius-md)',
            background: 'var(--material-regular)',
            backdropFilter: 'blur(20px)',
            overflow: 'hidden',
          }}>
            <EventManual onFire={fireEvent} disabled={loading} />
          </div>
        )}

        {/* Messages */}
        <div
          className="flex-1 overflow-y-auto"
          style={{
            borderRadius: showManual ? '0 var(--radius-md) var(--radius-md) 0' : 'var(--radius-md)',
            background: 'var(--material-regular)',
            backdropFilter: 'blur(20px)',
            padding: 'var(--space-3)',
            minHeight: 200,
          }}
        >
          {messages.length === 0 ? (
            <div className="flex flex-col items-center justify-center" style={{ height: '100%', minHeight: 200, color: 'var(--text-tertiary)', gap: 'var(--space-2)' }}>
              <span style={{ fontSize: 32, opacity: 0.5 }}>{'\uD83D\uDCAC'}</span>
              <span style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-medium)' }}>
                Text-Based Control
              </span>
              <span style={{ fontSize: 'var(--text-caption1)', textAlign: 'center', maxWidth: 300, lineHeight: 'var(--leading-relaxed)' }}>
                Use the Manual panel to fire events, or type naturally.
              </span>
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
                  <div style={{
                    maxWidth: '85%',
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

              {loading && (
                <div style={{ display: 'flex', alignItems: 'flex-start' }}>
                  <div style={{
                    padding: 'var(--space-2) var(--space-3)',
                    borderRadius: 'var(--radius-md) var(--radius-md) var(--radius-md) var(--radius-sm)',
                    background: 'var(--bg-tertiary)',
                    color: 'var(--text-tertiary)',
                    fontSize: 'var(--text-footnote)',
                  }}>
                    Processing...
                  </div>
                </div>
              )}

              <div ref={messagesEndRef} />
            </div>
          )}
        </div>
      </div>

      {/* Input Bar */}
      <div
        className="flex items-center flex-shrink-0 gap-2"
        style={{
          padding: 'var(--space-2) var(--space-3)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--material-regular)',
          border: '1px solid var(--separator)',
          marginTop: 'var(--space-3)',
        }}
      >
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message..."
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
          {'\u2191'}
        </button>
      </div>
    </div>
  )
}
