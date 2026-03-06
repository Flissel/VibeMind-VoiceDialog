# Database

## Overview

VibeMind uses SQLite (`python/vibemind.db`) with a repository pattern. Schema version is managed via migrations.

## Schema (v14)

### ideas

Primary table for bubbles and ideas.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `title` | TEXT | Name/title |
| `description` | TEXT | Content body |
| `source` | TEXT | `voice` or `text` |
| `created_at` | TEXT | ISO timestamp |
| `score` | REAL | Composite quality score |
| `status` | TEXT | `active`, `archived`, `promoted` |
| `parent_id` | TEXT FK | Parent bubble (null = top-level) |
| `tags` | TEXT | JSON array |
| `metadata` | TEXT | JSON object |
| `agent_id` | TEXT | Creating agent |
| `format_schema` | TEXT | JSON format definition |
| `content_json` | TEXT | Structured content |
| `embedding_vector` | BLOB | Semantic embedding |
| `embedding_hash` | TEXT | Embedding cache key |

### projects

Code generation projects.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `name` | TEXT | Project name |
| `description` | TEXT | Project description |
| `generation_status` | TEXT | `pending`, `generating`, `complete`, `error` |
| `from_idea_id` | TEXT FK | Source idea |
| `project_path` | TEXT | Local filesystem path |
| `vnc_port` | INTEGER | VNC preview port |
| `preview_url` | TEXT | Live preview URL |
| `tech_stack` | TEXT | Detected technologies |
| `job_id` | TEXT | Coding engine job ID |

### canvas_nodes

Visual nodes in the 3D scene.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `node_type` | TEXT | `idea`, `project`, `note`, `image`, `link` |
| `title` | TEXT | Display title |
| `x`, `y` | REAL | 3D position |
| `linked_idea_id` | TEXT FK | → ideas.id |
| `linked_project_id` | TEXT FK | → projects.id |
| `format_schema` | TEXT | JSON format definition |
| `content_json` | TEXT | Structured content |

### canvas_edges

Connections between nodes.

| Column | Type | Description |
|--------|------|-------------|
| `from_node_id` | TEXT FK | Source node |
| `to_node_id` | TEXT FK | Target node |
| `edge_type` | TEXT | `related`, `parent`, `depends_on`, etc. |

### conversation_sessions / conversation_history

Voice dialog session and message storage.

### shuttles

Requirements evaluation pipeline state.

### exploration_sessions

AI-driven idea exploration sessions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `bubble_id` | TEXT FK | Parent bubble being explored |
| `started_at` | TEXT | ISO timestamp |
| `status` | TEXT | `active`, `completed`, `cancelled` |
| `strategy` | TEXT | Exploration strategy used |

### exploration_nodes

Nodes discovered during exploration sessions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `session_id` | TEXT FK | -> exploration_sessions.id |
| `title` | TEXT | Discovered concept title |
| `description` | TEXT | Concept description |
| `depth` | INTEGER | Discovery depth from root |
| `parent_node_id` | TEXT FK | Parent exploration node |

### discovered_edges

Edges discovered between exploration nodes.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `session_id` | TEXT FK | -> exploration_sessions.id |
| `from_node_id` | TEXT FK | Source exploration node |
| `to_node_id` | TEXT FK | Target exploration node |
| `edge_type` | TEXT | Relationship type |
| `confidence` | REAL | Discovery confidence score |

### mermaid_diagrams

Stored Mermaid diagram definitions for visualization.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `bubble_id` | TEXT FK | Associated bubble |
| `diagram_type` | TEXT | `flowchart`, `mindmap`, `sequence`, etc. |
| `mermaid_code` | TEXT | Mermaid DSL source |
| `created_at` | TEXT | ISO timestamp |

### scheduled_tasks

APScheduler task definitions.

| Column | Type | Description |
|--------|------|-------------|
| `id` | TEXT PK | UUID |
| `task_type` | TEXT | `reminder`, `alarm`, `recurring` |
| `title` | TEXT | Task description |
| `trigger_at` | TEXT | ISO timestamp for next execution |
| `cron_expr` | TEXT | Cron expression for recurring tasks |
| `payload` | TEXT | JSON payload for execution |
| `status` | TEXT | `pending`, `fired`, `cancelled` |

## Repository Pattern

```python
from data import IdeasRepository, CanvasRepository

repo = IdeasRepository()
idea = repo.create(title="My Idea", description="Details")
found = repo.get_by_title_fuzzy("my idea")  # Accent-insensitive
all_ideas = repo.get_children(parent_id="bubble-123")
```

Available repositories: `IdeasRepository`, `CanvasRepository`, `ProjectsRepository`, `ConversationRepository`, `ShuttleRepository`, `ScheduleRepository`

## Migrations

Schema changes are in `python/data/database.py`. The `_run_migrations()` function checks the current schema version and applies changes sequentially.

## Key Files

| File | Purpose |
|------|---------|
| `python/data/database.py` | Connection, schema, migrations |
| `python/data/models.py` | Dataclass definitions |
| `python/data/repository.py` | CRUD operations |
