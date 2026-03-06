# Adding a Tool

This guide walks through adding a new tool to an existing space.

## Example: Adding a `rename_bubble` Tool

### Step 1: Write the Tool Function

Create or edit a file in `python/spaces/ideas/tools/` (or `python/tools/` for shared tools):

```python
# python/spaces/ideas/tools/bubble_tools.py

def rename_bubble(bubble_id: str = None, bubble_name: str = None, new_name: str = "") -> Dict[str, Any]:
    """Rename an existing bubble.

    Args:
        bubble_id: UUID of the bubble (optional if bubble_name given)
        bubble_name: Current name of the bubble (fuzzy matched)
        new_name: New name for the bubble

    Returns:
        Dict with success, message, and updated bubble data
    """
    repo = IdeasRepository()

    # Resolve bubble
    if bubble_name:
        bubble = repo.get_by_title_fuzzy(bubble_name)
    elif bubble_id:
        bubble = repo.get_by_id(bubble_id)
    else:
        return {"success": False, "message": "No bubble specified"}

    if not bubble:
        return {"success": False, "message": f"Bubble '{bubble_name or bubble_id}' not found"}

    # Update
    repo.update(bubble.id, title=new_name)

    # Broadcast to Electron UI
    _broadcast_to_electron({
        "type": "node_updated",
        "node": {"id": bubble.id, "title": new_name}
    })

    return {"success": True, "message": f"Bubble renamed to '{new_name}'"}
```

### Step 2: Add Event Type to Classifier

Edit `python/swarm/orchestrator/intent_classifier.py` — add to `CLASSIFIER_PROMPT_TEMPLATE`:

```
bubble.rename {bubble_name, new_name}  – "Benenne Bubble Marketing um in Sales"
```

### Step 3: Register in Backend Agent

Edit `python/spaces/ideas/agents/ideas_agent.py`:

```python
# In EVENT_TO_TOOL:
"bubble.rename": "rename_bubble",

# In PARAM_MAPPING:
"bubble.rename": {
    "title": "bubble_name",
    "name": "new_name",
},
```

### Step 4: Load the Tool

In the agent's `_load_tools()` method, ensure the function is imported:

```python
from spaces.ideas.tools.bubble_tools import rename_bubble

def _load_tools(self):
    tools = super()._load_tools()
    tools["rename_bubble"] = rename_bubble
    return tools
```

### Step 5: Test

```bash
cd python
python -m tests.test_intent_to_tool
```

Or test manually via voice: "Benenne die Bubble Marketing um in Sales"

## Tool Return Format

All tools must return a dict:

```python
{
    "success": True,           # Required
    "message": "Human-readable result",  # Required
    "data": {...},             # Optional — extra data
    "response_hint": "..."    # Optional — suggested voice response
}
```

## Broadcasting to UI

Call `_broadcast_to_electron()` for any change that should appear in the 3D UI:

```python
_broadcast_to_electron({"type": "node_added", "node": {...}})
_broadcast_to_electron({"type": "node_removed", "node_id": "..."})
_broadcast_to_electron({"type": "edge_added", "edge": {...}})
```
