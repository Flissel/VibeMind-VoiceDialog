// VibeCoder field: what it says when the main process does not answer it at all.
//
// Lauf of the operator (2026-11-26): the field "VibeCoder — Workflow Setup" stayed empty; its old backend
// (python spaces.n8n) is missing from the installation. Since steps 4 and 5 the field is a chat with the
// OpenFang agent brain-n8n through the main process (vibecoder-chat.js), which gives its own sentences for
// OpenFang down, agent missing and n8n tools missing. This one is left for a page without that channel.

export const VIBECODER_NOT_CONNECTED =
  'Der VibeCoder ist noch nicht verbunden. Den n8n-Editor rechts kannst du wie gewohnt benutzen.'
