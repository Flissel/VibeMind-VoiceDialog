import { useState } from 'react'
import type { DashboardTab } from './types'
import { ScheduleMonitor } from './features/ScheduleMonitor'
import { AgentStatus } from './features/AgentStatus'
import { ChatPanel } from './features/ChatPanel'
import { MemoryBrowser } from './features/MemoryBrowser'

const TABS: { key: DashboardTab; label: string; icon: string }[] = [
  { key: 'schedule', label: 'Schedule', icon: '\u{1F4C5}' },
  { key: 'agents', label: 'Agents', icon: '\u{1F916}' },
  { key: 'chat', label: 'Chat', icon: '\u{1F4AC}' },
  { key: 'memory', label: 'Memory', icon: '\u{1F9E0}' },
]

export default function App() {
  const [activeTab, setActiveTab] = useState<DashboardTab>('schedule')

  return (
    <div className="flex flex-col h-full" style={{ background: 'var(--bg)' }}>
      {/* Tab Bar */}
      <nav
        className="flex items-center flex-shrink-0"
        style={{
          height: 44,
          padding: '0 var(--space-4)',
          gap: 'var(--space-1)',
          borderBottom: '1px solid var(--separator)',
          background: 'var(--material-thick)',
          backdropFilter: 'blur(20px)',
          WebkitBackdropFilter: 'blur(20px)',
        }}
      >
        {TABS.map(tab => {
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              onClick={() => setActiveTab(tab.key)}
              className="focus-ring flex items-center"
              style={{
                border: 'none',
                cursor: 'pointer',
                padding: '6px 14px',
                borderRadius: 'var(--radius-sm)',
                fontSize: 'var(--text-footnote)',
                fontWeight: isActive ? 'var(--weight-semibold)' : 'var(--weight-medium)',
                gap: 'var(--space-2)',
                transition: 'all 150ms var(--ease-smooth)',
                background: isActive ? 'var(--accent-fill)' : 'transparent',
                color: isActive ? 'var(--accent)' : 'var(--text-secondary)',
              }}
            >
              <span style={{ fontSize: 14 }}>{tab.icon}</span>
              <span>{tab.label}</span>
            </button>
          )
        })}
      </nav>

      {/* Content */}
      <div className="flex-1 overflow-hidden" style={{ position: 'relative' }}>
        <div
          className="h-full overflow-y-auto"
          style={{ padding: 'var(--space-4)' }}
        >
          {activeTab === 'schedule' && <ScheduleMonitor />}
          {activeTab === 'agents' && <AgentStatus />}
          {activeTab === 'chat' && <ChatPanel />}
          {activeTab === 'memory' && <MemoryBrowser />}
        </div>
      </div>
    </div>
  )
}
