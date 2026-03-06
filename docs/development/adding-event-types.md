# Adding Event Types

Event types are the bridge between voice commands and tool execution. This guide shows how to add a new one.

## The 4 Places to Update

1. **Classifier prompt** — so the LLM knows about it
2. **Tool function** — the code that executes
3. **Backend agent TOOL_MAP** — maps event type to tool
4. **Backend agent PARAM_MAPPING** — normalizes parameter names

## Step-by-Step

### 1. Add to Classifier Prompt

Edit `python/swarm/orchestrator/intent_classifier.py` and add your event type to the `CLASSIFIER_PROMPT_TEMPLATE`:

```python
CLASSIFIER_PROMPT_TEMPLATE = """
...
## Bubble Events
bubble.create {title}           – "Erstelle Bubble Marketing"
bubble.enter {bubble_name}      – "Geh in Marketing"
bubble.rename {bubble_name, new_name}  – "Benenne Marketing um in Sales"   # NEW
...
"""
```

Include:
- Event type name with parameters
- At least one example utterance (German preferred, English also good)
- Parameter names that match what the LLM should extract

### 2. Add Tool Function

See [Adding a Tool](adding-a-tool.md).

### 3. Register in TOOL_MAP

In the relevant backend agent (e.g., `python/spaces/ideas/agents/ideas_agent.py`):

```python
EVENT_TO_TOOL = {
    ...
    "bubble.rename": "rename_bubble",
}
```

### 4. Add PARAM_MAPPING (if needed)

If the classifier extracts params with different names than the tool expects:

```python
PARAM_MAPPING = {
    ...
    "bubble.rename": {
        "title": "bubble_name",   # classifier says "title", tool wants "bubble_name"
        "name": "new_name",
    },
}
```

## Naming Conventions

- Event types use dot notation: `domain.action` or `domain.sub_action`
- Domains: `bubble`, `idea`, `code`, `desktop`, `messaging`, `web`, `research`, `schedule`, `shuttle`
- Actions: lowercase, underscored for multi-word (`auto_link`, `open_app`)

## Testing

Add test cases to `python/tests/intent_test_cases.py`:

```python
{
    "input": "Benenne Marketing um in Sales",
    "expected_event_type": "bubble.rename",
    "expected_params": {"bubble_name": "Marketing", "new_name": "Sales"}
}
```

Run: `python -m tests.test_intent_to_tool`
