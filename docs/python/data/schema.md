# Database Schema Reference

Canonical schema for VibeMind's SQLite database (`python/vibemind.db`).

**Schema version**: 14
**Source of truth**: `python/data/database.py` (`Database.SCHEMA_SQL`)

---

## ideas

Stores both top-level bubbles (spaces) and child ideas. Hierarchy via `parent_id`.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `title` | TEXT | | Display name |
| `description` | TEXT | | Free-text description |
| `source` | TEXT | | Origin (voice, manual, import) |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `score` | REAL | | Quality/relevance score |
| `status` | TEXT | | Current status |
| `promoted_to_project_id` | TEXT | FK -> projects.id | Link if promoted to project |
| `tags` | TEXT | | Comma-separated tags |
| `metadata` | TEXT | | JSON metadata blob |
| `agent_id` | TEXT | | Creating agent identifier |
| `parent_id` | TEXT | | Parent bubble ID (NULL = top-level) |
| `embedding_vector` | TEXT | | Cached semantic embedding (JSON array) |
| `embedding_hash` | TEXT | | Hash of text used to generate embedding |

---

## projects

Code generation projects created from ideas or directly.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `name` | TEXT | | Project name |
| `description` | TEXT | | Project description |
| `status` | TEXT | | General status |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `from_idea_id` | TEXT | FK -> ideas.id | Source idea if promoted |
| `progress` | REAL | | Overall progress (0.0 - 1.0) |
| `metadata` | TEXT | | JSON metadata blob |
| `project_path` | TEXT | | Filesystem path to generated code |
| `generation_status` | TEXT | | Generation pipeline status (pending/generating/converging/testing/completed/failed) |
| `vnc_port` | INTEGER | | VNC port for live preview |
| `job_id` | TEXT | | Background job identifier |
| `requirements_json` | TEXT | | JSON array of requirements |
| `convergence_progress` | REAL | | Convergence iteration progress |
| `preview_url` | TEXT | | Public preview URL |
| `tech_stack` | TEXT | | Technology stack description |
| `error_message` | TEXT | | Last error message if failed |

---

## canvas_nodes

Visual nodes displayed in the 3D bubble renderer.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `node_type` | TEXT | | Node category (idea, project, note) |
| `title` | TEXT | | Display title |
| `content` | TEXT | | Raw text content |
| `x` | REAL | | X coordinate in 3D space |
| `y` | REAL | | Y coordinate in 3D space |
| `linked_idea_id` | TEXT | FK -> ideas.id | Associated idea |
| `linked_project_id` | TEXT | FK -> projects.id | Associated project |
| `summary` | TEXT | | LLM-generated summary |
| `metadata` | TEXT | | JSON metadata blob |
| `format_schema` | TEXT | | Schema type (note, action_list, mind_map) |
| `content_json` | TEXT | | Structured content matching format_schema |
| `last_formatted` | TEXT | | Timestamp of last formatting |

---

## canvas_edges

Connections between canvas nodes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `from_node_id` | TEXT | FK -> canvas_nodes.id | Source node |
| `to_node_id` | TEXT | FK -> canvas_nodes.id | Target node |
| `edge_type` | TEXT | | Relationship type (related, depends_on, etc.) |

---

## conversation_history

Individual messages within conversation sessions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `session_id` | TEXT | | Session identifier |
| `speaker` | TEXT | | Who spoke (user, rachel, alice, adam, antoni) |
| `text` | TEXT | | Message content |
| `timestamp` | TIMESTAMP | | When the message was recorded |
| `metadata` | TEXT | | JSON metadata blob |

---

## conversation_sessions

Voice dialog session tracking.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `started_at` | TIMESTAMP | | Session start time |
| `ended_at` | TIMESTAMP | | Session end time |
| `summary` | TEXT | | LLM-generated session summary |
| `agent_id` | TEXT | | Primary agent for this session |
| `metadata` | TEXT | | JSON metadata blob |

---

## shuttles

Requirements pipeline tracking. A shuttle carries a bubble through validation stages.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `shuttle_id` | TEXT | UNIQUE | External shuttle identifier |
| `bubble_id` | TEXT | FK -> ideas.id | Source bubble |
| `bubble_name` | TEXT | | Bubble title at shuttle creation |
| `score` | REAL | | Overall quality score |
| `passed_count` | INTEGER | | Number of passed requirements |
| `failed_count` | INTEGER | | Number of failed requirements |
| `total_count` | INTEGER | | Total requirement count |
| `status` | TEXT | | Shuttle status (pending/in_progress/completed/failed) |
| `current_stage` | TEXT | | Active processing stage |
| `project_id` | TEXT | FK -> projects.id | Target project if promoted |
| `stage_type` | TEXT | | Current stage type identifier |
| `stage_data` | TEXT | | JSON data for current stage |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `completed_at` | TIMESTAMP | | Completion timestamp |
| `requirement_results` | TEXT | | JSON array of individual requirement results |
| `metadata` | TEXT | | JSON metadata blob |

