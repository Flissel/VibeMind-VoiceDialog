-- Migration 011: Evaluation Data Tables
-- Stores synthetic test utterances and evaluation run results

-- Synthetic test utterances for batch evaluation
CREATE TABLE IF NOT EXISTS synthetic_utterances (
    id TEXT PRIMARY KEY,
    text TEXT NOT NULL,
    expected_intent TEXT NOT NULL,
    expected_payload TEXT,  -- JSON
    category TEXT,
    difficulty TEXT,  -- easy, medium, hard
    tags TEXT,  -- JSON array
    source TEXT DEFAULT 'manual',  -- manual | generated | user_feedback
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_synthetic_intent ON synthetic_utterances(expected_intent);
CREATE INDEX IF NOT EXISTS idx_synthetic_category ON synthetic_utterances(category);
CREATE INDEX IF NOT EXISTS idx_synthetic_difficulty ON synthetic_utterances(difficulty);

-- Evaluation runs (batch test executions)
CREATE TABLE IF NOT EXISTS evaluation_runs (
    id TEXT PRIMARY KEY,
    name TEXT,
    started_at TEXT,
    completed_at TEXT,
    total_tests INTEGER,
    correct INTEGER,
    accuracy REAL,
    config TEXT,  -- JSON: classifier model, flags, etc.
    report TEXT   -- JSON: full evaluation report
);

CREATE INDEX IF NOT EXISTS idx_eval_runs_started ON evaluation_runs(started_at DESC);

-- Individual test results
CREATE TABLE IF NOT EXISTS evaluation_results (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES evaluation_runs(id),
    utterance_id TEXT,  -- Optional reference to synthetic_utterances

    -- Input
    input_text TEXT NOT NULL,
    expected_intent TEXT,
    expected_payload TEXT,  -- JSON

    -- Output
    predicted_intent TEXT,
    predicted_payload TEXT,  -- JSON
    confidence REAL,
    hypotheses TEXT,  -- JSON array of all hypotheses

    -- Evaluation
    is_correct INTEGER,
    intent_match INTEGER,
    payload_match INTEGER,
    latency_ms REAL,

    -- Metadata
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run ON evaluation_results(run_id);
CREATE INDEX IF NOT EXISTS idx_eval_results_intent ON evaluation_results(expected_intent);
CREATE INDEX IF NOT EXISTS idx_eval_results_correct ON evaluation_results(is_correct);
CREATE INDEX IF NOT EXISTS idx_eval_results_created ON evaluation_results(created_at DESC);
