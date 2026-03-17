# IPC Message Reference

JSON messages sent between Python backend and Electron frontend via stdin/stdout.

## Python to Electron

### Canvas / Node Messages

#### node_added

Sent when a bubble or idea is created.

```json
{
  "type": "node_added",
  "node": {
    "id": "uuid-string",
    "title": "My Idea",
    "node_type": "idea",
    "x": 100.0,
    "y": 200.0,
    "parent_id": "parent-uuid-or-null",
    "summary": "Optional short summary"
  }
}
```

#### node_removed

```json
{
  "type": "node_removed",
  "node_id": "uuid-string"
}
```

#### node_updated

```json
{
  "type": "node_updated",
  "node": {
    "id": "uuid-string",
    "title": "Updated Title",
    "content": "Updated content"
  }
}
```

#### node_structured_update

Sent when an idea is formatted (action list, kanban, etc.).

```json
{
  "type": "node_structured_update",
  "node_id": "uuid-string",
  "format_schema": {"type": "kanban", "columns": ["Todo", "In Progress", "Done"]},
  "content_json": {"items": []}
}
```

#### edge_added

```json
{
  "type": "edge_added",
  "edge": {
    "from_id": "source-uuid",
    "to_id": "target-uuid",
    "edge_type": "related"
  }
}
```

#### edge_deleted

```json
{
  "type": "edge_deleted",
  "from_id": "source-uuid",
  "to_id": "target-uuid"
}
```

#### canvas_refresh

Full canvas reload (sent after bulk operations).

```json
{
  "type": "canvas_refresh",
  "nodes": [],
  "edges": []
}
```

### Navigation Messages

#### space_changed

Navigate into or out of a bubble.

```json
{
  "type": "space_changed",
  "bubble_id": "uuid-string",
  "bubble_name": "Marketing"
}
```

#### navigate_to_space

Programmatic navigation request.

```json
{
  "type": "navigate_to_space",
  "bubble_id": "uuid-string",
  "bubble_name": "Marketing"
}
```

#### navigate_space

Alternative navigation message (alias).

```json
{
  "type": "navigate_space",
  "space_id": "uuid-string"
}
```

### Agent Transfer Messages

#### agent_transfer_start

Voice agent transfer initiated.

```json
{
  "type": "agent_transfer_start",
  "from_agent": "rachel",
  "to_agent": "alice",
  "reason": "User requested coordinator"
}
```

#### agent_transfer_complete

Voice agent transfer completed successfully.

```json
{
  "type": "agent_transfer_complete",
  "from_agent": "rachel",
  "to_agent": "alice"
}
```

#### agent_transfer_error

Voice agent transfer failed.

```json
{
  "type": "agent_transfer_error",
  "from_agent": "rachel",
  "to_agent": "alice",
  "error": "Agent not available"
}
```

### Code Generation Messages

#### project_created

New code project created.

```json
{
  "type": "project_created",
  "project_id": "uuid",
  "name": "My App",
  "from_idea_id": "idea-uuid-or-null"
}
```

#### project_status_update

Code generation progress.

```json
{
  "type": "project_status_update",
  "project_id": "uuid",
  "status": "generating",
  "progress": 45
}
```

#### project_preview_ready

VNC preview is available.

```json
{
  "type": "project_preview_ready",
  "project_id": "uuid",
  "preview_url": "https://preview.vibemind.io/vnc/...",
  "vnc_port": 5901
}
```

#### project_preview_stopped

VNC preview stopped.

```json
{
  "type": "project_preview_stopped",
  "project_id": "uuid"
}
```

#### generation_started

Code generation job started.

```json
{
  "type": "generation_started",
  "project_id": "uuid",
  "job_id": "job-uuid"
}
```

#### generation_cancelled

Code generation job cancelled.

```json
{
  "type": "generation_cancelled",
  "project_id": "uuid",
  "job_id": "job-uuid"
}
```

### Shuttle Messages

#### shuttle_launched

Requirements evaluation pipeline started.

```json
{
  "type": "shuttle_launched",
  "shuttle_id": "uuid",
  "bubble_id": "uuid",
  "bubble_name": "Marketing"
}
```

#### shuttle_stage_update

Shuttle pipeline stage progressed.

```json
{
  "type": "shuttle_stage_update",
  "shuttle_id": "uuid",
  "current_stage": "requirements",
  "status": "in_transit"
}
```

