-- Migration 012: Real-Time Evaluation Tables
-- Stores corrections from user feedback for training improvement

-- Corrections table for training data
CREATE TABLE IF NOT EXISTS intent_corrections (
    id TEXT PRIMARY KEY,
    original_log_id TEXT,  -- Reference to intent_analysis_log
    session_id TEXT,

    -- Original classification
    original_input TEXT NOT NULL,
    original_intent TEXT NOT NULL,
    original_payload TEXT,  -- JSON

    -- Correction
    corrected_intent TEXT,
    corrected_payload TEXT,  -- JSON
    user_explanation TEXT,

    -- Metadata
    created_at TEXT DEFAULT (datetime('now')),
    used_for_training INTEGER DEFAULT 0  -- 0 = not used, 1 = used
);

CREATE INDEX IF NOT EXISTS idx_corrections_session ON intent_corrections(session_id);
CREATE INDEX IF NOT EXISTS idx_corrections_training ON intent_corrections(used_for_training);
CREATE INDEX IF NOT EXISTS idx_corrections_original ON intent_corrections(original_intent);
CREATE INDEX IF NOT EXISTS idx_corrections_corrected ON intent_corrections(corrected_intent);
CREATE INDEX IF NOT EXISTS idx_corrections_created ON intent_corrections(created_at DESC);

-- Real-time accuracy statistics view
CREATE VIEW IF NOT EXISTS realtime_accuracy AS
SELECT
    date(created_at) as date,
    COUNT(*) as total,
    SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct,
    SUM(CASE WHEN was_correct = 0 THEN 1 ELSE 0 END) as incorrect,
    SUM(CASE WHEN was_correct IS NULL THEN 1 ELSE 0 END) as pending,
    ROUND(
        100.0 * SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) /
        NULLIF(SUM(CASE WHEN was_correct IS NOT NULL THEN 1 ELSE 0 END), 0),
        2
    ) as accuracy_percent
FROM intent_analysis_log
GROUP BY date(created_at)
ORDER BY date DESC;

-- Accuracy by intent type view
CREATE VIEW IF NOT EXISTS accuracy_by_intent AS
SELECT
    selected_intent as intent,
    COUNT(*) as total,
    SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) as correct,
    SUM(CASE WHEN was_correct = 0 THEN 1 ELSE 0 END) as incorrect,
    ROUND(
        100.0 * SUM(CASE WHEN was_correct = 1 THEN 1 ELSE 0 END) /
        NULLIF(SUM(CASE WHEN was_correct IS NOT NULL THEN 1 ELSE 0 END), 0),
        2
    ) as accuracy_percent
FROM intent_analysis_log
WHERE was_correct IS NOT NULL
GROUP BY selected_intent
ORDER BY accuracy_percent ASC;

-- Correction patterns view (most common misclassifications)
CREATE VIEW IF NOT EXISTS correction_patterns AS
SELECT
    original_intent,
    corrected_intent,
    COUNT(*) as occurrences,
    GROUP_CONCAT(SUBSTR(original_input, 1, 50), ' | ') as example_inputs
FROM intent_corrections
WHERE corrected_intent IS NOT NULL
GROUP BY original_intent, corrected_intent
ORDER BY occurrences DESC;
