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
}

export interface VideoListResponse {
  success: boolean
  message: string
  videos: VideoFileInfo[]
}
