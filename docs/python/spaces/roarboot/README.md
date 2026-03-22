# Roarboot Space (Rowboat)

> **Naming:** "Roarboot" is the internal codename used in class names, streams, and event prefixes. The official project name is "Rowboat".

Knowledge graph and content generation space powered by the Rowboat platform.

## Architecture

```
User: "Suche nach X in Rowboat"
  -> IntentClassifier -> roarboot.search
    -> RoarbootBackendAgent (events:tasks:roarboot)
      -> roarboot_tools.py (search_knowledge)
        -> roarboot_client.py (SDK + HTTP fallback)
          -> Rowboat Docker Stack (Next.js + MongoDB + Qdrant)
```

## Backend Agent

- **Class:** `RoarbootBackendAgent` in `python/spaces/rowboat/agents/roarboot_agent.py`
- **Stream:** `events:tasks:roarboot`
- **Event Prefix:** `roarboot.*`

## Tools

### Knowledge & Content Tools

**File:** `python/spaces/rowboat/tools/roarboot_tools.py`

| Tool | Description |
|------|-------------|
| `search_knowledge(query)` | Search knowledge graph |
| `query_knowledge(query)` | Query about person/project/topic |
| `draft_email(subject, body, recipient?)` | Generate email with context |
| `generate_meeting_brief(meeting_id?)` | Prepare meeting brief |
| `generate_deck(topic, slides?)` | Generate presentation |
| `process_voice_note(content)` | Process voice note input |
| `get_status()` | Check Rowboat service status |
| `open_webview()` | Open Rowboat WebView |
| `reset_conversation()` | Reset conversation context |

### Docker Management Tools

**File:** `python/spaces/rowboat/tools/docker_tools.py`

| Tool | Description |
|------|-------------|
| `start_docker()` | Start Rowboat Docker stack |
| `stop_docker()` | Stop Docker stack |
| `restart_docker()` | Restart Docker stack |
| `docker_status()` | Check Docker container health |

## Docker Stack

| Service | Port | Purpose |
|---------|------|---------|
| Rowboat | :3000 | Main application (Next.js) |
| MongoDB | :27017 | Data storage |
| Redis | :6379 | Queuing |
| Qdrant | :6333 | Vector search (RAG) |

## Event Types

| Event | Parameters | Description |
|-------|-----------|-------------|
| `roarboot.search` | `{query}` | Search knowledge graph |
| `roarboot.query` | `{query}` | Query knowledge base |
| `roarboot.email_draft` | `{subject, body, recipient?}` | Draft email |
| `roarboot.meeting_brief` | `{meeting_id?}` | Generate meeting brief |
| `roarboot.deck` | `{topic, slides?}` | Generate slide deck |
| `roarboot.voice_note` | `{content}` | Process voice note |
| `roarboot.status` | -- | Get service status |
| `roarboot.open` | -- | Open Rowboat interface |
| `roarboot.reset` | -- | Reset conversation |
| `roarboot.docker.start` | -- | Start Docker stack |
| `roarboot.docker.stop` | -- | Stop Docker stack |
| `roarboot.docker.restart` | -- | Restart Docker stack |
| `roarboot.docker.status` | -- | Get Docker health |

## Supporting Modules

| Module | File | Purpose |
|--------|------|---------|
| API Client | `tools/roarboot_client.py` | SDK wrapper + direct HTTP fallback |
| Broadcast Agent | `broadcast/roarboot_broadcast_agent.py` | Fan-out broadcast agent |
| Health Worker | `workers/roarboot_workers.py` | HealthCheckWorker (monitors Docker every 60s) |
| Config | `config.py` | RoarbootConfig settings |
