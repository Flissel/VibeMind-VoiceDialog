# Spaces

VibeMind has 10 domain spaces. Each space is a self-contained module in `python/spaces/` with its own agents, tools, workers, and broadcast agents.

## Space Directory

| Space | Directory | Backend Agent | Stream | Events |
|-------|-----------|---------------|--------|--------|
| Bubbles | `ideas/` | BubblesAgent | `events:tasks:bubbles` | 14 bubble.* events |
| Ideas | `ideas/` | IdeasAgent | `events:tasks:ideas` | 33 idea.* events |
| Coding | `coding/` | CodingAgent | `events:tasks:coding` | 9 code.* events |
| Desktop | `desktop/` | DesktopAgent | `events:tasks:desktop` | 19 desktop.*/messaging.*/web.* events |
| Rowboat | `rowboat/` | RoarbootBackendAgent | `events:tasks:roarboot` | 13 roarboot.* events |
| Research | `research/` | ZeroClawResearchAgent | `events:tasks:zeroclaw` | 5 research.* events |
| Minibook | `minibook/` | MinibookBackendAgent | `events:tasks:minibook` | 6 minibook.* events |
| Schedule | `schedule/` | ScheduleBackendAgent | `events:tasks:schedule` | 6 schedule.* events |
| N8n | `n8n/` | N8nBackendAgent | `events:tasks:n8n` | 8 n8n.* events |

> **Note:** Shuttles (`python/spaces/shuttles/`) contains only the SWE Design submodule -- no dedicated agent or tools.
> **Note:** Brain (`python/spaces/brain/`) contains the Tahlamus submodule -- a standalone neuroscience-inspired cognitive system with its own microservices (ports 5000–5002), not a traditional backend agent.

| Brain | `brain/` | — (standalone) | — | Tahlamus cognitive routing (submodule) |

## Space Internal Structure

Each space follows a consistent layout:

```
python/spaces/<space>/
├── __init__.py
├── agents/            # Backend agent(s) for this space
├── tools/             # Space-specific tool implementations
├── workers/           # Background workers (optional)
├── broadcast/         # Broadcast profiling agent (optional)
├── sub_agents/        # Sub-agents for complex workflows (optional)
├── config.py          # Space configuration (optional)
└── <submodule>/       # Git submodule (if applicable)
```

## How Spaces Integrate

1. **Intent Classification** -- The `IntentClassifier` maps user input to an `event_type` (e.g., `bubble.create`, `code.generate`).
2. **Event Routing** -- The `EventRouter` inspects the event prefix and dispatches to the correct stream.
3. **Backend Agent** -- The space's agent picks up the event, maps it via `TOOL_MAP`, normalizes parameters via `PARAM_MAPPING`, and executes the tool function.
4. **Broadcast** -- Tool results are broadcast to the Electron UI via `_broadcast_to_electron()`.

## Shared Dependencies

All spaces import from the top-level `python/` packages:

- `data/` -- Repository pattern for SQLite access (`IdeasRepository`, `CanvasRepository`, etc.)
- `swarm/backend_agents/base_agent.py` -- `BaseBackendAgent` base class
- `swarm/event_bus.py` -- Event publishing and subscription
- `tools/` -- Legacy tool modules (spaces may re-export or adapt these)

## Adding a New Space

1. Create `python/spaces/<name>/` with the standard layout above.
2. Implement a backend agent subclassing `BaseBackendAgent`.
3. Define `TOOL_MAP` and `PARAM_MAPPING` in the agent.
4. Add tool functions in the `tools/` subdirectory.
5. Register the stream prefix in `python/swarm/event_team/event_router.py`.
6. Add new event types to `CLASSIFIER_PROMPT_TEMPLATE` in `intent_classifier.py`.
