-- Migration 009: Conversion AI Tables
-- Phase 13: Multi-Agent Intent Analysis System
--
-- Tables for storing AI personalities, user preferences, and intent analysis logs.

-- Conversion AI Personalities
-- Stores the AI's personality configuration per user
CREATE TABLE IF NOT EXISTS conversion_ai_personalities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    style TEXT DEFAULT 'casual',      -- formal | casual | technical
    verbosity TEXT DEFAULT 'concise', -- concise | detailed
    traits TEXT,                       -- JSON array of traits
    language TEXT DEFAULT 'de',
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_personalities_user ON conversion_ai_personalities(user_id);

-- User Interaction Preferences (learned over time)
-- Stores preferences the AI learns about users during interactions
CREATE TABLE IF NOT EXISTS user_preferences (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    preference_key TEXT NOT NULL,
    preference_value TEXT,
    confidence REAL DEFAULT 0.5,      -- 0.0-1.0 confidence level
    learned_at TEXT,
    UNIQUE(user_id, preference_key)
);

CREATE INDEX IF NOT EXISTS idx_preferences_user ON user_preferences(user_id);

-- Intent Analysis Results (for improvement)
-- Logs all intent analysis results for accuracy tracking and improvement
CREATE TABLE IF NOT EXISTS intent_analysis_log (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    user_input TEXT NOT NULL,
    hypotheses TEXT,                   -- JSON array of IntentHypothesis
    selected_intent TEXT,
    was_correct INTEGER,               -- NULL = not evaluated, 1 = correct, 0 = incorrect
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_analysis_session ON intent_analysis_log(session_id);
CREATE INDEX IF NOT EXISTS idx_analysis_created ON intent_analysis_log(created_at);
