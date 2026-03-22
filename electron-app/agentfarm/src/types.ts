/* ── VibeMind Agent Farm Types ─────────────────────────────── */

// ── Projects ──

export interface ProjectInfo {
  id: string
  name: string
  description: string | null
  status: string
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

// ── Sub-Tab ──

export type AgentFarmTab = 'autogen' | 'n8n'

// ── Video ──

export interface VideoStatusResponse {
  success: boolean
  message: string
  vibevideo_installed: boolean
  deepfake_installed: boolean
  available_tools: string[]
}

export interface VideoToolResult {
  success: boolean
  message: string
  stdout?: string
  stderr?: string
  exit_code?: number
}

export interface VideoFileInfo {
  path: string
  filename: string
  size_bytes: number
  size_human: string
  category: string
  modified: number
  modified_iso: string
}

export interface VideoListResponse {
  success: boolean
  message: string
  videos: VideoFileInfo[]
}