#### shuttle_complete

Shuttle pipeline finished.

```json
{
  "type": "shuttle_complete",
  "shuttle_id": "uuid",
  "score": 85.5,
  "results": {}
}
```

### Schedule Messages

#### schedule_created

Scheduled task created.

```json
{
  "type": "schedule_created",
  "task_id": "uuid",
  "title": "Daily standup reminder",
  "next_run_at": "2026-03-07T09:00:00Z"
}
```

#### schedule_cancelled

Scheduled task cancelled.

```json
{
  "type": "schedule_cancelled",
  "task_id": "uuid"
}
```

### Roarboot Messages

#### roarboot_status

Roarboot service status update.

```json
{
  "type": "roarboot_status",
  "status": "running",
  "docker_status": "healthy"
}
```

#### roarboot_result

Roarboot operation result.

```json
{
  "type": "roarboot_result",
  "operation": "search",
  "data": {}
}
```

#### roarboot_open_webview

Open Roarboot web interface in embedded view.

```json
{
  "type": "roarboot_open_webview",
  "url": "http://localhost:3838"
}
```

### Research Messages

#### research_result

Research operation completed.

```json
{
  "type": "research_result",
  "query": "AI trends 2026",
  "results": [],
  "summary": "..."
}
```

### Exploration Messages

#### exploration_update

AI exploration progress.

```json
{
  "type": "exploration_update",
  "session_id": "uuid",
  "nodes": [],
  "edges": [],
  "status": "exploring"
}
```

### Voice Control Messages

#### voice_end_requested

Request to end voice session.

```json
{
  "type": "voice_end_requested"
}
```

#### voice_restart_requested

Request to restart voice session.

```json
{
  "type": "voice_restart_requested"
}
```

### Task Messages

#### task_created

Desktop/background task created.

```json
{
  "type": "task_created",
  "task_id": "uuid",
  "title": "Install dependencies",
  "status": "pending"
}
```

#### task_updated

Task status changed.

```json
{
  "type": "task_updated",
  "task_id": "uuid",
  "status": "completed",
  "result": {}
}
```

#### task_progress

Task execution progress.

```json
{
  "type": "task_progress",
  "task_id": "uuid",
  "progress": 60,
  "message": "Installing packages..."
}
```

### N8n Messages

#### n8n_workflow_created

N8n workflow generated and pushed to instance.

```json
{
  "type": "n8n_workflow_created",
  "workflow_id": "string",
  "name": "My Workflow",
  "nodes_count": 5
}
```

### Minibook Messages

#### minibook_result

Minibook collaboration result.

```json
{
  "type": "minibook_result",
  "discussion_id": "uuid",
  "responses": []
}
```

### Summary / Document Messages

#### idea_summarized

Idea summary generated.

```json
{
  "type": "idea_summarized",
  "idea_id": "uuid",
  "summary": "..."
}
```

#### feature_docs_generated

Feature documentation generated from bubble.

```json
{
  "type": "feature_docs_generated",
  "bubble_id": "uuid",
  "docs": []
}
```

#### project_structure_generated

Project structure generated from bubble content.

```json
{
  "type": "project_structure_generated",
  "bubble_id": "uuid",
  "structure": {}
}
```

#### projektdoku_generated

Project documentation generated (German).

```json
{
  "type": "projektdoku_generated",
  "bubble_id": "uuid",
  "content": "..."
}
```

### Bubble Lifecycle Messages

#### bubble_created

Bubble created (distinct from node_added for bubble-specific UI).

```json
{
  "type": "bubble_created",
  "bubble_id": "uuid",
  "title": "Marketing"
}
```

#### bubble_updated

Bubble properties changed.

```json
{
  "type": "bubble_updated",
  "bubble_id": "uuid",
  "title": "New Title"
}
```

#### bubble_deleted

Bubble deleted.

```json
{
  "type": "bubble_deleted",
  "bubble_id": "uuid"
}
```

#### bubble_scored

Bubble score updated.

```json
{
  "type": "bubble_scored",
  "bubble_id": "uuid",
  "score": 78.5
}
```

#### bubble_evolution_scored

Bubble evolution evaluation completed.

```json
{
  "type": "bubble_evolution_scored",
  "bubble_id": "uuid",
  "evolution_score": 65.0
}
```

#### bubble_promoted

Bubble promoted to project.

