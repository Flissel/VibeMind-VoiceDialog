import { useState, useEffect, useCallback, useRef } from 'react'
import type {
  MemoryOverviewResponse,
  MemorySearchResponse,
  ScheduledTasksResponse,
  AgentStatusResponse,
  ConversationHistoryResponse,
  ProjectsResponse,
  GenerationStatusResponse,
  PluginListResponse,
} from '../types'

/**
 * Hook for IPC communication with VibeMind backend.
 * Wraps window.vibemindDashboard calls with loading/error states.
 */

const api = typeof window !== 'undefined' ? (window as any).vibemindDashboard : null

// ── Generic fetch hook ──

export function useIPCQuery<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = []
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    if (!api) {
      setError('Dashboard API nicht verfügbar')
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const result = await fetcher()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e))
    } finally {
      setLoading(false)
    }
  }, deps)

  useEffect(() => {
    refresh()
  }, [refresh])

  return { data, loading, error, refresh }
}

// ── Memory ──

export function useMemoryOverview() {
  return useIPCQuery<MemoryOverviewResponse>(
    () => api.getMemoryOverview(),
    []
  )
}

export function useMemorySearch(query: string, category: string, limit = 20) {
  return useIPCQuery<MemorySearchResponse>(
    () => api.searchMemory(query, category, limit),
    [query, category, limit]
  )
}

// ── Schedule ──

export function useScheduledTasks(status?: string) {
  return useIPCQuery<ScheduledTasksResponse>(
    () => api.getScheduledTasks(status, 50),
    [status]
  )
}

export async function updateTaskStatus(taskId: string, status: string) {
  if (!api) throw new Error('API not available')
  return api.updateTaskStatus(taskId, status)
}

// ── Agents ──

export function useAgentStatus() {
  return useIPCQuery<AgentStatusResponse>(() => api.getAgentStatus(), [])
}

// ── Chat ──

export async function sendChatMessage(text: string) {
  if (!api) throw new Error('API not available')
  return api.sendChatMessage(text)
}

export function useConversationHistory(limit = 50) {
  return useIPCQuery<ConversationHistoryResponse>(
    () => api.getConversationHistory(limit),
    [limit]
  )
}

// ── Projects ──

export function useProjects(statusFilter?: string) {
  return useIPCQuery<ProjectsResponse>(
    () => api.getProjects(statusFilter, 50),
    [statusFilter]
  )
}

export function useGenerationStatus(projectId?: string, jobId?: string) {
  return useIPCQuery<GenerationStatusResponse>(
    () => api.getGenerationStatus(projectId, jobId),
    [projectId, jobId]
  )
}

// ── Plugins ──

export function usePlugins() {
  return useIPCQuery<PluginListResponse>(() => api.getPlugins(), [])
}

export async function acceptPlugin(pluginId: string) {
  if (!api) throw new Error('API not available')
  return api.acceptPlugin(pluginId)
}

export async function rejectPlugin(pluginId: string) {
  if (!api) throw new Error('API not available')
  return api.rejectPlugin(pluginId)
}

export async function togglePlugin(pluginId: string, enabled: boolean) {
  if (!api) throw new Error('API not available')
  return api.togglePlugin(pluginId, enabled)
}

// ── AgentFarm / Autogen ──

export function useAgentFarmTeams() {
  return useIPCQuery<any>(() => api.agentfarmListTeams(), [])
}

export function useAgentFarmStatus() {
  return useIPCQuery<any>(() => api.agentfarmStatus(), [])
}

export async function createAgentTeam(templateId: string | null, config?: any) {
  if (!api) throw new Error('API not available')
  return api.agentfarmCreateTeam(templateId, config)
}

export async function runAgentTeam(teamId: string, task: string) {
  if (!api) throw new Error('API not available')
  return api.agentfarmRunTeam(teamId, task)
}

export async function stopAgentRun(runId: string) {
  if (!api) throw new Error('API not available')
  return api.agentfarmStopRun(runId)
}

export async function getAgentRunResults(runId: string) {
  if (!api) throw new Error('API not available')
  return api.agentfarmRunResults(runId)
}

// ── Python message listener ──

export function usePythonMessages(
  messageType: string,
  callback: (message: Record<string, unknown>) => void
) {
  const callbackRef = useRef(callback)
  callbackRef.current = callback

  useEffect(() => {
    if (!api) return

    const handler = (msg: Record<string, unknown>) => {
      if (msg.type === messageType) {
        callbackRef.current(msg)
      }
    }

    api.onPythonMessage(handler)
    // Note: No cleanup since Electron IPC listeners are per-renderer lifecycle
  }, [messageType])
}
