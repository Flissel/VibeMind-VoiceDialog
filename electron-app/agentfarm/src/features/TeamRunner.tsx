import { useState, useCallback, useEffect } from 'react'
import type { TeamInfo } from '../types'

const api = typeof window !== 'undefined' ? (window as any).vibemindAgentFarm : null
// Minibook Frontend shows pipeline posts, agent discussions, and user Q&A
const WEBCHAT_URL = 'http://localhost:3481/dashboard'

/* ── Hooks ────────────────────────────────────────────────── */

function useTeams() {
  const [teams, setTeams] = useState<TeamInfo[]>([])
  const [loading, setLoading] = useState(false)

  const refresh = useCallback(async () => {
    if (!api?.listTeams) return
    setLoading(true)
    try {
      const result = await api.listTeams()
      // Only show completed teams
      const completed = (result?.teams || []).filter(
        (t: TeamInfo) => t.status === 'completed'
      )
      setTeams(completed)
    } catch { /* ignore */ }
    finally { setLoading(false) }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  return { teams, loading, refresh }
}

/* ── Components ──────────────────────────────────────────── */

function TeamCard({ team }: { team: TeamInfo }) {
  return (
    <div style={{
      background: 'var(--bg-secondary)',
      border: '1px solid var(--separator)',
      borderRadius: 'var(--radius-lg)',
      padding: 'var(--space-3)',
      marginBottom: 'var(--space-2)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <span style={{
            fontSize: 'var(--text-body)',
            fontWeight: 600,
            color: 'var(--text-primary)',
          }}>
            {team.name}
          </span>
          <span style={{
            marginLeft: 'var(--space-2)',
            fontSize: 'var(--text-caption1)',
            color: 'var(--text-tertiary)',
          }}>
            {team.agent_count} Agents | {team.pattern}
          </span>
        </div>
        {team.eval_score != null && (
          <span style={{
            fontSize: 'var(--text-caption1)',
            fontWeight: 600,
            color: team.eval_score >= 7 ? 'var(--green)' : team.eval_score >= 5 ? 'var(--yellow)' : 'var(--red)',
            background: 'var(--fill-tertiary)',
            padding: '2px 8px',
            borderRadius: 'var(--radius-sm)',
          }}>
            Score: {team.eval_score}/10
          </span>
        )}
      </div>

      {/* Agent list */}
      <div style={{
        marginTop: 'var(--space-2)',
        display: 'flex',
        flexWrap: 'wrap',
        gap: 'var(--space-1)',
      }}>
        {team.agent_names.map(name => (
          <span key={name} style={{
            fontSize: 'var(--text-caption2)',
            color: 'var(--text-secondary)',
            background: 'var(--fill-quaternary)',
            padding: '2px 8px',
            borderRadius: 'var(--radius-sm)',
          }}>
            {name}
          </span>
        ))}
      </div>

      {/* Actions */}
      <div style={{ marginTop: 'var(--space-2)', display: 'flex', gap: 'var(--space-2)' }}>
        {team.github_url && (
          <a href={team.github_url} target="_blank" rel="noreferrer" style={{
            fontSize: 'var(--text-caption1)',
            color: 'var(--tint)',
            textDecoration: 'none',
          }}>
            GitHub
          </a>
        )}
        {team.output_path && (
          <span style={{
            fontSize: 'var(--text-caption2)',
            color: 'var(--text-tertiary)',
          }}>
            {team.output_path}
          </span>
        )}
      </div>
    </div>
  )
}

/* ── Main Component ──────────────────────────────────────── */

export function TeamRunner() {
  const { teams, loading, refresh } = useTeams()
  const [showChat, setShowChat] = useState(false)

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', gap: 'var(--space-3)' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h2 style={{
          margin: 0,
          fontSize: 'var(--text-title3)',
          fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-primary)',
        }}>
          Fertige Teams
        </h2>
        <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
          <button
            onClick={() => setShowChat(!showChat)}
            style={{
              border: '1px solid var(--separator)',
              background: showChat ? 'var(--tint)' : 'var(--fill-tertiary)',
              color: showChat ? '#fff' : 'var(--text-secondary)',
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              cursor: 'pointer',
              fontSize: 'var(--text-caption1)',
              fontWeight: 600,
            }}
          >
            {showChat ? 'Chat ausblenden' : 'Pipeline Chat'}
          </button>
          <button
            onClick={refresh}
            disabled={loading}
            style={{
              border: '1px solid var(--separator)',
              background: 'var(--fill-tertiary)',
              color: 'var(--text-secondary)',
              padding: '6px 14px',
              borderRadius: 'var(--radius-md)',
              cursor: loading ? 'wait' : 'pointer',
              fontSize: 'var(--text-caption1)',
            }}
          >
            {loading ? 'Lade...' : 'Aktualisieren'}
          </button>
        </div>
      </div>

      {/* Content: Teams + optional WebChat */}
      <div style={{ flex: 1, display: 'flex', gap: 'var(--space-3)', overflow: 'hidden' }}>
        {/* Teams list */}
        <div style={{
          flex: showChat ? '0 0 50%' : '1',
          overflowY: 'auto',
          transition: 'flex 200ms ease',
        }}>
          {teams.length === 0 && !loading && (
            <div style={{
              textAlign: 'center',
              padding: 'var(--space-6)',
              color: 'var(--text-tertiary)',
              fontSize: 'var(--text-callout)',
            }}>
              Keine fertigen Teams.
              <br />
              <span style={{ fontSize: 'var(--text-caption1)' }}>
                Sage "Baue ein Agent-Team fuer..." um eine Pipeline zu starten.
              </span>
            </div>
          )}
          {teams.map(team => (
            <TeamCard key={team.team_id} team={team} />
          ))}
        </div>

        {/* WebChat iframe (OpenClaw Canvas) */}
        {showChat && (
          <div style={{
            flex: '0 0 50%',
            borderLeft: '1px solid var(--separator)',
            borderRadius: 'var(--radius-lg)',
            overflow: 'hidden',
          }}>
            <iframe
              src={WEBCHAT_URL}
              title="Pipeline Chat"
              style={{
                width: '100%',
                height: '100%',
                border: 'none',
                borderRadius: 'var(--radius-lg)',
                background: '#000',
              }}
            />
          </div>
        )}
      </div>
    </div>
  )
}
