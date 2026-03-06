# Testing Guide

## Running Tests

All tests are in `python/tests/`. Run from the `python/` directory:

```bash
cd python

# Individual test suites
python -m tests.test_data_layer          # Database CRUD
python -m tests.test_intent_to_tool      # Intent → event_type → tool routing
python -m tests.test_desktop_tools       # Desktop automation tools
python -m tests.test_integration_e2e     # End-to-end flow
python -m tests.test_advanced_features   # Memory, exploration, etc.
```

## Test Structure

```
python/tests/
├── intent_test_cases.py        # 100+ intent classification test cases
├── test_data_layer.py          # Repository CRUD operations
├── test_intent_to_tool.py      # Classification + routing accuracy
├── test_desktop_tools.py       # Desktop automation (mocked)
├── test_integration_e2e.py     # Full pipeline tests
├── test_advanced_features.py   # Memory, exploration, shuttles
├── test_all_ai_tools.py        # All AI-powered tool tests
└── test_reports/               # Generated test result reports
```

## Writing Tests

### Tool Tests

```python
def test_create_bubble():
    from spaces.ideas.tools.bubble_tools import create_bubble
    result = create_bubble(title="Test Bubble")
    assert result["success"] is True
    assert "Test Bubble" in result["message"]
```

### Intent Classification Tests

Add cases to `intent_test_cases.py`:

```python
TEST_CASES = [
    {
        "input": "Erstelle Bubble Marketing",
        "expected_event_type": "bubble.create",
        "expected_params": {"title": "Marketing"},
    },
    # ... more cases
]
```

### Mocking External Services

For tests that touch OpenAI, Supermemory, or other APIs:

```python
from unittest.mock import patch, MagicMock

@patch('swarm.orchestrator.intent_classifier.openai_client')
def test_classification(mock_client):
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content='{"event_type": "bubble.create"}'))]
    )
    # Test classification logic
```

## Test Reports

Some test suites generate reports in `python/tests/test_reports/`:

```bash
python -m tests.test_intent_to_tool
# Generates: test_reports/intent_tool_report_YYYYMMDD_HHMMSS.md
```

## What to Test for New Features

| Change | What to Test |
|--------|-------------|
| New tool | Tool function returns correct dict, handles edge cases |
| New event type | Classification accuracy, param extraction |
| New space | Agent TOOL_MAP resolution, event routing |
| Database change | Repository CRUD, migration runs cleanly |
| IPC message | Electron receives correct message format |
