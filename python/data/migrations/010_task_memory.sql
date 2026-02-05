-- Migration 010: Persistent Task Memory
-- Phase 15: Task Memory System
--
-- Tables for storing persistent tasks across conversation sessions.
-- Rachel can remember ongoing tasks and their status.

-- Persistent tasks table
CREATE TABLE IF NOT EXISTS persistent_tasks (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    session_id TEXT,

    -- Task info
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed, blocked, cancelled

    -- Timestamps
    created_at TEXT,
    started_at TEXT,
    completed_at TEXT,

    -- Execution context
    intent_type TEXT,      -- original event_type (idea.move, code.generate, etc.)
    payload TEXT,          -- JSON of original parameters
    job_id TEXT,           -- last job_id for this task
    progress INTEGER DEFAULT 0,
    stage TEXT,

    -- Results
    result TEXT,
    error TEXT,

    -- Priority and tags
    priority INTEGER DEFAULT 2,  -- 1=low, 2=medium, 3=high
    tags TEXT,  -- JSON array

    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_tasks_user ON persistent_tasks(user_id);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON persistent_tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_session ON persistent_tasks(session_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON persistent_tasks(created_at);