---

## exploration_sessions

Deep-dive exploration sessions that traverse bubble connections.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `root_bubble_id` | TEXT | FK -> ideas.id | Starting bubble |
| `root_bubble_title` | TEXT | | Starting bubble title |
| `exploration_query` | TEXT | | User's exploration question |
| `status` | TEXT | | Session status |
| `current_stage` | INTEGER | | Current exploration depth |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `completed_at` | TIMESTAMP | | Completion timestamp |
| `total_nodes_explored` | INTEGER | | Count of nodes visited |
| `best_score` | REAL | | Highest relevance score found |
| `metadata` | TEXT | | JSON metadata blob |

---

## exploration_nodes

Individual steps within an exploration session.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `session_id` | TEXT | FK -> exploration_sessions.id | Parent session |
| `step` | INTEGER | | Step number in sequence |
| `parent_node_id` | TEXT | FK -> exploration_nodes.id | Parent step |
| `source_bubble_id` | TEXT | | Source bubble ID |
| `source_bubble_title` | TEXT | | Source bubble title |
| `target_bubble_id` | TEXT | | Target bubble ID |
| `target_bubble_title` | TEXT | | Target bubble title |
| `connection_type` | TEXT | | How the connection was found |
| `reasoning` | TEXT | | LLM reasoning for this step |
| `edge_label` | TEXT | | Descriptive edge label |
| `embedding_similarity` | REAL | | Cosine similarity score |
| `llm_confidence` | REAL | | LLM confidence score |
| `combined_score` | REAL | | Weighted combined score |
| `exploration_depth` | INTEGER | | Depth from root |
| `is_accepted` | INTEGER | | Whether user accepted this path |
| `is_rejected` | INTEGER | | Whether user rejected this path |
| `is_valid` | INTEGER | | Whether connection is valid |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `metadata` | TEXT | | JSON metadata blob |

---

## discovered_edges

Edges discovered during exploration sessions, stored permanently.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `from_idea_id` | TEXT | FK -> ideas.id | Source idea |
| `to_idea_id` | TEXT | FK -> ideas.id | Target idea |
| `edge_type` | TEXT | | Relationship type |
| `edge_label` | TEXT | | Descriptive label |
| `reasoning` | TEXT | | Why this connection exists |
| `confidence` | REAL | | Confidence score |
| `connection_type` | TEXT | | Discovery method |
| `exploration_session_id` | TEXT | | Session that found this edge |
| `exploration_node_id` | TEXT | | Specific exploration step |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `metadata` | TEXT | | JSON metadata blob |

**Constraint**: `UNIQUE(from_idea_id, to_idea_id)` -- no duplicate edges between the same pair.

---

## mermaid_diagrams

Generated Mermaid diagram source stored for re-rendering.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `title` | TEXT | | Diagram title |
| `diagram_type` | TEXT | | Mermaid diagram type (flowchart, sequence, etc.) |
| `content` | TEXT | | Raw Mermaid source code |
| `source_idea_id` | TEXT | FK -> ideas.id | Originating idea |
| `source_shuttle_id` | TEXT | FK -> shuttles.id | Originating shuttle |
| `source_requirement_ids` | TEXT | | JSON array of requirement IDs |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `updated_at` | TIMESTAMP | | Last update timestamp |
| `version` | INTEGER | | Diagram version number |
| `metadata` | TEXT | | JSON metadata blob |

---

## scheduled_tasks

Recurring or one-shot tasks managed by the Schedule Space.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | TEXT | PRIMARY KEY | UUID |
| `title` | TEXT | | Task display name |
| `description` | TEXT | | What the task does |
| `action_text` | TEXT | | Natural language action to execute |
| `execution_mode` | TEXT | | How to execute (voice, direct, api) |
| `trigger_type` | TEXT | | Trigger kind (cron, interval, one_shot) |
| `trigger_config` | TEXT | | JSON trigger configuration |
| `timezone` | TEXT | | IANA timezone for scheduling |
| `status` | TEXT | | Task status (active, paused, completed, failed) |
| `next_run_at` | TIMESTAMP | | Next scheduled execution |
| `last_run_at` | TIMESTAMP | | Last execution timestamp |
| `run_count` | INTEGER | | Total executions |
| `max_runs` | INTEGER | | Maximum allowed runs (NULL = unlimited) |
| `last_result` | TEXT | | Result of last execution |
| `last_error` | TEXT | | Error from last execution |
| `created_at` | TIMESTAMP | | Creation timestamp |
| `updated_at` | TIMESTAMP | | Last update timestamp |
| `metadata` | TEXT | | JSON metadata blob |
