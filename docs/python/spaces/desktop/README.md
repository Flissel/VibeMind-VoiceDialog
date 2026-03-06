# Desktop Space

The Desktop space handles system automation, application control, messaging, and web interactions. It integrates with the Automation_ui submodule for UI automation capabilities.

## Directory Structure

```
python/spaces/desktop/
├── __init__.py
├── Automation_ui/              # Git submodule (UI automation framework)
├── adapted/                    # Adapted tool wrappers
│   ├── __init__.py
│   ├── desktop_tools.py        # Desktop tool adaptations
│   └── messaging_tools.py      # Messaging tool adaptations
├── agents/                     # Backend agents
│   ├── __init__.py
│   ├── desktop_agent.py        # DesktopAgent (desktop.*/messaging.*/web.* events)
│   └── desktop_swarm_agent.py  # DesktopSwarmAgent (multi-step orchestration)
├── automation_ui_client.py     # Client interface to Automation_ui submodule
├── broadcast/                  # Broadcast profiling
│   ├── __init__.py
│   └── desktop_broadcast_agent.py
├── sub_agents/                 # Sub-agents for complex workflows
│   ├── __init__.py
│   └── desktop_sub_agents.py
├── tools/                      # Tool implementations
│   ├── __init__.py
│   ├── adapted_desktop_tools.py # Adapted desktop tool wrappers
│   ├── desktop_tools.py        # Core desktop automation tools
│   ├── moire_tools.py          # Moire pattern / visual tools
│   ├── quickaction_tools.py    # Quick action shortcuts
│   └── task_tools.py           # Task management tools
└── workers/                    # Background workers
    ├── __init__.py
    └── desktop_workers.py
```

## Agents

### DesktopAgent (`agents/desktop_agent.py`)

Handles `desktop.*`, `messaging.*`, and `web.*` events (19 event types total):

**Desktop events:**
- `desktop.open_app` -- Open an application
- `desktop.click` -- Click on a UI element
- `desktop.type_text` -- Type text
- `desktop.screenshot` -- Take a screenshot
- `desktop.scroll` -- Scroll in a direction
- And more

**Messaging events:**
- `messaging.send` -- Send a message
- `messaging.read` -- Read messages

**Web events:**
- `web.open` -- Open a URL
- `web.search` -- Perform a web search

Stream: `events:tasks:desktop`

### DesktopSwarmAgent (`agents/desktop_swarm_agent.py`)

Orchestrates multi-step desktop workflows (e.g., "open Chrome, navigate to a URL, and take a screenshot").

## Automation UI Client

`automation_ui_client.py` -- The bridge between VibeMind and the Automation_ui submodule. Provides a Python client interface to the UI automation framework for:

- Application launching and management
- UI element detection and interaction
- Screen capture and analysis
- Keyboard and mouse automation

## Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `desktop_tools.py` | `open_app`, `click`, `type_text`, `screenshot` | Core desktop automation |
| `adapted_desktop_tools.py` | Adapted wrappers | Adapts tool signatures for the backend agent pattern |
| `moire_tools.py` | Visual/pattern tools | Moire pattern and visual analysis tools |
| `quickaction_tools.py` | Quick shortcuts | Pre-defined action shortcuts for common tasks |
| `task_tools.py` | Task management | System task tracking and management |

### Adapted Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `adapted/desktop_tools.py` | Desktop adaptations | Wrapper layer for desktop tools |
| `adapted/messaging_tools.py` | Messaging adaptations | Wrapper layer for messaging tools |

## Workers

`desktop_workers.py` -- Background processing for desktop automation tasks, screenshot monitoring, and application state tracking.

## Broadcast

`desktop_broadcast_agent.py` -- Broadcasts desktop events to the Electron UI, including screenshot results and application state changes.

## Submodule

The Automation_ui submodule provides the UI automation framework:

- **Path:** `python/spaces/desktop/Automation_ui/`
- **Upstream:** https://github.com/Flissel/Automation_ui.git
- **Initialize:** `git submodule update --init python/spaces/desktop/Automation_ui`

See [docs/submodules/automation-ui.md](../../submodules/automation-ui.md) for details.
