import { useState } from 'react'
import type { PluginInfo } from '../types'
import { usePlugins, acceptPlugin, rejectPlugin, togglePlugin } from '../hooks/useIPC'

/* ── Helpers ───────────────────────────────────────────────── */

const CATEGORY_META: Record<string, { icon: string; color: string }> = {
  core: { icon: '\u{2B50}', color: '#ffcc00' },
  development: { icon: '\u{1F4BB}', color: '#44ff88' },
  automation: { icon: '\u{26A1}', color: '#ff8844' },
  knowledge: { icon: '\u{1F4DA}', color: '#22ccaa' },
  research: { icon: '\u{1F50D}', color: '#ff6633' },
  collaboration: { icon: '\u{1F91D}', color: '#ff66aa' },
  productivity: { icon: '\u{23F0}', color: '#8866ff' },
  cognitive: { icon: '\u{1F9E0}', color: '#66aaff' },
  general: { icon: '\u{1F9E9}', color: 'var(--text-secondary)' },
}

type FilterKey = 'all' | 'enabled' | 'new' | 'community'

const PILLS: { key: FilterKey; label: string }[] = [
  { key: 'all', label: 'All' },
  { key: 'enabled', label: 'Enabled' },
  { key: 'new', label: 'New' },
  { key: 'community', label: 'Community' },
]

/* ── Component ─────────────────────────────────────────────── */

