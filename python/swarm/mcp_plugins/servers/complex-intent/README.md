# Complex Intent Processing MCP Plugin

## Overview

This MCP plugin provides advanced complex intent processing using the **Society of Mind pattern**. It specializes in breaking down and executing complex user requests that involve multiple steps and tools.

## Key Features

- **Multi-Agent Team**: IntentAnalyzer → WorkflowAgent → QAValidator
- **Complex Request Handling**: Processes requests like "formatiere die Ideen zu Tabellenansicht mit Fokus auf Futures und Content"
- **Society of Mind Architecture**: Event-driven, session-based processing
- **Quality Assurance**: Built-in validation and error checking

## Architecture

### Agent Team

1. **IntentAnalyzer**: Breaks down complex requests into actionable steps
2. **WorkflowAgent**: Executes sequences of tool calls using Swarm tools
3. **QAValidator**: Validates results and ensures completeness

### Workflow Example

```
User: "formatiere die Ideen zu Tabellenansicht mit Fokus auf Futures und Content"

IntentAnalyzer:
- Identifies: format + filter operation
- Extracts: "Futures", "Content", "Tabellenansicht"
- Plans: list_ideas → filter → format_table

WorkflowAgent:
- Executes: list_ideas() → filter results → format as table

QAValidator:
- Verifies: All requirements met, results complete
```

## Usage

```bash
# Run the complex intent processor
python agent.py --session-id "session123" --task "formatiere die Ideen zu Tabellenansicht mit Fokus auf Futures und Content"
```

## Integration

This plugin integrates with the VibeMind Swarm system via:
- **SESSION_ANNOUNCE**: Announces session to main system
- **Event Broadcasting**: Real-time status updates
- **Swarm Tools**: Uses adapted_bubble_tools and adapted_idea_tools

## Dependencies

- AutoGen AgentChat
- Swarm Tools (adapted_bubble_tools, adapted_idea_tools)
- EventServer (shared)
- ConversationLogger (shared)

## Configuration

Configure via environment variables:
- `OPENROUTER_API_KEY`: For LLM access
- Model selection via `--model` parameter
- Session management via `--session-id`

## Society of Mind Benefits

- **Separation of Concerns**: Each agent has a specific role
- **Quality Assurance**: Built-in validation prevents errors
- **Scalability**: Easy to add new agents for specific tasks
- **Robustness**: Fallback mechanisms and error recovery
- **Observability**: Full conversation logging for ML training