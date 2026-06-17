import { useState } from 'react'

/**
 * Rowboat Workflow/Agent Builder — embedded as a 4th AgentFarm sub-tab.
 *
 * Loads the apps/rowboat Next.js workflow builder (Docker, :3100) for the
 * VibeMind project. URL is hardcoded like WorkflowBuilder's n8nBaseUrl
 * (the project id is stable; .env has no renderer-side interpolation).
 *
 * Replaces the earlier AGENTFARM_DEV_URL override which wrongly swapped the
 * whole AgentFarm app for this single page (losing Pipeline/Teams/n8n).
 */
const ROWBOAT_PROJECT_ID = 'c157ade4-ebce-4d1b-a7a5-5fd70d238f8d'
const ROWBOAT_URL = `http://localhost:3100/projects/${ROWBOAT_PROJECT_ID}`

export function RowboatWorkflow() {
  const [loading, setLoading] = useState(true)
  const [failed, setFailed] = useState(false)

  return (
    <div
      style={{
        position: 'absolute',
        inset: 0,
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg)',
      }}
    >
      {loading && !failed && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: 'var(--text-tertiary)',
            fontSize: 'var(--text-caption1)',
            zIndex: 1,
          }}
        >
          Lade Rowboat Workflow Builder…
        </div>
      )}

      {failed && (
        <div
          style={{
            position: 'absolute',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 'var(--space-2)',
            color: 'var(--text-tertiary)',
            fontSize: 'var(--text-caption1)',
            textAlign: 'center',
            padding: 'var(--space-4)',
          }}
        >
          <div>Rowboat ist nicht erreichbar ({ROWBOAT_URL}).</div>
          <div>Läuft der Docker-Stack (vibemind-rowboat)?</div>
          <button
            onClick={() => { setFailed(false); setLoading(true) }}
            style={{
              marginTop: 'var(--space-2)',
              padding: '5px 18px',
              borderRadius: 'var(--radius-sm)',
              border: '1px solid var(--separator)',
              background: 'var(--bg-secondary)',
              color: 'var(--text-primary)',
              cursor: 'pointer',
              fontSize: 'var(--text-caption1)',
            }}
          >
            Erneut versuchen
          </button>
        </div>
      )}

      {!failed && (
        <iframe
          src={ROWBOAT_URL}
          title="Rowboat Workflow Builder"
          onLoad={() => setLoading(false)}
          onError={() => { setLoading(false); setFailed(true) }}
          style={{
            flex: 1,
            width: '100%',
            height: '100%',
            border: 'none',
            background: 'var(--bg)',
          }}
        />
      )}
    </div>
  )
}
