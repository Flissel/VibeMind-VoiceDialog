# Roarboot (Docker Data)

This directory contains **Docker Compose volume data** for the Rowboat knowledge graph stack. It is **not** a VibeMind space with agents or tools.

## What's Here

```
roarboot/
└── rowboat/
    └── data/
        ├── mongo/     # MongoDB data files (WiredTiger)
        └── qdrant/    # Qdrant vector search data
```

## Actual Rowboat Space

The agent code, tools, and README are in **`python/spaces/rowboat/`**:

| Component | Location |
|-----------|----------|
| Agent | `python/spaces/rowboat/agents/roarboot_agent.py` |
| Tools | `python/spaces/rowboat/tools/roarboot_tools.py` |
| Client | `python/spaces/rowboat/roarboot_client.py` |
| Docker Compose | `python/spaces/rowboat/docker-compose.yml` |
| README | `python/spaces/rowboat/README.md` |

## Naming History

"Roarboot" is an internal codename that persists in class names (`RoarbootBackendAgent`), tool files, and stream names (`events:tasks:roarboot`). The official project name is **Rowboat**.

## Docker Services

| Service | Port | Purpose |
|---------|------|---------|
| Rowboat | 3000 | Main application |
| MongoDB | 27017 | Data storage |
| Redis | 6379 | Queuing |
| Qdrant | 6333 | Vector search |
