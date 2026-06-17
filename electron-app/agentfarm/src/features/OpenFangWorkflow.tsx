import { useState } from 'react'

/**
 * OpenFang Agents — embedded as a 5th AgentFarm sub-tab.
 *
 * Loads OpenFang's own Alpine.js dashboard (HTTP API, :4200) where agents
 * can be listed, created, edited and chatted with. URL is hardcoded like
 * RowboatWorkflow's :3100 and WorkflowBuilder's n8n :15678 (the port is
 * stable; .env has no renderer-side interpolation — master .env default is
 * OPENFANG_URL=http://localhost:4200).
 *
 * Caveat: the OpenFang daemon has no watchdog and can die. The
 * loading/error/retry pattern (from RowboatWorkflow) handles a dead :4200
 * gracefully — no white screen, clear message + retry instead.
 */
const OPENFANG_URL = 'http://localhost:4200'

export function OpenFangWorkflow() {
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
          Lade OpenFang Agents…
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
          <div>OpenFang ist nicht erreichbar ({OPENFANG_URL}).</div>
          <div>Läuft der OpenFang-Daemon (:4200)?</div>
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
          src={OPENFANG_URL}
          title="OpenFang Agents"
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