```json
{
  "type": "bubble_promoted",
  "bubble_id": "uuid",
  "project_id": "uuid"
}
```

#### entered_bubble

Entered a bubble context.

```json
{
  "type": "entered_bubble",
  "bubble_id": "uuid",
  "bubble_name": "Marketing"
}
```

#### exited_bubble

Exited a bubble context.

```json
{
  "type": "exited_bubble"
}
```

#### bubbles_listed

Bubble list response.

```json
{
  "type": "bubbles_listed",
  "bubbles": []
}
```

#### ideas_listed

Ideas list response.

```json
{
  "type": "ideas_listed",
  "ideas": []
}
```

### Agent Messages

#### agent_switching

Agent switch in progress.

```json
{
  "type": "agent_switching",
  "from_agent": "rachel",
  "to_agent": "alice"
}
```

### Navigation Control Messages

#### enter_selection

Enter selected bubble/project.

```json
{"type": "enter_selection"}
```

#### exit_view

Exit current view to overview.

```json
{"type": "exit_view"}
```

#### select_item

Select next/previous item.

```json
{"type": "select_item", "direction": "next"}
```

#### select_by_name

Select item by name or index.

```json
{"type": "select_by_name", "name": "Marketing"}
```

#### select_by_index

Select item by numeric index.

```json
{"type": "select_by_index", "index": 3}
```

#### get_view_state

Request current view state.

```json
{"type": "get_view_state"}
```

### Shuttle Navigation Messages

#### enter_shuttle / enter_shuttle_by_name

Enter shuttle detail view.

```json
{"type": "enter_shuttle", "shuttle_id": "uuid"}
```

#### exit_shuttle

Exit shuttle view.

```json
{"type": "exit_shuttle"}
```

#### select_shuttle / select_shuttle_by_name

Select a shuttle.

```json
{"type": "select_shuttle", "direction": "next"}
```

#### list_shuttles

List all shuttles.

```json
{"type": "list_shuttles"}
```

#### shuttle_synced

Shuttle synced from req-orchestrator.

```json
{"type": "shuttle_synced", "shuttle_id": "uuid"}
```

#### shuttle_continue_to_project

Continue from shuttle to project creation.

```json
{"type": "shuttle_continue_to_project", "shuttle_id": "uuid"}
```

#### stage_shuttle_created

Stage-specific shuttle created.

```json
{"type": "stage_shuttle_created", "shuttle_id": "uuid", "stage": "requirements"}
```

#### requirements_evaluated

Requirements evaluation completed.

```json
{"type": "requirements_evaluated", "bubble_id": "uuid", "results": {}}
```

### Coding Navigation Messages

#### exit_project_space

Exit coding/projects space.

```json
{"type": "exit_project_space"}
```

### Canvas Operation Messages

#### node_deleted

Canvas node deleted (alias for node_removed).

```json
{"type": "node_deleted", "node_id": "uuid"}
```

#### node_moved

Canvas node position changed.

```json
{"type": "node_moved", "node_id": "uuid", "x": 150, "y": 300}
```

#### canvas_node_created

Canvas-specific node created.

```json
{"type": "canvas_node_created", "node": {}}
```

#### edge_created

Edge created (alias for edge_added).

```json
{"type": "edge_created", "edge": {}}
```

### Tool Feedback Messages

#### tool_add_node / tool_update_node / tool_delete_node

Tool-initiated canvas mutations.

```json
{"type": "tool_add_node", "node": {}}
```

#### tool_failed

Tool execution failed.

```json
{"type": "tool_failed", "tool": "create_bubble", "error": "..."}
```

### Batch Messages

#### batch_progress

Batch operation progress.

```json
{"type": "batch_progress", "completed": 5, "total": 10}
```

### EyeTerm / Calibration Messages

#### calibration_done

Eye tracking calibration completed.

```json
{"type": "calibration_done", "accuracy": 0.95}
```

### Error Messages

#### error

```json
{
  "type": "error",
  "message": "Tool execution failed: ...",
  "event_type": "bubble.create"
}
```

## Electron to Python

### voice_input

Manual text input (bypass voice layer).

```json
{
  "type": "voice_input",
  "text": "Erstelle Bubble Test"
}
```

### navigate

UI-triggered navigation.

```json
{
  "type": "navigate",
  "bubble_id": "uuid-string"
}
```
