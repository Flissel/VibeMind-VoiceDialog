/// <reference types="vite/client" />

interface VibeMindDashboardAPI {
  // Memory
  getMemoryOverview: () => Promise<MemoryOverviewResponse>
  searchMemory: (query: string, category: string, limit: number) => Promise<MemorySearchResponse>
  getRecentMemory: (category: string, limit: number) => Promise<RecentMemoryResponse>
  // Schedule
  getScheduledTasks: (status?: string, limit?: number) => Promise<ScheduledTasksResponse>
  updateTaskStatus: (taskId: string, status: string) => Promise<TaskStatusUpdateResponse>
  // Agents
  getAgentStatus: () => Promise<AgentStatusResponse>
  // Chat
  sendChatMessage: (text: string) => Promise<ChatResponse>
  getConversationHistory: (limit?: number) => Promise<ConversationHistoryResponse>
  // Events
  onPythonMessage: (callback: (message: Record<string, unknown>) => void) => void
  // UI control
  closeDashboard: () => void
}

interface Window {
  vibemindDashboard: VibeMindDashboardAPI
}
