# Adding a New Space

A space is a self-contained domain with its own agent, tools, and event types. This guide walks through creating one from scratch.

## Directory Structure

```
python/spaces/myspace/
├── __init__.py
├── README.md
├── agents/
│   ├── __init__.py
│   └── myspace_agent.py
└── tools/
    ├── __init__.py
    └── myspace_tools.py
```

## Step 1: Create the Backend Agent

```python
# python/spaces/myspace/agents/myspace_agent.py

from swarm.backend_agents.base_agent import BaseBackendAgent
from swarm.event_bus import EventBus

class MySpaceAgent(BaseBackendAgent):

    @property
    def stream(self) -> str:
        return "events:tasks:myspace"

    @property
    def name(self) -> str:
        return "MySpaceAgent"

    EVENT_TO_TOOL = {
        "myspace.action_one": "do_action_one",
        "myspace.action_two": "do_action_two",
    }

    PARAM_MAPPING = {
        "myspace.action_one": {
            "name": "item_name",
        },
    }

    def _load_tools(self):
        from spaces.myspace.tools.myspace_tools import do_action_one, do_action_two
        return {
            "do_action_one": do_action_one,
            "do_action_two": do_action_two,
        }

    def _get_tool_name(self, event_type: str):
        return self.EVENT_TO_TOOL.get(event_type)
```

## Step 2: Create Tool Functions

```python
# python/spaces/myspace/tools/myspace_tools.py

from typing import Dict, Any

def do_action_one(item_name: str = "") -> Dict[str, Any]:
    """Execute action one."""
    # Your logic here
    return {"success": True, "message": f"Did action one on '{item_name}'"}

def do_action_two() -> Dict[str, Any]:
    """Execute action two."""
    return {"success": True, "message": "Action two complete"}
```

## Step 3: Add Event Routing

Edit `python/swarm/event_team/event_router.py`:

```python
STREAM_TASKS_MYSPACE = "events:tasks:myspace"

def get_stream(event_type: str) -> str:
    if event_type.startswith("myspace."):
        return STREAM_TASKS_MYSPACE
    # ... existing routing
```

## Step 4: Add to Intent Classifier

Edit `python/swarm/orchestrator/intent_classifier.py`:

```python
CLASSIFIER_PROMPT_TEMPLATE = """
...
## MySpace Events
myspace.action_one {item_name}  – "Do action one on X"
myspace.action_two              – "Do action two"
...
"""
```

## Step 5: Write a README

Create `python/spaces/myspace/README.md` documenting the space's purpose, event types, and tools.

## Step 6: Test

```python
# python/tests/test_myspace.py
def test_action_one():
    from spaces.myspace.tools.myspace_tools import do_action_one
    result = do_action_one(item_name="test")
    assert result["success"] is True
```

## Optional: Enable via Config

Add a feature flag in `.env`:

```bash
USE_MYSPACE=true
```

Check it in the agent or router:

```python
import os
if os.getenv("USE_MYSPACE", "false").lower() == "true":
    # Register agent
```
