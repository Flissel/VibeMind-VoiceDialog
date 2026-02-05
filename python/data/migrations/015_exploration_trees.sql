-- Migration 015: Add exploration tree tables for AI-Scientist-style idea connection discovery
-- Enables tree-based exploration of connections between ideas using BFTS algorithm

-- ============================================================
-- Table: exploration_sessions
-- Tracks individual exploration sessions (when user says "Finde Verbindungen")
-- ============================================================
CREATE TABLE IF NOT EXISTS exploration_sessions (
    id TEXT PRIMARY KEY,
    root_bubble_id TEXT NOT NULL,
    root_bubble_title TEXT,
    exploration_query TEXT,          -- Original user request
    status TEXT DEFAULT 'running',   -- running, completed, paused, stopped
    current_stage INTEGER DEFAULT 1, -- 1=direct, 2=indirect, 3=abstract, 4=creative
    created_at TEXT DEFAULT (datetime('now')),
    completed_at TEXT,
    total_nodes_explored INTEGER DEFAULT 0,
    best_score REAL DEFAULT 0.0,
    metadata TEXT,                   -- JSON for extra data
    FOREIGN KEY (root_bubble_id) REFERENCES ideas(id) ON DELETE CASCADE
);

-- Indexes for exploration_sessions
CREATE INDEX IF NOT EXISTS idx_exploration_sessions_status ON exploration_sessions(status);
CREATE INDEX IF NOT EXISTS idx_exploration_sessions_root ON exploration_sessions(root_bubble_id);
CREATE INDEX IF NOT EXISTS idx_exploration_sessions_created ON exploration_sessions(created_at);

-- ============================================================
-- Table: exploration_nodes
-- Individual discovered connections in the exploration tree
-- ============================================================
CREATE TABLE IF NOT EXISTS exploration_nodes (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL,
    step INTEGER NOT NULL,           -- Order of discovery
    parent_node_id TEXT,             -- Parent in exploration tree

    -- Connection details
    source_bubble_id TEXT NOT NULL,
    source_bubble_title TEXT,
    target_bubble_id TEXT NOT NULL,
    target_bubble_title TEXT,
    connection_type TEXT DEFAULT 'semantic',  -- semantic, causal, creative, etc.
    reasoning TEXT,                  -- LLM-generated explanation
    edge_label TEXT,                 -- Short label for visualization

    -- Scoring
    embedding_similarity REAL DEFAULT 0.0,
    llm_confidence REAL DEFAULT 0.0,
    combined_score REAL DEFAULT 0.0,

    -- Tree metadata
    exploration_depth INTEGER DEFAULT 1,

    -- Status
    is_accepted INTEGER DEFAULT 0,   -- User accepted this connection
    is_rejected INTEGER DEFAULT 0,   -- User rejected this connection
    is_valid INTEGER DEFAULT 1,      -- Connection is valid

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    metadata TEXT,                   -- JSON for extra data

    FOREIGN KEY (session_id) REFERENCES exploration_sessions(id) ON DELETE CASCADE,
    FOREIGN KEY (source_bubble_id) REFERENCES ideas(id) ON DELETE CASCADE,
    FOREIGN KEY (target_bubble_id) REFERENCES ideas(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_node_id) REFERENCES exploration_nodes(id) ON DELETE SET NULL
);

-- Indexes for exploration_nodes
CREATE INDEX IF NOT EXISTS idx_exploration_nodes_session ON exploration_nodes(session_id);
CREATE INDEX IF NOT EXISTS idx_exploration_nodes_score ON exploration_nodes(combined_score DESC);
CREATE INDEX IF NOT EXISTS idx_exploration_nodes_source ON exploration_nodes(source_bubble_id);
CREATE INDEX IF NOT EXISTS idx_exploration_nodes_target ON exploration_nodes(target_bubble_id);
CREATE INDEX IF NOT EXISTS idx_exploration_nodes_depth ON exploration_nodes(exploration_depth);
CREATE INDEX IF NOT EXISTS idx_exploration_nodes_valid ON exploration_nodes(is_valid) WHERE is_valid = 1;
CREATE INDEX IF NOT EXISTS idx_exploration_nodes_accepted ON exploration_nodes(is_accepted) WHERE is_accepted = 1;

-- ============================================================
-- Table: discovered_edges
-- Permanent edges created from accepted exploration results
-- These are shown in the main bubble visualization
-- ============================================================
CREATE TABLE IF NOT EXISTS discovered_edges (
    id TEXT PRIMARY KEY,
    from_idea_id TEXT NOT NULL,
    to_idea_id TEXT NOT NULL,
    edge_type TEXT DEFAULT 'discovered',  -- discovered, manual, auto_link
    edge_label TEXT,
    reasoning TEXT,                  -- Explanation of why this connection exists
    confidence REAL DEFAULT 0.0,
    connection_type TEXT,            -- semantic, causal, creative, etc.

    -- Source tracking
    exploration_session_id TEXT,     -- Which exploration found this (if any)
    exploration_node_id TEXT,        -- Specific node that created this

    -- Timestamps
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT,
    metadata TEXT,                   -- JSON for extra data

    FOREIGN KEY (from_idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
    FOREIGN KEY (to_idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
    FOREIGN KEY (exploration_session_id) REFERENCES exploration_sessions(id) ON DELETE SET NULL
);

-- Indexes for discovered_edges
CREATE INDEX IF NOT EXISTS idx_discovered_edges_from ON discovered_edges(from_idea_id);
CREATE INDEX IF NOT EXISTS idx_discovered_edges_to ON discovered_edges(to_idea_id);
CREATE INDEX IF NOT EXISTS idx_discovered_edges_type ON discovered_edges(edge_type);
CREATE INDEX IF NOT EXISTS idx_discovered_edges_confidence ON discovered_edges(confidence DESC);
CREATE INDEX IF NOT EXISTS idx_discovered_edges_session ON discovered_edges(exploration_session_id) WHERE exploration_session_id IS NOT NULL;

-- Unique constraint to prevent duplicate edges
CREATE UNIQUE INDEX IF NOT EXISTS idx_discovered_edges_unique
    ON discovered_edges(from_idea_id, to_idea_id, edge_type);

-- ============================================================
-- View: active_explorations
-- Quick access to currently running exploration sessions
-- ============================================================
CREATE VIEW IF NOT EXISTS active_explorations AS
SELECT
    s.id,
    s.root_bubble_id,
    s.root_bubble_title,
    s.exploration_query,
    s.current_stage,
    s.total_nodes_explored,
    s.best_score,
    s.created_at,
    COUNT(n.id) as node_count,
    MAX(n.combined_score) as max_score
FROM exploration_sessions s
LEFT JOIN exploration_nodes n ON s.id = n.session_id
WHERE s.status = 'running'
GROUP BY s.id;

-- ============================================================
-- View: best_connections
-- Top connections from all explorations
-- ============================================================
CREATE VIEW IF NOT EXISTS best_connections AS
SELECT
    n.id,
    n.source_bubble_title,
    n.target_bubble_title,
    n.edge_label,
    n.reasoning,
    n.combined_score,
    n.connection_type,
    n.exploration_depth,
    s.root_bubble_title as exploration_root,
    n.created_at
FROM exploration_nodes n
JOIN exploration_sessions s ON n.session_id = s.id
WHERE n.is_valid = 1 AND n.is_rejected = 0
ORDER BY n.combined_score DESC
LIMIT 100;
