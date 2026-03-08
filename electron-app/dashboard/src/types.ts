/* ── VibeMind Dashboard Types ─────────────────────────────── */

// ── Memory ──

export interface MemoryServiceStatus {
  available: boolean
  status?: string
  error?: string
  top_intents?: Array<{ intent: string; count: number }>
}

export interface MemoryOverviewResponse {
  type: 'memory_overview'
  data: {
    task_memory: MemoryServiceStatus
    conversation_memory: MemoryServiceStatus
    user_profiles: MemoryServiceStatus
  }
}

export interface MemorySearchResult {
  id: string
  content: string
  metadata: Record<string, unknown>
  score?: number
  timestamp?: string
}

export interface MemorySearchResponse {
  type: 'memory_search_results'
  category: string
  results: MemorySearchResult[]
}

export interface RecentMemoryResponse {
  type: 'recent_memory'
  category: string
  results: MemorySearchResult[]
}

// ── Schedule ──

export interface ScheduledTask {
  id: string
  title: string
  description: string
  action_text: string
  trigger_type: 'date' | 'cron' | 'interval'
  trigger_config: string // JSON string
  execution_mode: string
  timezone: string
  status: 'active' | 'paused' | 'completed' | 'cancelled' | 'failed'
  next_run_at: string | null
  last_run_at: string | null
  run_count: number
  max_runs: number | null
  last_result: string | null
  last_error: string | null
  created_at: string
  updated_at: string | null
  metadata: Record<string, unknown>
}

export interface ScheduledTasksResponse {
  type: 'scheduled_tasks_list'
  tasks: ScheduledTask[]
  total: number
}

export interface TaskStatusUpdateResponse {
  type: 'task_status_updated'
  success: boolean
  task_id: string
  new_status: string
}

// ── Agents ──

export interface AgentStatusInfo {
  name: string
  status: 'idle' | 'started' | 'completed' | 'error'
  last_event_type: string | null
  last_event_at: string | null
  last_result: string | null
  error: string | null
}

export interface AgentStatusResponse {
  type: 'agent_status_list'
  agents: AgentStatusInfo[]
}

// ── Chat ──

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  timestamp: number
  event_type?: string
}

export interface ChatResponse {
  type: 'chat_response'
  success: boolean
  message: string
  event_type?: string
  data?: Record<string, unknown>
}

export interface ConversationHistoryResponse {
  type: 'conversation_history'
  messages: Array<{
    speaker: string
    text: string
    timestamp: string
  }>
}

// ── Tab ──

export type DashboardTab = 'schedule' | 'agents' | 'chat' | 'memory'
