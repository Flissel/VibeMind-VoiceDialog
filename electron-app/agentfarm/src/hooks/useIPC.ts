import { useState, useEffect, useCallback, useRef } from 'react'
import type { ProjectsResponse, GenerationStatusResponse } from '../types'

/**
 * Hook for IPC communication with VibeMind backend.
 * Wraps window.vibemindAgentFarm calls with loading/error states.
 */

const api = typeof window !== 'undefined' ? (window as any).vibemindAgentFarm : null

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
      setError('Agent Farm API nicht verfügbar')
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

// ── Projects ──

export function useProjects(statusFilter?: string) {
  return useIPCQuery<ProjectsResponse>(
    () => api.getProjects(statusFilter, 50),
    [statusFilter]
  )
}

export function useGenerationStatus(projectId?: string, jobId?: string) {
  return useIPCQuery<GenerationStatusResponse>(
    () => api.getProjectStatus(projectId, jobId),
    [projectId, jobId]
  )
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

    api.onMessage(handler)
  }, [messageType])
}
