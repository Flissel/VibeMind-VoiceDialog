# N8n Space

Workflow automation space that generates, manages, and executes n8n workflows via voice commands.

## Architecture

```
User: "Erstelle einen Workflow fuer X"
  -> IntentClassifier -> n8n.generate
    -> N8nBackendAgent (events:tasks:n8n)
      -> workflow_generator.py (LLM generates workflow JSON)
        -> n8n_api_client.py (pushes to n8n instance)
          -> Electron broadcast (workflow_created)
```

## Backend Agent

- **Class:** `N8nBackendAgent` in `python/spaces/n8n/agents/n8n_agent.py`
- **Stream:** `events:tasks:n8n`
- **Event Prefix:** `n8n.*`

## Tools

| Tool | File | Description |
|------|------|-------------|
| `generate_workflow` | `tools/n8n_workflow_tools.py` | Generate workflow from natural language |
| `list_workflows` | `tools/n8n_workflow_tools.py` | List all workflows |
| `get_n8n_status` | `tools/n8n_workflow_tools.py` | Check n8n instance health |
| `activate_workflow` | `tools/n8n_workflow_tools.py` | Activate a workflow |
| `deactivate_workflow` | `tools/n8n_workflow_tools.py` | Deactivate a workflow |
| `delete_workflow` | `tools/n8n_workflow_tools.py` | Delete a workflow |
| `execute_workflow` | `tools/n8n_workflow_tools.py` | Execute workflow manually |
| `describe_workflow` | `tools/n8n_workflow_tools.py` | Show workflow details |

## Event Types

| Event | Parameters | Description |
|-------|-----------|-------------|
| `n8n.generate` | `{description}` | Generate workflow from natural language |
| `n8n.list` | -- | List all workflows |
| `n8n.status` | -- | Get n8n instance health status |
| `n8n.activate` | `{name}` | Activate a workflow |
| `n8n.deactivate` | `{name}` | Deactivate a workflow |
| `n8n.delete` | `{name}` | Delete a workflow |
| `n8n.execute` | `{name}` | Execute a workflow manually |
| `n8n.describe` | `{name}` | Show workflow details |

## Supporting Modules

| Module | File | Purpose |
|--------|------|---------|
| API Client | `tools/n8n_api_client.py` | REST API wrapper for n8n v1 |
| Workflow Generator | `tools/workflow_generator.py` | LLM-based workflow JSON generation |
