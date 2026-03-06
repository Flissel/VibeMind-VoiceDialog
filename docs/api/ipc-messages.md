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
