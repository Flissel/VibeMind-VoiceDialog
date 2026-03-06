# Research Space

The Research space provides deep research capabilities via the ZeroClaw research agent. It is a lightweight space with a single agent and tool file, backed by the external `zeroclaw` submodule.

## Directory Structure

```
python/spaces/research/
├── __init__.py
├── agents/                     # Backend agents
│   ├── __init__.py
│   └── zeroclaw_research_agent.py  # ZeroClawResearchAgent (research.* events)
└── tools/                      # Tool implementations
    ├── __init__.py
    └── research_tools.py       # Research tool functions
```

> **Note:** This space has no workers, broadcast agents, or sub_agents directories. It is the most minimal space in VibeMind.

## Agent

### ZeroClawResearchAgent (`agents/zeroclaw_research_agent.py`)

Handles all `research.*` events (5 event types):

- `research.start` -- Start a research session
- `research.query` -- Submit a research query
- `research.status` -- Check research progress
- `research.results` -- Retrieve research results
- `research.stop` -- Stop an active research session

Stream: `events:tasks:zeroclaw`

## Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `research_tools.py` | `start_research`, `query_research`, `get_research_results` | Core research operations |

## Submodule

The zeroclaw submodule provides the research engine:

- **Path:** `external/zeroclaw/`
- **Upstream:** https://github.com/zeroclaw-labs/zeroclaw.git
- **Status:** EMPTY -- needs initialization

> **Important:** The zeroclaw submodule directory exists but is empty. You must initialize it before the Research space can function:
>
> ```bash
> git submodule update --init external/zeroclaw
> ```

See [docs/submodules/zeroclaw.md](../../submodules/zeroclaw.md) for details.

## Configuration

Enable the Research space via `.env`:

```bash
USE_ZEROCLAW=true
```

When `USE_ZEROCLAW` is not set or is `false`, the Research space is inactive and research events will not be processed.
