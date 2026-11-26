// The sub-tabs of the Agent Farm, and which of them are shown.
//
// R2: "Pipeline" and "Teams" are hidden, not removed. Their code stays; whoever wants them back sets
// localStorage "vibemind.agentfarm.alleReiter" to "1" and opens the Agent Farm again.
import type { AgentFarmTab } from './types'

export const SUB_TABS: readonly { key: AgentFarmTab; label: string }[] = [
  { key: 'autogen', label: 'Pipeline' },
  { key: 'teams', label: 'Teams' },
  { key: 'n8n', label: 'n8n' },
  { key: 'rowboat', label: 'Rowboat' },
  { key: 'openfang', label: 'OpenFang' },
]

/** Hidden unless the switch below is set. */
export const HIDDEN_SUB_TABS: readonly AgentFarmTab[] = ['autogen', 'teams']

/** localStorage key that shows every sub-tab again. */
export const ALLE_REITER_KEY = 'vibemind.agentfarm.alleReiter'

type Storage = { getItem(key: string): string | null } | null | undefined

/** Whether the person asked for every sub-tab; a storage that is missing or throws counts as no. */
export function alleReiter(getStorage: () => Storage): boolean {
  try {
    const storage = getStorage()
    return Boolean(storage) && storage!.getItem(ALLE_REITER_KEY) === '1'
  } catch {
    return false
  }
}

/** The sub-tabs to show, in their order. */
export function shownTabs(all: boolean): { key: AgentFarmTab; label: string }[] {
  return SUB_TABS.filter(tab => all || !HIDDEN_SUB_TABS.includes(tab.key))
}

/** The tab the Agent Farm opens with: the first one shown (n8n while Pipeline and Teams are hidden). */
export function startTab(all: boolean): AgentFarmTab {
  return shownTabs(all)[0].key
}

/** A switch asked by the main process: only to a tab that is shown, otherwise null (ignored). */
export function switchTarget(tab: unknown, all: boolean): AgentFarmTab | null {
  return shownTabs(all).some(t => t.key === tab) ? (tab as AgentFarmTab) : null
}
