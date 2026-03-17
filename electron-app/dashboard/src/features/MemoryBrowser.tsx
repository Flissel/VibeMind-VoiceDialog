import { useState, useCallback } from 'react'
import type { MemorySearchResult } from '../types'
import { useMemoryOverview, useIPCQuery } from '../hooks/useIPC'

/* ── Helpers ───────────────────────────────────────────────── */

function formatTs(ts: string | undefined): string {
  if (!ts) return '--'
  const d = new Date(ts)
  return d.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const CATEGORY_COLORS: Record<string, { bg: string; color: string; label: string }> = {
  tasks: { bg: 'rgba(0,122,255,0.1)', color: 'var(--system-blue)', label: 'Tasks' },
  conversations: { bg: 'rgba(175,82,222,0.1)', color: 'var(--system-purple)', label: 'Conversations' },
}

/* ── Component ─────────────────────────────────────────────── */

export function MemoryBrowser() {
  const { data: overview, loading: overviewLoading, error: overviewError, refresh: refreshOverview } = useMemoryOverview()
  const [searchQuery, setSearchQuery] = useState('')
  const [searchCategory, setSearchCategory] = useState<'tasks' | 'conversations'>('tasks')
  const [activeSearch, setActiveSearch] = useState(false)
  const [searchResults, setSearchResults] = useState<MemorySearchResult[]>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [expanded, setExpanded] = useState<string | null>(null)

  const api = typeof window !== 'undefined' ? (window as any).vibemindDashboard : null

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim() || !api) return
    setSearchLoading(true)
    setActiveSearch(true)
    try {
      const result = await api.searchMemory(searchQuery.trim(), searchCategory, 20)
      setSearchResults(result?.results ?? [])
    } catch (e) {
      console.error('Search failed:', e)
      setSearchResults([])
    } finally {
      setSearchLoading(false)
    }
  }, [searchQuery, searchCategory, api])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      handleSearch()
    }
  }

  const memoryData = overview?.data

  // Check availability
  const anyAvailable = memoryData && (
    memoryData.task_memory?.available ||
    memoryData.conversation_memory?.available ||
    memoryData.user_profiles?.available
  )

  // Loading
  if (overviewLoading) {
    return (
      <div>
        <div style={{ height: 32, width: 200, borderRadius: 'var(--radius-sm)', background: 'var(--fill-tertiary)', marginBottom: 'var(--space-4)' }} />
        <div className="flex gap-3" style={{ marginBottom: 'var(--space-4)' }}>
          {[1, 2, 3].map(i => (
            <div key={i} style={{ flex: 1, height: 80, borderRadius: 'var(--radius-md)', background: 'var(--material-regular)' }} />
          ))}
        </div>
      </div>
    )
  }

  if (overviewError) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ height: 300, color: 'var(--text-secondary)', gap: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-title3)' }}>&#x26A0;&#xFE0F;</span>
        <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>Error Loading</span>
        <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)' }}>{overviewError}</span>
        <button onClick={refreshOverview} style={{ marginTop: 'var(--space-2)', padding: '6px 16px', borderRadius: 'var(--radius-sm)', border: '1px solid var(--separator)', background: 'var(--fill-secondary)', color: 'var(--text-primary)', cursor: 'pointer', fontSize: 'var(--text-footnote)' }}>
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
          Memory Browser
        </h2>
        <button
          onClick={refreshOverview}
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

      {/* Service Status Cards */}
      <div className="flex gap-3" style={{ marginBottom: 'var(--space-4)' }}>
        {[
          { key: 'task_memory', label: 'Task Memory', desc: 'Intent Execution & Results', icon: '\u{1F4CB}' },
          { key: 'conversation_memory', label: 'Conversation Memory', desc: 'Cross-Session Context', icon: '\u{1F4AC}' },
          { key: 'user_profiles', label: 'User Profiles', desc: 'Preferences & Habits', icon: '\u{1F464}' },
        ].map(svc => {
          const available = memoryData?.[svc.key as keyof typeof memoryData] as { available: boolean } | undefined
          const isUp = available?.available ?? false
          return (
            <div key={svc.key} style={{
              flex: 1,
              padding: 'var(--space-3) var(--space-4)',
              borderRadius: 'var(--radius-md)',
              background: 'var(--material-regular)',
              backdropFilter: 'blur(20px)',
              border: isUp ? '1px solid rgba(48,209,88,0.2)' : '1px solid var(--separator)',
            }}>
              <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-2)' }}>
                <span style={{ fontSize: 18 }}>{svc.icon}</span>
                <span style={{ fontSize: 'var(--text-footnote)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)' }}>
                  {svc.label}
                </span>
                <span className="rounded-full" style={{
                  width: 8, height: 8,
                  background: isUp ? 'var(--system-green)' : 'var(--text-tertiary)',
                  marginLeft: 'auto',
                }} />
              </div>
              <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>
                {isUp ? svc.desc : 'Not Configured'}
              </div>
            </div>
          )
        })}
      </div>

      {/* Not configured hint */}
      {!anyAvailable && (
        <div className="flex flex-col items-center justify-center" style={{
          padding: 'var(--space-6)',
          borderRadius: 'var(--radius-md)',
          background: 'var(--material-regular)',
          color: 'var(--text-secondary)',
          gap: 'var(--space-3)',
          marginBottom: 'var(--space-4)',
        }}>
          <span style={{ fontSize: 32, opacity: 0.5 }}>&#x1F9E0;</span>
          <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>
            Memory Services Not Configured
          </span>
          <span style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-tertiary)', textAlign: 'center', maxWidth: 400, lineHeight: 'var(--leading-relaxed)' }}>
            Enable Memory Services in .env:
          </span>
          <div style={{
            padding: 'var(--space-3)',
            borderRadius: 'var(--radius-sm)',
            background: 'var(--code-bg)',
            border: '1px solid var(--code-border)',
            fontFamily: '"SF Mono", Monaco, Menlo, monospace',
            fontSize: 'var(--text-caption1)',
            color: 'var(--code-text)',
            lineHeight: 'var(--leading-relaxed)',
          }}>
            USE_TASK_MEMORY=true{'\n'}
            USE_CONVERSATION_MEMORY=true{'\n'}
            USE_USER_PROFILES=true{'\n'}
            SUPERMEMORY_API_KEY=xxx
          </div>
        </div>
      )}

      {/* Top Intents */}
      {memoryData?.user_profiles?.top_intents && memoryData.user_profiles.top_intents.length > 0 && (
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <h3 style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', marginBottom: 'var(--space-3)' }}>
            Top Intents
          </h3>
          <div className="flex flex-wrap gap-2">
            {memoryData.user_profiles.top_intents.map((item: { intent: string; count: number }) => (
              <span key={item.intent} className="font-mono" style={{
                padding: '4px 10px',
                borderRadius: 'var(--radius-sm)',
                background: 'var(--fill-tertiary)',
                fontSize: 'var(--text-caption1)',
                color: 'var(--text-secondary)',
              }}>
                {item.intent} <span style={{ color: 'var(--accent)', fontWeight: 'var(--weight-semibold)' }}>({item.count})</span>
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Search Section */}
      {anyAvailable && (
        <div style={{ marginBottom: 'var(--space-4)' }}>
          <h3 style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-semibold)', color: 'var(--text-primary)', marginBottom: 'var(--space-3)' }}>
            Search
       </h3>

          {/* Category toggle + search */}
          <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-3)' }}>
            {(['tasks', 'conversations'] as const).map(cat => {
              const isActive = searchCategory === cat
              const badge = CATEGORY_COLORS[cat]
              return (
                <button
                  key={cat}
                  onClick={() => setSearchCategory(cat)}
                  className="focus-ring"
                  style={{
                    borderRadius: 20,
                    padding: '6px 14px',
                    fontSize: 'var(--text-footnote)',
                    fontWeight: 'var(--weight-medium)',
                    border: 'none',
                    cursor: 'pointer',
                    transition: 'all 200ms var(--ease-smooth)',
                    background: isActive ? badge.bg : 'var(--fill-secondary)',
                    color: isActive ? badge.color : 'var(--text-primary)',
                  }}
                >
                  {badge.label}
                </button>
              )
            })}

            <div className="flex items-center flex-1 gap-2" style={{ marginLeft: 'auto', maxWidth: 350 }}>
              <input
                type="text"
                placeholder="Semantic Search..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onKeyDown={handleKeyDown}
                className="focus-ring"
                style={{
                  flex: 1,
                  padding: '6px 12px',
                  fontSize: 'var(--text-footnote)',
                  borderRadius: 'var(--radius-sm)',
                  border: '1px solid var(--separator)',
                  background: 'var(--fill-secondary)',
                  color: 'var(--text-primary)',
                  outline: 'none',
                }}
              />
              <button
                onClick={handleSearch}
                disabled={!searchQuery.trim() || searchLoading}
                style={{
                  padding: '6px 14px',
                  borderRadius: 'var(--radius-sm)',
                  border: 'none',
                  background: searchQuery.trim() ? 'var(--accent)' : 'var(--fill-tertiary)',
                  color: searchQuery.trim() ? 'var(--accent-contrast)' : 'var(--text-tertiary)',
                  cursor: searchQuery.trim() ? 'pointer' : 'default',
                  fontSize: 'var(--text-footnote)',
                  fontWeight: 'var(--weight-medium)',
                }}
              >
                Search
              </button>
            </div>
          </div>

          {/* Search Results */}
          {searchLoading && (
            <div className="flex items-center justify-center" style={{ height: 100, color: 'var(--text-tertiary)' }}>
              Searching...
            </div>
          )}

          {activeSearch && !searchLoading && searchResults.length === 0 && (
            <div className="flex flex-col items-center justify-center" style={{ height: 100, color: 'var(--text-tertiary)', gap: 'var(--space-1)' }}>
              <span style={{ fontSize: 'var(--text-footnote)' }}>No Results</span>
              <span style={{ fontSize: 'var(--text-caption1)' }}>Try a different search query</span>
            </div>
          )}

          {searchResults.length > 0 && (
            <div style={{ borderRadius: 'var(--radius-md)', overflow: 'hidden', background: 'var(--material-regular)', backdropFilter: 'blur(20px)' }}>
              {searchResults.map((result, idx) => {
                const isExpanded = expanded === result.id
                return (
                  <div key={result.id}>
                    {idx > 0 && <div style={{ height: 1, background: 'var(--separator)', marginLeft: 'var(--space-4)', marginRight: 'var(--space-4)' }} />}

                    <div
                      onClick={() => setExpanded(isExpanded ? null : result.id)}
                      className="cursor-pointer hover-bg flex items-center"
                      style={{ minHeight: 44, padding: '0 var(--space-4)', gap: 'var(--space-3)' }}
                    >
                      {/* Score indicator */}
                      {result.score != null && (
                        <span className="flex-shrink-0" style={{
                          width: 32,
                          fontSize: 'var(--text-caption2)',
                          fontWeight: 'var(--weight-semibold)',
                          color: result.score > 0.7 ? 'var(--system-green)' : result.score > 0.4 ? 'var(--system-orange)' : 'var(--text-tertiary)',
                          textAlign: 'center',
                        }}>
                          {(result.score * 100).toFixed(0)}%
                        </span>
                      )}

                      {/* Content preview */}
                      <span className="truncate flex-1" style={{ fontSize: 'var(--text-footnote)', color: 'var(--text-primary)' }}>
                        {result.content.length > 150 ? result.content.slice(0, 147) + '...' : result.content}
                      </span>

                      {/* Timestamp */}
                      <span className="flex-shrink-0" style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
                        {formatTs(result.timestamp)}
                      </span>

                      {/* Chevron */}
                      <span style={{
                        fontSize: 'var(--text-footnote)',
                        color: 'var(--text-tertiary)',
                        transition: 'transform 200ms var(--ease-smooth)',
                        transform: isExpanded ? 'rotate(90deg)' : 'rotate(0deg)',
                        display: 'inline-block',
                      }}>
                        &#8250;
                      </span>
                    </div>

                    {/* Expanded detail */}
                    {isExpanded && (
                      <div className="animate-slide-down" style={{ padding: '0 var(--space-4) var(--space-4) var(--space-4)' }}>
                        <div style={{
                          fontSize: 'var(--text-caption1)',
                          color: 'var(--text-secondary)',
                          lineHeight: 'var(--leading-relaxed)',
                          whiteSpace: 'pre-wrap',
                          wordBreak: 'break-word',
                          marginBottom: 'var(--space-3)',
                        }}>
                          {result.content}
                        </div>

                        {Object.keys(result.metadata).length > 0 && (
                          <div style={{
                            borderRadius: 'var(--radius-sm)',
                            background: 'var(--code-bg)',
                            border: '1px solid var(--code-border)',
                            padding: 'var(--space-3)',
                          }}>
                            <pre className="font-mono" style={{
                              fontSize: 'var(--text-caption2)',
                              color: 'var(--text-secondary)',
                              whiteSpace: 'pre-wrap',
                              wordBreak: 'break-word',
                              margin: 0,
                              maxHeight: 200,
                              overflow: 'auto',
                            }}>
                              {JSON.stringify(result.metadata, null, 2)}
                            </pre>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
