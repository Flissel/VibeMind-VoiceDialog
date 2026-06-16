import { useState, useEffect } from 'react'
import type { AgentFarmTab } from './types'
import { ProjectProgress } from './features/ProjectProgress'
import { TeamRunner } from './features/TeamRunner'
import { WorkflowBuilder } from './features/WorkflowBuilder'
import { RowboatWorkflow } from './features/RowboatWorkflow'
import { OpenFangWorkflow } from './features/OpenFangWorkflow'

const SUB_TABS: { key: AgentFarmTab; label: string }[] = [
  { key: 'autogen', label: 'Pipeline' },
  { key: 'teams', label: 'Teams' },
  { key: 'n8n', label: 'n8n' },
  { key: 'rowboat', label: 'Rowboat' },
  { key: 'openfang', label: 'OpenFang' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<AgentFarmTab>('autogen')

  // Listen for tab switch commands from main process (e.g. Video space navigation)
  useEffect(() => {
    const af = (window as any).vibemindAgentFarm
    if (af?.onSwitchTab) {
      af.onSwitchTab((data: { tab: AgentFarmTab }) => {
        if (data?.tab && SUB_TABS.some(t => t.key === data.tab)) {
          setActiveTab(data.tab)
        }
      })
    }
  }, [])

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg)' }}>
      {/* Header bar */}
      <nav
        className="flex items-center flex-shrink-0"
        style={{
          height: 44,
          padding: '0 var(--space-4)',
          gap: 'var(--space-3)',
          borderBottom: '1px solid var(--separator)',
          background: 'var(--material-thick)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
        }}
      >
        {/* Title */}
        <span style={{
          fontSize: 'var(--text-footnote)',
          fontWeight: 'var(--weight-semibold)',
          color: 'var(--text-primary)',
          marginRight: 'var(--space-4)',
        }}>
          Agent Farm
        </span>

        {/* Sub-Tab Pills */}
        <div
          className="flex items-center"
          style={{
            gap: 'var(--space-1)',
            padding: '2px',
            background: 'var(--fill-tertiary)',
            borderRadius: 'var(--radius-md)',
          }}
        >
          {SUB_TABS.map(tab => {
            const isActive = activeTab === tab.key
            return (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                style={{
                  border: 'none',
                  cursor: 'pointer',
                  padding: '5px 18px',
                  borderRadius: 'var(--radius-sm)',
                  fontSize: 'var(--text-caption1)',
                  fontWeight: isActive ? 600 : 500,
                  transition: 'all 150ms var(--ease-smooth)',
                  background: isActive ? 'var(--bg-secondary)' : 'transparent',
                  color: isActive ? 'var(--text-primary)' : 'var(--text-tertiary)',
                  boxShadow: isActive
                    ? '0 1px 3px rgba(0,0,0,0.2), 0 0 0 0.5px rgba(255,255,255,0.05)'
                    : 'none',
                }}
              >
                {tab.label}
              </button>
            )
          })}
        </div>

        {/* Spacer + Close button */}
        <div style={{ flex: 1 }} />
        <button
          onClick={() => {
            const af = (window as any).vibemindAgentFarm
            if (af?.closeAgentFarm) af.closeAgentFarm()
          }}
          className="hover-bg"
          title="Schliessen"
          style={{
            width: 28, height: 28, borderRadius: 'var(--radius-sm)',
            border: 'none', background: 'transparent',
            color: 'var(--text-tertiary)', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14,
          }}
        >
          &#x2715;
        </button>
      </nav>

      {/* Content */}
      <div className="flex-1 overflow-hidden" style={{ position: 'relative' }}>
        {/* rowboat + openfang are full-bleed iframes (no padding/scroll wrapper) */}
        {activeTab === 'rowboat' && <RowboatWorkflow />}
        {activeTab === 'openfang' && <OpenFangWorkflow />}
        {activeTab !== 'rowboat' && activeTab !== 'openfang' && (
          <div
            className="h-full overflow-y-auto"
            style={{ padding: 'var(--space-4)' }}
          >
            {activeTab === 'autogen' && <ProjectProgress />}
            {activeTab === 'teams' && <TeamRunner />}
            {activeTab === 'n8n' && <WorkflowBuilder />}
          </div>
        )}
      </div>
    </div>
  )
}
