# Data Layer

The `python/data/` package provides SQLite persistence for VibeMind. It uses the repository pattern with dataclass models, WAL mode for concurrent access, and automatic schema migrations.

## File Index

| File | Purpose |
|------|---------|
| `database.py` | SQLite connection manager, schema v14, WAL mode, migration system |
| `models.py` | Dataclasses for all entities (Idea, Project, CanvasNode, Shuttle, ScheduledTask, etc.) |
| `repository.py` | CRUD repositories with fuzzy/accent-insensitive search |
| `embedding_service.py` | Semantic embeddings via sentence-transformers (all-MiniLM-L6-v2, 384 dimensions) |
| `format_schemas.py` | JSON schema definitions for structured idea content (note, action_list, mind_map, etc.) |
| `intent_rule_repository.py` | Intent classification rules stored in Supermemory for embedding-based lookup |
| `task_memory_repository.py` | Persistent task storage (ongoing work Rachel remembers across sessions) |
| `conversion_ai_repository.py` | AI personality storage and user preference tracking |
| `__init__.py` | Package init -- re-exports all repositories, models, and singletons |

## database.py

Central database manager. Key characteristics:

- **Schema version**: 14 (auto-migrates on startup)
- **WAL mode**: Enabled for better concurrent read performance
- **Singleton**: `get_database()` returns a shared instance
- **Location**: `python/vibemind.db` (auto-created)
- **12 tables**: See [schema.md](schema.md) for the complete schema reference

## models.py

Python dataclasses representing each table. Notable models:

- `Idea` -- Bubbles and ideas (parent_id creates hierarchy)
- `Project` -- Code generation projects with status tracking
- `CanvasNode` / `CanvasEdge` -- Visual graph elements
- `ConversationSession` / `ConversationMessage` -- Chat history
- `Shuttle` -- Requirements pipeline stages
- `ScheduledTask` -- Cron/interval/one-shot scheduled actions
- `GenerationStatus` -- Enum-like class for project generation states
- `ShuttleStatus` / `ShuttleStage` -- Enum-like classes for shuttle lifecycle

## repository.py

Repository classes providing CRUD operations:

| Repository | Table | Key Features |
|------------|-------|--------------|
| `IdeasRepository` | `ideas` | Fuzzy title search (`get_by_title_fuzzy`), accent-insensitive matching, parent hierarchy |
| `ProjectsRepository` | `projects` | Generation status tracking, VNC port management |
| `CanvasRepository` | `canvas_nodes`, `canvas_edges` | Node/edge CRUD, linked idea/project resolution |
| `ConversationRepository` | `conversation_sessions`, `conversation_history` | Session lifecycle, message storage |
| `ShuttlesRepository` | `shuttles` | Stage progression, requirement result tracking |
| `ScheduledTaskRepository` | `scheduled_tasks` | Trigger config, run history, next-run calculation |

Helper function: `promote_idea_to_project()` -- converts an idea into a project record.

## embedding_service.py

Provides semantic search capabilities:

- Model: `all-MiniLM-L6-v2` (384 dimensions, fast, multilingual-capable)
- Caches embeddings in the `embedding_vector` and `embedding_hash` columns of the `ideas` table
- Used by exploration tools and auto-linking to find semantically related ideas

## format_schemas.py

JSON schema definitions that constrain LLM-generated structured content stored in `content_json`:

- `NOTE_SCHEMA` -- Default free-text note
- `ACTION_LIST_SCHEMA` -- Checklist with items and status
- `MIND_MAP_SCHEMA` -- Hierarchical node tree
- Additional schemas for tables, timelines, and custom formats

## intent_rule_repository.py

Stores intent classification rules in Supermemory for embedding-based similarity search. Architecture: `User Input -> Supermemory Search -> Top-K Rules -> LLM + Rules -> Intent`. Replaces hardcoded keyword matching with semantic lookup.

## task_memory_repository.py

Database operations for persistent tasks that Rachel remembers across sessions. Stores task status, progress, and history for voice-queryable task tracking.

## conversion_ai_repository.py

Stores AI personalities (name, style, traits), user preferences (learned over time), and intent analysis logs for the Conversion AI system.
