"""
Vibemind SQLite Database Manager

Handles database connection, schema creation, and migrations.
"""

import sqlite3
import os
from pathlib import Path
from typing import Optional
from contextlib import contextmanager

# Default database location
DEFAULT_DB_PATH = Path(__file__).parent.parent / "vibemind.db"

# Singleton database instance
_database_instance: Optional["Database"] = None


class Database:
    """
    SQLite database manager with connection pooling and schema management.

    Uses WAL mode for better concurrent access performance.
    """

    SCHEMA_VERSION = 8

    SCHEMA_SQL = """
    -- Ideas table: captures raw ideas from voice/text
    CREATE TABLE IF NOT EXISTS ideas (
        id TEXT PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT,
        source TEXT DEFAULT 'voice',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        score REAL DEFAULT 0.0,
        status TEXT DEFAULT 'raw',
        promoted_to_project_id TEXT,
        tags TEXT,
        metadata TEXT,
        agent_id TEXT,
        FOREIGN KEY (promoted_to_project_id) REFERENCES projects(id)
    );

    -- Projects table: promoted ideas or direct projects (with code generation support)
    CREATE TABLE IF NOT EXISTS projects (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        status TEXT DEFAULT 'active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        from_idea_id TEXT,
        progress REAL DEFAULT 0.0,
        metadata TEXT,
        -- Code Generation Fields (v4)
        project_path TEXT,
        generation_status TEXT DEFAULT 'pending',
        vnc_port INTEGER,
        job_id TEXT,
        requirements_json TEXT,
        convergence_progress REAL DEFAULT 0.0,
        preview_url TEXT,
        tech_stack TEXT,
        error_message TEXT,
        FOREIGN KEY (from_idea_id) REFERENCES ideas(id)
    );

    -- Canvas nodes: visual representation on canvas
    CREATE TABLE IF NOT EXISTS canvas_nodes (
        id TEXT PRIMARY KEY,
        node_type TEXT NOT NULL,
        title TEXT,
        content TEXT,
        x REAL DEFAULT 0.0,
        y REAL DEFAULT 0.0,
        linked_idea_id TEXT,
        linked_project_id TEXT,
        summary TEXT,
        metadata TEXT,
        FOREIGN KEY (linked_idea_id) REFERENCES ideas(id),
        FOREIGN KEY (linked_project_id) REFERENCES projects(id)
    );

    -- Canvas edges: connections between nodes
    CREATE TABLE IF NOT EXISTS canvas_edges (
        id TEXT PRIMARY KEY,
        from_node_id TEXT NOT NULL,
        to_node_id TEXT NOT NULL,
        edge_type TEXT DEFAULT 'default',
        FOREIGN KEY (from_node_id) REFERENCES canvas_nodes(id),
        FOREIGN KEY (to_node_id) REFERENCES canvas_nodes(id)
    );

    -- Conversation history: persists all voice dialog messages
    CREATE TABLE IF NOT EXISTS conversation_history (
        id TEXT PRIMARY KEY,
        session_id TEXT NOT NULL,
        speaker TEXT NOT NULL,
        text TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        metadata TEXT
    );

    -- Conversation sessions: groups messages into sessions
    CREATE TABLE IF NOT EXISTS conversation_sessions (
        id TEXT PRIMARY KEY,
        started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        ended_at TIMESTAMP,
        summary TEXT,
        agent_id TEXT,
        metadata TEXT
    );

    -- Shuttles table: tracks requirement evaluation progress (v5, updated v6, v7, v8)
    CREATE TABLE IF NOT EXISTS shuttles (
        id TEXT PRIMARY KEY,
        shuttle_id TEXT NOT NULL UNIQUE,
        bubble_id TEXT NOT NULL,
        bubble_name TEXT NOT NULL,
        score REAL DEFAULT 0.0,
        passed_count INTEGER DEFAULT 0,
        failed_count INTEGER DEFAULT 0,
        total_count INTEGER DEFAULT 0,
        status TEXT DEFAULT 'launching',
        current_stage TEXT DEFAULT 'mining',
        project_id TEXT,
        stage_type TEXT DEFAULT 'full',
        stage_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP,
        requirement_results TEXT,
        metadata TEXT,
        FOREIGN KEY (bubble_id) REFERENCES ideas(id),
        FOREIGN KEY (project_id) REFERENCES projects(id)
    );

    -- Schema version tracking
    CREATE TABLE IF NOT EXISTS schema_version (
        version INTEGER PRIMARY KEY
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_ideas_status ON ideas(status);
    CREATE INDEX IF NOT EXISTS idx_ideas_score ON ideas(score DESC);
    CREATE INDEX IF NOT EXISTS idx_ideas_created ON ideas(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
    CREATE INDEX IF NOT EXISTS idx_projects_job_id ON projects(job_id);
    CREATE INDEX IF NOT EXISTS idx_projects_generation_status ON projects(generation_status);
    CREATE INDEX IF NOT EXISTS idx_canvas_nodes_type ON canvas_nodes(node_type);
    CREATE INDEX IF NOT EXISTS idx_canvas_edges_from ON canvas_edges(from_node_id);
    CREATE INDEX IF NOT EXISTS idx_canvas_edges_to ON canvas_edges(to_node_id);
    CREATE INDEX IF NOT EXISTS idx_conversation_history_session ON conversation_history(session_id);
    CREATE INDEX IF NOT EXISTS idx_conversation_history_timestamp ON conversation_history(timestamp DESC);
    CREATE INDEX IF NOT EXISTS idx_conversation_sessions_started ON conversation_sessions(started_at DESC);
    CREATE INDEX IF NOT EXISTS idx_shuttles_bubble_id ON shuttles(bubble_id);
    CREATE INDEX IF NOT EXISTS idx_shuttles_status ON shuttles(status);
    CREATE INDEX IF NOT EXISTS idx_shuttles_created_at ON shuttles(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_shuttles_project_id ON shuttles(project_id);
    """

    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to vibemind.db in python/ dir.
        """
        self.db_path = db_path or DEFAULT_DB_PATH
        self._connection: Optional[sqlite3.Connection] = None
        self._ensure_database()

    def _ensure_database(self):
        """Create database and schema if they don't exist"""
        # Create parent directory if needed
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize schema
        with self.connection() as conn:
            conn.executescript(self.SCHEMA_SQL)

            # Check and apply migrations
            cursor = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cursor.fetchone()

            if row is None:
                # Fresh database
                conn.execute("INSERT INTO schema_version (version) VALUES (?)", (self.SCHEMA_VERSION,))
            else:
                current_version = row[0]
                if current_version < self.SCHEMA_VERSION:
                    self._apply_migrations(conn, current_version)

            conn.commit()

    def _apply_migrations(self, conn, from_version: int):
        """Apply schema migrations from from_version to SCHEMA_VERSION"""
        # Migration 1 -> 2: Add agent_id column to ideas table
        if from_version < 2:
            try:
                conn.execute("ALTER TABLE ideas ADD COLUMN agent_id TEXT")
            except Exception:
                pass  # Column may already exist

        # Migration 2 -> 3: Add summary column to canvas_nodes table
        if from_version < 3:
            try:
                conn.execute("ALTER TABLE canvas_nodes ADD COLUMN summary TEXT")
            except Exception:
                pass  # Column may already exist

        # Migration 3 -> 4: Add code generation fields to projects table
        if from_version < 4:
            code_gen_columns = [
                ("project_path", "TEXT"),
                ("generation_status", "TEXT DEFAULT 'pending'"),
                ("vnc_port", "INTEGER"),
                ("job_id", "TEXT"),
                ("requirements_json", "TEXT"),
                ("convergence_progress", "REAL DEFAULT 0.0"),
                ("preview_url", "TEXT"),
                ("tech_stack", "TEXT"),
                ("error_message", "TEXT"),
            ]
            for col_name, col_type in code_gen_columns:
                try:
                    conn.execute(f"ALTER TABLE projects ADD COLUMN {col_name} {col_type}")
                except Exception:
                    pass  # Column may already exist
            
            # Create new indexes for code generation queries
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_job_id ON projects(job_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_projects_generation_status ON projects(generation_status)")
            except Exception:
                pass

        # Migration 4 -> 5: Add shuttles table for requirement tracking
        if from_version < 5:
            try:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS shuttles (
                        id TEXT PRIMARY KEY,
                        shuttle_id TEXT NOT NULL UNIQUE,
                        bubble_id TEXT NOT NULL,
                        bubble_name TEXT NOT NULL,
                        score REAL DEFAULT 0.0,
                        passed_count INTEGER DEFAULT 0,
                        failed_count INTEGER DEFAULT 0,
                        total_count INTEGER DEFAULT 0,
                        status TEXT DEFAULT 'launching',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        completed_at TIMESTAMP,
                        requirement_results TEXT,
                        metadata TEXT,
                        FOREIGN KEY (bubble_id) REFERENCES ideas(id)
                    )
                """)
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shuttles_bubble_id ON shuttles(bubble_id)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shuttles_status ON shuttles(status)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shuttles_created_at ON shuttles(created_at DESC)")
            except Exception:
                pass  # Table may already exist

        # Migration 5 -> 6: Add current_stage column to shuttles table (DNA pipeline stages)
        if from_version < 6:
            try:
                conn.execute("ALTER TABLE shuttles ADD COLUMN current_stage TEXT DEFAULT 'mining'")
            except Exception:
                pass  # Column may already exist

        # Migration 6 -> 7: Add project_id column to shuttles table (link to project created at launch)
        if from_version < 7:
            try:
                conn.execute("ALTER TABLE shuttles ADD COLUMN project_id TEXT")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shuttles_project_id ON shuttles(project_id)")
            except Exception:
                pass  # Column/index may already exist

        # Migration 7 -> 8: Add stage_type and stage_data columns for multi-shuttle per checkpoint
        if from_version < 8:
            try:
                conn.execute("ALTER TABLE shuttles ADD COLUMN stage_type TEXT DEFAULT 'full'")
            except Exception:
                pass  # Column may already exist
            try:
                conn.execute("ALTER TABLE shuttles ADD COLUMN stage_data TEXT")
            except Exception:
                pass  # Column may already exist
            # Index for querying shuttles by bubble and stage type
            try:
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shuttles_stage_type ON shuttles(stage_type)")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_shuttles_bubble_stage ON shuttles(bubble_id, stage_type)")
            except Exception:
                pass  # Index may already exist

        # Update schema version
        conn.execute("UPDATE schema_version SET version = ?", (self.SCHEMA_VERSION,))

    @contextmanager
    def connection(self):
        """
        Get a database connection with proper configuration.

        Uses WAL mode for better concurrency.
        """
        conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable column access by name
        conn.execute("PRAGMA journal_mode=WAL")  # Better concurrent access
        conn.execute("PRAGMA foreign_keys=ON")  # Enforce foreign key constraints

        try:
            yield conn
        finally:
            conn.close()

    def execute(self, sql: str, params: tuple = ()):
        """Execute a single SQL statement"""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor

    def execute_many(self, sql: str, params_list: list):
        """Execute SQL statement with multiple parameter sets"""
        with self.connection() as conn:
            conn.executemany(sql, params_list)
            conn.commit()

    def fetch_one(self, sql: str, params: tuple = ()):
        """Fetch a single row"""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchone()

    def fetch_all(self, sql: str, params: tuple = ()):
        """Fetch all rows"""
        with self.connection() as conn:
            cursor = conn.execute(sql, params)
            return cursor.fetchall()

    def get_schema_version(self) -> int:
        """Get current schema version"""
        row = self.fetch_one("SELECT version FROM schema_version LIMIT 1")
        return row[0] if row else 0

    def close(self):
        """Close database connection if open"""
        if self._connection:
            self._connection.close()
            self._connection = None


def get_database(db_path: Optional[Path] = None) -> Database:
    """
    Get singleton database instance.

    Args:
        db_path: Optional custom database path (only used on first call)

    Returns:
        Database instance
    """
    global _database_instance

    if _database_instance is None:
        _database_instance = Database(db_path)

    return _database_instance


def reset_database():
    """Reset the singleton instance (for testing)"""
    global _database_instance
    if _database_instance:
        _database_instance.close()
        _database_instance = None
