-- Migration 013: Add parent_id to ideas table for bubble hierarchy
-- This enables nested bubbles (parent-child relationships)

ALTER TABLE ideas ADD COLUMN parent_id TEXT;

-- Index for efficient hierarchy queries
CREATE INDEX IF NOT EXISTS idx_ideas_parent_id ON ideas(parent_id);

-- Composite index for listing children of a parent
CREATE INDEX IF NOT EXISTS idx_ideas_parent_title ON ideas(parent_id, title);
