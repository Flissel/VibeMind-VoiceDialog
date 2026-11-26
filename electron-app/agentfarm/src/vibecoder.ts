// VibeCoder field: what it says when its backend does not answer.
//
// Lauf of the operator (2026-11-26): the field "VibeCoder — Workflow Setup" stayed empty. Its backend
// (python spaces.n8n) is missing from the installation, so the start answered success: false with
// "No module named 'spaces.n8n'" and no checklist; the field showed nothing at all. Now it says so in one
// sentence; the raw error is not shown. The n8n editor on the right does not depend on it.

export const VIBECODER_NOT_CONNECTED =
  'Der VibeCoder ist noch nicht verbunden: sein Baustein fehlt in dieser Installation. Den n8n-Editor rechts kannst du wie gewohnt benutzen.'

/** The sentence for the field after the start, or null when the checklist came. */
export function startNotice(result: unknown): string | null {
  if (!result || typeof result !== 'object') return VIBECODER_NOT_CONNECTED
  const r = result as { success?: unknown; session_id?: unknown; checklist_items?: unknown }
  if (r.success === false) return VIBECODER_NOT_CONNECTED
  if (typeof r.session_id !== 'string' || !r.session_id) return VIBECODER_NOT_CONNECTED
  if (!Array.isArray(r.checklist_items) || r.checklist_items.length === 0) return VIBECODER_NOT_CONNECTED
  return null
}
