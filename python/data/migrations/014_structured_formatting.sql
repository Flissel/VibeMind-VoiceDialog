-- Migration 014: Add structured formatting fields to canvas_nodes table
-- Enables LLM-driven structured content formatting (action lists, tables, etc.)

-- Add structured formatting columns to canvas_nodes table
ALTER TABLE canvas_nodes ADD COLUMN format_schema TEXT;  -- JSON schema defining allowed structure
ALTER TABLE canvas_nodes ADD COLUMN content_json TEXT;   -- Structured JSON content (alternative to plain text)
ALTER TABLE canvas_nodes ADD COLUMN last_formatted TEXT; -- ISO timestamp when content was last structured

-- Indexes for efficient queries on structured content
CREATE INDEX IF NOT EXISTS idx_canvas_nodes_format_schema ON canvas_nodes(format_schema) WHERE format_schema IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_canvas_nodes_last_formatted ON canvas_nodes(last_formatted) WHERE last_formatted IS NOT NULL;

-- Index for finding nodes with structured content
CREATE INDEX IF NOT EXISTS idx_canvas_nodes_structured ON canvas_nodes(id) WHERE content_json IS NOT NULL;