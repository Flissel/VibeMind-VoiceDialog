# Minibook Space

The Minibook space provides document collaboration and content enrichment capabilities. It includes a central execution hub (MinibookHub), an enrichment pipeline, and integration with the external minibook submodule.

## Directory Structure

```
python/spaces/minibook/
├── __init__.py
├── README.md
├── config.py                   # MINIBOOK_* configuration settings
├── minibook_hub.py             # Central execution router (MinibookHub)
├── rachel_interface.py         # Rachel voice agent prompt metadata
├── result_aggregator.py        # Aggregates results from multiple sources
├── agents/                     # Backend agents
│   ├── __init__.py
│   └── minibook_agent.py       # MinibookBackendAgent (minibook.* events)
├── broadcast/                  # Broadcast profiling (placeholder)
│   └── __init__.py
├── enrichment/                 # Enrichment pipeline
│   ├── __init__.py
│   ├── context_gather.py       # Gathers context from other spaces
│   ├── pipeline.py             # Main enrichment pipeline orchestrator
│   ├── space_router.py         # Routes enrichment tasks to spaces
│   └── task_enricher.py        # Enriches tasks with additional context
├── tools/                      # Tool implementations
│   ├── __init__.py
│   ├── collaboration_tools.py  # Multi-user collaboration tools
│   ├── minibook_client.py      # HTTP client for Minibook API
│   └── minibook_tools.py       # Core Minibook tools
└── workers/                    # Background workers
    ├── __init__.py
    └── minibook_workers.py
```

## Agent

### MinibookBackendAgent (`agents/minibook_agent.py`)

Handles all `minibook.*` events (6 event types):

- `minibook.create` -- Create a new minibook document
- `minibook.edit` -- Edit document content
- `minibook.list` -- List all documents
- `minibook.share` -- Share a document
- `minibook.export` -- Export a document
- `minibook.collaborate` -- Start a collaboration session

Stream: `events:tasks:minibook`

## MinibookHub (`minibook_hub.py`)

The central execution router for the Minibook space. MinibookHub acts as a coordinator that:

- Receives incoming minibook events
- Routes them to the appropriate tool or enrichment pipeline
- Aggregates results from multiple sources
- Returns unified responses

Enable via `.env`:

```bash
USE_MINIBOOK_HUB=true
```

## Enrichment Pipeline

The enrichment pipeline enhances minibook content with context from other VibeMind spaces:

| File | Purpose |
|------|---------|
| `pipeline.py` | Main pipeline orchestrator -- coordinates the enrichment flow |
| `context_gather.py` | Gathers relevant context from ideas, coding, and other spaces |
| `space_router.py` | Routes enrichment tasks to the appropriate space for processing |
| `task_enricher.py` | Enriches individual tasks with gathered context |

### Pipeline Flow

```
Minibook Event
    → context_gather.py (gather context from spaces)
    → task_enricher.py (enrich with context)
    → space_router.py (route to relevant space if needed)
    → result_aggregator.py (combine results)
    → Response
```

## Rachel Interface

`rachel_interface.py` -- Provides prompt metadata and response formatting for the Rachel voice agent when handling minibook-related requests. Ensures voice responses are natural and concise.

## Result Aggregator

`result_aggregator.py` -- Combines results from multiple enrichment sources into a unified response format.

## Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `minibook_tools.py` | `create_minibook`, `edit_minibook`, `list_minibooks` | Core document operations |
| `minibook_client.py` | `MinibookClient` | HTTP client for the Minibook API |
| `collaboration_tools.py` | `start_collaboration`, `invite_collaborator` | Multi-user collaboration |

## Workers

`minibook_workers.py` -- Background processing for document sync, collaboration events, and enrichment pipeline execution.

## Submodule

The minibook submodule provides the document platform:

- **Path:** `external/minibook/`
- **Upstream:** https://github.com/c4pt0r/minibook.git
- **Initialize:** `git submodule update --init external/minibook`

See [docs/submodules/minibook.md](../../submodules/minibook.md) for details.

## Configuration

`config.py` contains `MINIBOOK_*` settings.

Relevant `.env` settings:

```bash
MINIBOOK_ENABLED=true          # Enable the Minibook space
USE_MINIBOOK_HUB=true          # Enable the MinibookHub central router
```
