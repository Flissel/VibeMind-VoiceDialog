/* ── VibeMind Video Studio Types ─────────────────────────────── */

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
  id?: string
}

export interface VideoDeleteResponse {
  success: boolean
  message: string
}

export interface VideoListResponse {
  success: boolean
  message: string
  videos: VideoFileInfo[]
}

// ── Video Project Types ──────────────────────────────────────

export interface VideoProject {
  id: string
  name: string
  description: string
  status: string
  created_at: string
  person_count: number
}

export interface PipelineStepInfo {
  label: string
  description: string
  input: string
  output: string
  api: string | null
}

export interface PipelineStepStatus {
  status: 'pending' | 'running' | 'completed' | 'failed' | 'skipped'
  output_path: string
  video_id: string
}

export interface PipelineMatrix {
  persons: string[]
  steps: string[]
  step_info: Record<string, PipelineStepInfo>
  matrix: Record<string, Record<string, PipelineStepStatus>>
}

export interface ReferencePipeline {
  person: string
  project_id: string
  steps: string[]
  step_info: Record<string, PipelineStepInfo>
  assets: Record<string, PipelineStepStatus>
}
