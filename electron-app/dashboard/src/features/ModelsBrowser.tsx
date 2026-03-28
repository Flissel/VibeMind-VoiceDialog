import { useState } from 'react'
import type { ModelRoleConfig, ProviderInfo, ModelTestResponse } from '../types'
import { useModelsConfig, updateModelRole, testModelConnection } from '../hooks/useIPC'

/* ── Constants ────────────────────────────────────────────── */

const PROVIDER_COLORS: Record<string, string> = {
  openai: '#10a37f',
  openrouter: '#ff8844',
  ollama: '#22ccaa',
  anthropic: '#d4a574',
}

const GROUP_ORDER = ['Core', 'Agents & Routing', 'Content', 'Personality & Context', 'Workers', 'Special', 'Other']

/* ── Component ────────────────────────────────────────────── */

export function ModelsBrowser() {
  const { data, loading, error, refresh } = useModelsConfig()
  const [editingRole, setEditingRole] = useState<string | null>(null)
  const [editForm, setEditForm] = useState({ provider: '', model: '', maxTokens: '' })
  const [saving, setSaving] = useState<string | null>(null)
  const [testing, setTesting] = useState<string | null>(null)
  const [testResult, setTestResult] = useState<ModelTestResponse | null>(null)

  const models: ModelRoleConfig[] = data?.models ?? []
  const providers: ProviderInfo[] = data?.providers ?? []

  // Group models
  const grouped = new Map<string, ModelRoleConfig[]>()
  for (const m of models) {
    const group = m.group || 'Other'
    if (!grouped.has(group)) grouped.set(group, [])
    grouped.get(group)!.push(m)
  }

  function startEdit(m: ModelRoleConfig) {
    if (m.locked) return
    setEditingRole(m.role)
    setEditForm({
      provider: m.provider,
      model: m.model,
      maxTokens: m.max_tokens != null ? String(m.max_tokens) : '',
    })
    setTestResult(null)
  }

  function cancelEdit() {
    setEditingRole(null)
    setTestResult(null)
  }

  async function handleSave(role: string) {
    setSaving(role)
    try {
      const maxTokens = editForm.maxTokens ? parseInt(editForm.maxTokens, 10) : null
      await updateModelRole(role, editForm.provider, editForm.model, maxTokens)
      setEditingRole(null)
      refresh()
    } finally {
      setSaving(null)
    }
  }

  async function handleTest(role: string) {
    setTesting(role)
    setTestResult(null)
    try {
      const result = await testModelConnection(role) as ModelTestResponse
      setTestResult(result)
    } catch (e) {
      setTestResult({ type: 'model_test_result', success: false, role, error: String(e) })
    } finally {
      setTesting(null)
    }
  }

  // Loading skeleton
  if (loading && models.length === 0) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-3)' }}>
        {[1, 2, 3, 4, 5, 6].map(i => (
          <div key={i} style={{ height: 56, borderRadius: 'var(--radius-md)', background: 'var(--material-regular)' }} />
        ))}
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center" style={{ height: 300, color: 'var(--text-secondary)', gap: 'var(--space-3)' }}>
        <span style={{ fontSize: 'var(--text-title3)' }}>&#x26A0;&#xFE0F;</span>
        <span style={{ fontSize: 'var(--text-subheadline)', fontWeight: 'var(--weight-medium)' }}>Error Loading Models</span>
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
          Models
        </h2>
        <div className="flex items-center gap-3">
          {/* Provider status indicators */}
          {providers.map(p => (
            <div key={p.name} className="flex items-center gap-1" style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)' }}>
              <span className="rounded-full" style={{
                width: 6,
                height: 6,
                background: p.has_key ? 'var(--system-green)' : 'var(--system-red)',
                flexShrink: 0,
              }} />
              {p.name}
            </div>
          ))}
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

      {/* Grouped model list */}
      {GROUP_ORDER.filter(g => grouped.has(g)).map(groupName => (
        <div key={groupName} style={{ marginBottom: 'var(--space-4)' }}>
          <h3 style={{
            fontSize: 'var(--text-footnote)',
            fontWeight: 'var(--weight-semibold)',
            color: 'var(--text-tertiary)',
            textTransform: 'uppercase',
            letterSpacing: '0.05em',
            marginBottom: 'var(--space-2)',
          }}>
            {groupName}
          </h3>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            {grouped.get(groupName)!.map(m => {
              const isEditing = editingRole === m.role
              const isSaving = saving === m.role
              const provColor = PROVIDER_COLORS[m.provider] || 'var(--text-tertiary)'

              return (
                <div
                  key={m.role}
                  onClick={() => !isEditing && startEdit(m)}
                  style={{
                    padding: 'var(--space-3)',
                    borderRadius: 'var(--radius-md)',
                    background: 'var(--material-regular)',
                    backdropFilter: 'blur(20px)',
                    transition: 'all 150ms var(--ease-smooth)',
                    border: isEditing ? '1px solid var(--accent)' : '1px solid transparent',
                    cursor: m.locked ? 'default' : 'pointer',
                    opacity: isSaving ? 0.6 : 1,
                  }}
                >
                  {/* Role row */}
                  <div className="flex items-center gap-2">
                    <span style={{
                      fontSize: 'var(--text-footnote)',
                      fontWeight: 'var(--weight-semibold)',
                      color: 'var(--text-primary)',
                      minWidth: 140,
                    }}>
                      {m.role}
                    </span>

                    {/* Provider badge */}
                    <span style={{
                      fontSize: 'var(--text-caption2)',
                      color: provColor,
                      padding: '1px 8px',
                      borderRadius: 'var(--radius-sm)',
                      background: `${provColor}18`,
                      fontWeight: 'var(--weight-medium)',
                    }}>
                      {m.provider}
                    </span>

                    {/* Model name */}
                    <span className="font-mono" style={{
                      fontSize: 'var(--text-caption1)',
                      color: 'var(--text-secondary)',
                      flex: 1,
                    }}>
                      {m.model}
                    </span>

                    {/* Max tokens */}
                    {m.max_tokens != null && (
                      <span style={{
                        fontSize: 'var(--text-caption2)',
                        color: 'var(--text-quaternary)',
                      }}>
                        {m.max_tokens} tok
                      </span>
                    )}

                    {/* Locked badge */}
                    {m.locked && (
                      <span style={{
                        fontSize: 'var(--text-caption2)',
                        color: 'var(--text-tertiary)',
                        padding: '1px 6px',
                        borderRadius: 'var(--radius-sm)',
                        background: 'var(--fill-tertiary)',
                      }}>
                        &#x1F512; LOCKED
                      </span>
                    )}
                  </div>

                  {/* Description */}
                  <div style={{
                    fontSize: 'var(--text-caption2)',
                    color: 'var(--text-quaternary)',
                    marginTop: 2,
                  }}>
                    {m.description}
                  </div>

                  {/* Edit form */}
                  {isEditing && (
                    <div
                      className="animate-slide-down"
                      style={{ marginTop: 'var(--space-3)', paddingTop: 'var(--space-3)', borderTop: '1px solid var(--separator)' }}
                      onClick={e => e.stopPropagation()}
                    >
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr 1fr', gap: 'var(--space-2)', marginBottom: 'var(--space-3)' }}>
                        {/* Provider */}
                        <div>
                          <label style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', display: 'block', marginBottom: 2 }}>
                            Provider
                          </label>
                          <select
                            value={editForm.provider}
                            onChange={e => setEditForm(f => ({ ...f, provider: e.target.value }))}
                            style={{
                              width: '100%',
                              padding: '6px 8px',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--separator)',
                              background: 'var(--fill-secondary)',
                              color: 'var(--text-primary)',
                              fontSize: 'var(--text-caption1)',
                              outline: 'none',
                            }}
                          >
                            {providers.map(p => (
                              <option key={p.name} value={p.name}>{p.name}</option>
                            ))}
                          </select>
                        </div>

                        {/* Model */}
                        <div>
                          <label style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', display: 'block', marginBottom: 2 }}>
                            Model
                          </label>
                          <input
                            type="text"
                            value={editForm.model}
                            onChange={e => setEditForm(f => ({ ...f, model: e.target.value }))}
                            style={{
                              width: '100%',
                              padding: '6px 8px',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--separator)',
                              background: 'var(--fill-secondary)',
                              color: 'var(--text-primary)',
                              fontSize: 'var(--text-caption1)',
                              fontFamily: 'var(--font-mono, monospace)',
                              outline: 'none',
                            }}
                            placeholder="e.g. gpt-4o, claude-sonnet-4-6"
                          />
                        </div>

                        {/* Max Tokens */}
                        <div>
                          <label style={{ fontSize: 'var(--text-caption2)', color: 'var(--text-tertiary)', display: 'block', marginBottom: 2 }}>
                            Max Tokens
                          </label>
                          <input
                            type="number"
                            value={editForm.maxTokens}
                            onChange={e => setEditForm(f => ({ ...f, maxTokens: e.target.value }))}
                            style={{
                              width: '100%',
                              padding: '6px 8px',
                              borderRadius: 'var(--radius-sm)',
                              border: '1px solid var(--separator)',
                              background: 'var(--fill-secondary)',
                              color: 'var(--text-primary)',
                              fontSize: 'var(--text-caption1)',
                              outline: 'none',
                            }}
                            placeholder="4096"
                          />
                        </div>
                      </div>

                      {/* Actions row */}
                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => handleSave(m.role)}
                          disabled={isSaving || !editForm.model.trim()}
                          style={{
                            padding: '6px 16px',
                            borderRadius: 'var(--radius-sm)',
                            border: 'none',
                            background: 'var(--accent)',
                            color: '#fff',
                            cursor: isSaving ? 'wait' : 'pointer',
                            fontSize: 'var(--text-footnote)',
                            fontWeight: 'var(--weight-semibold)',
                            opacity: !editForm.model.trim() ? 0.5 : 1,
                          }}
                        >
                          {isSaving ? 'Saving...' : 'Save'}
                        </button>

                        <button
                          onClick={() => handleTest(m.role)}
                          disabled={testing === m.role}
                          style={{
                            padding: '6px 16px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--separator)',
                            background: 'transparent',
                            color: 'var(--text-secondary)',
                            cursor: testing === m.role ? 'wait' : 'pointer',
                            fontSize: 'var(--text-footnote)',
                          }}
                        >
                          {testing === m.role ? 'Testing...' : 'Test'}
                        </button>

                        <button
                          onClick={cancelEdit}
                          style={{
                            padding: '6px 16px',
                            borderRadius: 'var(--radius-sm)',
                            border: '1px solid var(--separator)',
                            background: 'transparent',
                            color: 'var(--text-tertiary)',
                            cursor: 'pointer',
                            fontSize: 'var(--text-footnote)',
                          }}
                        >
                          Cancel
                        </button>

                        {/* Test result */}
                        {testResult && testResult.role === m.role && (
                          <span style={{
                            marginLeft: 'auto',
                            fontSize: 'var(--text-caption1)',
                            color: testResult.success ? 'var(--system-green)' : 'var(--system-red)',
                          }}>
                            {testResult.success
                              ? `\u2713 OK (${testResult.latency_ms}ms)`
                              : `\u2717 ${testResult.error}`
                            }
                          </span>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      ))}

      {/* Empty state */}
      {models.length === 0 && (
        <div className="flex flex-col items-center justify-center" style={{ height: 200, color: 'var(--text-tertiary)' }}>
          <span style={{ fontSize: 32, marginBottom: 'var(--space-2)' }}>{'\u2699'}</span>
          <span style={{ fontSize: 'var(--text-footnote)' }}>No model roles configured</span>
        </div>
      )}
    </div>
  )
}
