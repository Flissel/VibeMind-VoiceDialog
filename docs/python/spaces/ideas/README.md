# Ideas Space

The Ideas space handles bubble management and idea CRUD operations. It is the largest space in VibeMind and includes two backend agents (BubblesAgent and IdeasAgent), an explorer subsystem for deep idea analysis, and a swarm agent for multi-step workflows.

## Directory Structure

```
python/spaces/ideas/
├── __init__.py
├── README.md
├── adapted/                    # Adapted tool wrappers
│   ├── __init__.py
│   ├── bubble_tools.py         # Bubble tool adaptations
│   └── idea_tools.py           # Idea tool adaptations
├── agents/                     # Backend agents
│   ├── __init__.py
│   ├── bubbles_agent.py        # BubblesAgent (bubble.* events)
│   ├── ideas_agent.py          # IdeasAgent (idea.* events)
│   ├── ideas_swarm_agent.py    # IdeasSwarmAgent (multi-step orchestration)
│   └── rachel_agent.py         # RachelAgent (voice entry point)
├── broadcast/                  # Broadcast profiling
│   ├── __init__.py
│   └── ideas_broadcast_agent.py
├── explorer/                   # Explorer subsystem
│   ├── __init__.py
│   ├── connection_evaluator.py # Evaluates semantic connections between ideas
│   ├── exploration_clarification.py # Handles clarification dialogs
│   ├── exploration_repository.py    # Persistence for exploration sessions
│   ├── idea_journal.py         # Idea journaling and evolution tracking
│   ├── idea_node.py            # Node representation for idea graphs
│   └── idea_tree_search.py     # Tree search across idea hierarchies
├── sub_agents/                 # Sub-agents for complex workflows
│   ├── __init__.py
│   └── ideas_sub_agents.py
├── swarm/                      # Swarm orchestration
│   ├── __init__.py
│   └── ideas_swarm.py
├── tools/                      # Tool implementations
│   ├── __init__.py
│   ├── autogen_research.py     # Auto-generated research content
│   ├── bubble_tools.py         # Bubble CRUD (create, enter, list, delete, etc.)
│   ├── exploration_tools.py    # Deep exploration tools
│   ├── format_dispatcher.py    # Routes formatting requests
│   ├── idea_tools.py           # Idea CRUD (create, update, link, etc.)
│   ├── structured_formatting_tools.py # Structured content formatting
│   └── summary_tools.py        # LLM-powered summarization
└── workers/                    # Background workers
    ├── __init__.py
    └── ideas_workers.py
```

## Agents

### BubblesAgent (`agents/bubbles_agent.py`)

Handles all `bubble.*` events (14 event types):

- `bubble.create` -- Create a new bubble
- `bubble.enter` -- Navigate into a bubble
- `bubble.exit` -- Navigate back to parent
- `bubble.list` -- List all bubbles
- `bubble.delete` -- Delete a bubble
- `bubble.evaluate` -- Evaluate bubble via shuttle pipeline
- `bubble.promote` -- Promote bubble through stages
- And more

Stream: `events:tasks:bubbles`

### IdeasAgent (`agents/ideas_agent.py`)

Handles all `idea.*` events (33 event types):

- `idea.create` -- Create a new idea
- `idea.list` -- List ideas in current bubble
- `idea.update` -- Update idea content
- `idea.delete` -- Delete an idea
- `idea.auto_link` -- Automatically link related ideas
- `idea.format` -- Format idea content
- `idea.explore` -- Deep exploration of an idea
- And many more

Stream: `events:tasks:ideas`

### RachelAgent (`agents/rachel_agent.py`)

The voice entry point agent. Receives raw voice input from the OpenAI Realtime API and routes it into the intent classification pipeline.

### IdeasSwarmAgent (`agents/ideas_swarm_agent.py`)

Orchestrates multi-step idea workflows (e.g., "create a bubble, add three ideas, and link them together").

## Explorer Subsystem

The explorer is a dedicated subsystem for deep idea analysis:

- **`idea_tree_search.py`** -- Traverses the idea hierarchy using tree search algorithms
- **`connection_evaluator.py`** -- Uses LLM to evaluate semantic connections between ideas
- **`exploration_clarification.py`** -- Manages clarification dialogs when exploration is ambiguous
- **`exploration_repository.py`** -- Persists exploration sessions and results
- **`idea_journal.py`** -- Tracks how ideas evolve over time
- **`idea_node.py`** -- Graph node representation for idea networks

## Tools

| Tool File | Key Functions | Purpose |
|-----------|---------------|---------|
| `bubble_tools.py` | `create_bubble`, `enter_bubble`, `list_bubbles`, `delete_bubble` | Bubble CRUD operations |
| `idea_tools.py` | `create_idea_tool`, `auto_link_ideas`, `update_idea`, `delete_idea` | Idea CRUD operations |
| `exploration_tools.py` | `explore_idea`, `explore_connections` | Deep idea exploration |
| `summary_tools.py` | `summarize_bubble`, `summarize_idea` | LLM-powered summaries |
| `structured_formatting_tools.py` | `format_idea_content` | Convert ideas to structured formats |
| `format_dispatcher.py` | `dispatch_format` | Route formatting requests to handlers |
| `autogen_research.py` | `auto_research` | Auto-generate research content |

## Workers

`ideas_workers.py` -- Background processing for idea operations (e.g., batch linking, periodic summaries).

## Broadcast

`ideas_broadcast_agent.py` -- Profiles and broadcasts idea events to the Electron UI, sending `node_added`, `node_removed`, `edge_added`, and `node_structured_update` messages.
