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

// ── Projects ──

export interface ProjectInfo {
  id: string
  name: string
  description: string | null
  status: string // shuttling, active, generating, completed, idle
  generation_status: string | null
  convergence_progress: number | null
  tech_stack: string | null
  job_id: string | null
  project_path: string | null
  error_message: string | null
  created_at: string | null
  total_issues: number
  quality_score: number
  task_count: number
  stages_completed: number
  total_stages: number
}

export interface ProjectsResponse {
  type: 'generated_projects_list'
  projects: ProjectInfo[]
  error?: string
}

export interface GenerationStatusResponse {
  type: 'generation_status'
  project_id?: string
  name?: string
  status?: string
  progress?: number
  phase?: string
  phase_error?: string
  error?: string
}

// ── Plugins ──

export interface PluginInfo {
  id: string
  name: string
  version: string
  description: string
  author: string
  category: string
  changelog: string
  stream: string
  event_count: number
  enabled: boolean
  builtin: boolean
  is_new: boolean
  is_updated: boolean
  env_flag: string | null
  dependencies: string[]
}

export interface PluginListResponse {
  type: 'plugin_list'
  plugins: PluginInfo[]
  total_enabled: number
  total_available: number
  error?: string
}

export interface PluginActionResponse {
  type: 'plugin_action_result'
  action: 'accept' | 'reject' | 'toggle'
  plugin_id: string
  success: boolean
  enabled?: boolean
  error?: string
}

// ── Tab ──

export type DashboardTab = 'schedule' | 'agents' | 'chat' | 'memory' | 'plugins'