export function PluginBrowser() {
  const { data, loading, error, refresh } = usePlugins()
  const [filter, setFilter] = useState<FilterKey>('all')
  const [expanded, setExpanded] = useState<string | null>(null)
  const [acting, setActing] = useState<string | null>(null)

  const plugins: PluginInfo[] = data?.plugins ?? []

  const filtered = plugins.filter(p => {
    if (filter === 'enabled') return p.enabled
    if (filter === 'new') return p.is_new || p.is_updated
    if (filter === 'community') return !p.builtin
    return true
  })

  const newCount = plugins.filter(p => p.is_new || p.is_updated).length

  async function handleAccept(id: string) {
    setActing(id)
    try {
      await acceptPlugin(id)
      refresh()
    } finally {
      setActing(null)
    }
  }

  async function handleReject(id: string) {
    setActing(id)
    try {
      await rejectPlugin(id)
      refresh()
    } finally {
      setActing(null)
    }
  }

  async function handleToggle(id: string, enabled: boolean) {
    setActing(id)
    try {
      await togglePlugin(id, enabled)
      refresh()
    } finally {
      setActing(null)
    }
  }

  // Loading skeleton
  if (loading && plugins.length === 0) {
    return (
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 'var(--space-3)' }}>
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} style={{ height: 120, borderRadius: 'var(--radius-md)', background: 'var(--material-regular)' }} />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ height: 300, color: 'var(--text-secondary)', gap: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-title3)' }}>&#x26A0;&#xFE0F;</span>
        <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>Error Loading Plugins</span>
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
          Plugins
        </h2>
        <div className="flex items-center gap-3">
          <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)' }}>
            {data?.total_enabled ?? 0} / {data?.total_available ?? 0} active
          </span>
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
      </div>

      {/* Filter Pills */}
      <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-4)' }}>
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
                position: 'relative',
              }}
            >
              {pill.label}
              {pill.key === 'new' && newCount > 0 && (
                <span style={{
                  position: 'absolute',
                  top: -4,
                  right: -4,
                  width: 16,
                  height: 16,
                  borderRadius: '50%',
                  background: 'var(--system-red)',
                  color: '#fff',
                  fontSize: 10,
                  fontWeight: 'var(--weight-bold)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                }}>
                  {newCount}
                </span>
              )}
            </button>
          )
        })}
        <span style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-tertiary)', marginLeft: 'auto' }}>
          {filtered.length} plugins
        </span>
      </div>

      {/* Plugin Grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: 'repeat(3, 1fr)',
        gap: 'var(--space-3)',
      }}>
        {filtered.map(plugin => {
          const cat = CATEGORY_META[plugin.category] ?? CATEGORY_META.general
          const isExpanded = expanded === plugin.id
          const isActing = acting === plugin.id

          return (
            <div
              key={plugin.id}
              onClick={() => setExpanded(isExpanded ? null : plugin.id)}
              className="cursor-pointer hover-bg"
              style={{
                padding: 'var(--space-3)',
                borderRadius: 'var(--radius-md)',
                background: 'var(--material-regular)',
                backdropFilter: 'blur(20px)',
                transition: 'all 150ms var(--ease-smooth)',
                border: isExpanded ? `1px solid ${cat.color}` : '1px solid transparent',
                opacity: isActing ? 0.6 : 1,
              }}
            >
              {/* Top row: icon + name + badge */}
              <div className="flex items-center gap-2" style={{ marginBottom: 'var(--space-2)' }}>
                <span style={{ fontSize: 18 }}>{cat.icon}</span>
                <span style={{
                  fontSize: 'var(--text-footnote)',
                  fontWeight: 'var(--weight-semibold)',
                  color: 'var(--text-primary)',
                  flex: 1,
                  minWidth: 0,
                }} className="truncate">
                  {plugin.name}
                </span>
                {/* Badges */}
                {plugin.builtin && (
                  <span style={{
                    fontSize: 'var(--text-caption2)',
                    color: 'var(--text-tertiary)',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--fill-tertiary)',
                  }}>
                    &#x1F512;
                  </span>
                )}
                {plugin.is_new && (
                  <span style={{
                    fontSize: 'var(--text-caption2)',
                    color: '#fff',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--system-blue)',
                    fontWeight: 'var(--weight-semibold)',
                  }}>
                    NEW
                  </span>
                )}
                {plugin.is_updated && (
                  <span style={{
                    fontSize: 'var(--text-caption2)',
                    color: '#fff',
                    padding: '1px 6px',
                    borderRadius: 'var(--radius-sm)',
                    background: 'var(--system-orange)',
                    fontWeight: 'var(--weight-semibold)',
                  }}>
                    UPDATE
                  </span>
                )}
                {/* Status dot */}
                <span className="rounded-full" style={{
                  width: 8,
                  height: 8,
                  background: plugin.enabled ? 'var(--system-green)' : 'var(--text-tertiary)',
                  flexShrink: 0,
                }} />
              </div>

              {/* Description */}
              <div style={{
                fontSize: 'var(--text-caption1)',
                color: 'var(--text-tertiary)',
                lineHeight: 1.4,
                display: '-webkit-box',
                WebkitLineClamp: 2,
                WebkitBoxOrient: 'vertical',
                overflow: 'hidden',
              }}>
                {plugin.description}
              </div>

              {/* Meta row */}
              <div className="flex items-center gap-2" style={{ marginTop: 'var(--space-2)' }}>
                <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-quaternary)' }}>
                  v{plugin.version}
                </span>
                <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-quaternary)' }}>
                  {plugin.event_count} events
                </span>
                <span style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-quaternary)', marginLeft: 'auto' }}>
                  {plugin.author}
                </span>
              </div>

              {/* Expanded section */}
              {isExpanded && (
                <div
                  className="animate-slide-down"
                  style={{ marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--separator)' }}
                  onClick={e => e.stopPropagation()}
                >
                  {/* Changelog */}
                  {plugin.changelog && (
                    <div style={{ marginBottom: 'var(--space-3)' }}>
                      <div style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', marginBottom: 2, fontWeight: 'var(--weight-medium)' }}>
                        Changelog
                      </div>
                      <div style={{ fontSize: 'var(--text-caption1)', color: 'var(--text-secondary)' }}>
                        {plugin.changelog}
                      </div>
                    </div>
                  )}

                  {/* Actions */}
                  {!plugin.builtin && (
                    <div className="flex gap-2">
                      {plugin.is_new ? (
                        <>
                          <button
                            onClick={() => handleAccept(plugin.id)}
                            disabled={isActing}
                            style={{
                              flex: 1,
                              padding: '6px 12px',
                              borderRadius: 'var(--radius-sm)',
                              border: 'none',
                              background: 'var(--system-green)',
                              color: '#fff',
                              cursor: isActing ? 'wait' : 'pointer',
                              fontSize: 'var(--text-footnote)',
                              fontWeight: 'var(--weight-semibold)',
                            }}
                          >
                            Aktivieren
                          </button>
                          <button
                            onClick={() => handleReject(plugin.id)}
                            disabled={isActing}
                            style={{
                              flex: 1,
                              padding: '6px 12px',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--separator)',
                              background: 'transparent',
                              color: 'var(--text-secondary)',
                              cursor: isActing ? 'wait' : 'pointer',
                              fontSize: 'var(--text-footnote)',
                            }}
                          >
                            Nicht jetzt
                          </button>
                        </>
                      ) : (
                        <button
                          onClick={() => handleToggle(plugin.id, !plugin.enabled)}
                          disabled={isActing}
                          style={{
                            flex: 1,
                            padding: '6px 12px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--separator)',
                            background: plugin.enabled ? 'var(--fill-secondary)' : 'var(--system-green)',
                            color: plugin.enabled ? 'var(--text-primary)' : '#fff',
                            cursor: isActing ? 'wait' : 'pointer',
                            fontSize: 'var(--text-footnote)',
                            fontWeight: 'var(--weight-medium)',
                          }}
                        >
                          {plugin.enabled ? 'Deaktivieren' : 'Aktivieren'}
                        </button>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {/* Empty state */}
      {filtered.length === 0 && (
        <div className="flex flex-col items-center justify-center" style={{ height: 200, color: 'var(--text-tertiary)' }}>
          <span style={{ fontSize: 32, marginBottom: 'var(--space-2)' }}>{'\u{1F9E9}'}</span>
          <span style={{ fontSize: 'var(--text-footnote)' }}>
            {filter === 'new' ? 'Keine neuen Plugins' : 'Keine Plugins gefunden'}
          </span>
        </div>
      )}
    </div>
  )
}
