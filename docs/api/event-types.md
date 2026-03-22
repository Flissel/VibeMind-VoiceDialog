# Event Types Reference

Complete list of all event types routed by the Event Router, grouped by domain.
Source of truth: `python/swarm/event_team/event_router.py` STREAM_MAPPING.

## Bubble Events

Stream: `events:tasks:bubbles`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `bubble.list` | — | List all top-level bubbles |
| `bubble.create` | `{title}` | Create a new bubble |
| `bubble.enter` | `{bubble_name}` | Navigate into a bubble |
| `bubble.exit` | — | Exit current bubble (go up) |
| `bubble.back` | — | Alias for bubble.exit |
| `bubble.delete` | `{title}` | Delete a bubble |
| `bubble.delete_all_except` | `{titles}` | Delete all bubbles except specified |
| `bubble.update` | `{title, new_title?, new_description?}` | Update bubble properties |
| `bubble.find` | `{query}` | Search bubbles by name |
| `bubble.stats` | — | Get bubble statistics |
| `bubble.score` | — | Score all bubbles |
| `bubble.evaluate` | `{title?}` | Evaluate bubble quality |
| `bubble.promote` | `{title}` | Promote bubble to project |
| `bubble.current` | — | Get current bubble context |

## Idea Events

Stream: `events:tasks:ideas`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `idea.list` | — | List ideas in current bubble |
| `idea.create` | `{title, content?}` | Create a new idea/note |
| `idea.update` | `{idea_name, new_content}` | Update idea content |
| `idea.delete` | `{idea_name}` | Delete an idea |
| `idea.find` | `{query}` | Search ideas |
| `idea.connect` | `{idea1, idea2}` | Link two ideas |
| `idea.auto_link` | — | Auto-link related ideas (LLM) |
| `idea.add_image` | `{idea_name, image_url}` | Attach image to idea |
| `idea.current_space` | — | Get current space context |
| `idea.format_table` | `{idea_name}` | Format idea as table |
| `idea.summarize` | `{idea_name?}` | Generate summary |
| `idea.whitepaper` | `{start_node?}` | Generate white paper |
| `idea.white_paper` | `{start_node?}` | Alias for idea.whitepaper |
| `idea.expand` | `{idea_name, count?}` | Expand into sub-ideas |
| `idea.explain` | `{idea_name}` | Explain an idea |
| `idea.analyze_links` | `{idea_name?}` | Analyze link structure |
| `idea.generate_doc` | `{idea_name?}` | Generate documentation for idea |

### Idea Format Events

All format events route to the ideas stream and map to the `convert_format` tool with injected `target_format`:

| Event Type | Target Format |
|-----------|--------------|
| `idea.format_note` | note |
| `idea.format_action_list` | action_list |
| `idea.format_pros_cons` | pros_cons |
| `idea.format_hierarchy` | hierarchy |
| `idea.format_specs` | specs |
| `idea.convert_format` | (user-specified) |
| `idea.list_formats` | (lists available formats) |
| `idea.format_revert` | (reverts to previous format) |

### Idea Exploration Events

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `idea.explore.start` | `{query?}` | Start AI exploration |
| `idea.explore.stop` | — | Stop exploration |
| `idea.explore.status` | — | Get exploration state |
| `idea.explore.accept` | `{node_id}` | Accept discovered connection |
| `idea.explore.reject` | `{node_id}` | Reject discovered connection |
| `idea.explore.depth` | `{level}` | Set exploration depth |
| `idea.explore.visualize` | — | Generate exploration visualization |
| `idea.explore.continue` | — | Continue paused exploration |
| `idea.explore.direction` | `{direction}` | Set exploration direction |
| `idea.explore.respond` | `{response}` | Respond to exploration prompt |

## Code Events

Stream: `events:tasks:coding`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `code.generate` | `{title, description?}` | Generate a code project |
| `code.modify` | `{instruction}` | Modify generated code |
| `code.status` | — | Get generation status |
| `code.show` | `{project_id?}` | Show project details |
| `code.preview.start` | `{project_id?}` | Start VNC preview |
| `code.preview.stop` | `{project_id?}` | Stop preview |
| `code.list` | — | List generated projects |
| `code.cancel` | `{job_id}` | Cancel code generation |
| `idea.to_project` | `{idea_name}` | Convert idea to project |

## Desktop Events

Stream: `events:tasks:desktop`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `desktop.open_app` | `{app_name}` | Open an application |
| `desktop.click` | `{element_description}` | Click a UI element |
| `desktop.type` | `{text}` | Type text |
| `desktop.press_key` | `{key}` | Press a keyboard key |
| `desktop.screenshot` | — | Take screenshot |
| `desktop.scroll` | `{direction}` | Scroll up/down |
| `desktop.task` | `{description}` | General desktop task |
| `desktop.task.create` | `{title, description}` | Create task node |
| `desktop.task.update` | `{task_id, status}` | Update task status |
| `desktop.task.list` | — | List tasks |
| `desktop.moire.scan` | — | Vision-based screen scan |
| `desktop.moire.find` | `{element}` | Find element via OCR |

## Messaging / Web Events

Stream: `events:tasks:desktop` (routed with desktop events)

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `messaging.whatsapp` | `{recipient, message}` | Send WhatsApp message |
| `messaging.telegram` | `{recipient, message}` | Send Telegram message |
| `messaging.send` | `{platform, recipient, message}` | Send message (generic) |
| `web.search` | `{query}` | Web search |
| `web.fetch` | `{url}` | Fetch webpage content |
| `openclaw.status` | — | Get OpenClaw service status |
| `openclaw.notifications` | — | Get OpenClaw notifications |

## Research Events

Stream: `events:tasks:zeroclaw`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `research.web` | `{query}` | Deep web research |
| `research.scrape` | `{url}` | Scrape webpage content |
| `research.summarize` | `{url}` | Summarize webpage |
| `research.to_idea` | `{research_id}` | Convert research result to idea |
| `research.to_rowboat` | `{research_id}` | Send research to Roarboot |

## Roarboot Events

Stream: `events:tasks:roarboot`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `roarboot.search` | `{query}` | Search across Roarboot data |
| `roarboot.query` | `{query}` | Query Roarboot knowledge base |
| `roarboot.email_draft` | `{subject, body, recipient?}` | Draft an email |
| `roarboot.meeting_brief` | `{meeting_id?}` | Generate meeting brief |
| `roarboot.deck` | `{topic, slides?}` | Generate slide deck |
| `roarboot.voice_note` | `{content}` | Create voice note |
| `roarboot.status` | — | Get Roarboot service status |
| `roarboot.open` | — | Open Roarboot interface |
| `roarboot.reset` | — | Reset Roarboot state |
| `roarboot.docker.start` | — | Start Roarboot Docker container |
| `roarboot.docker.stop` | — | Stop Roarboot Docker container |
| `roarboot.docker.restart` | — | Restart Roarboot Docker container |
| `roarboot.docker.status` | — | Get Docker container status |

## Minibook Events

Stream: `events:tasks:minibook`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `minibook.discuss` | `{topic, context?}` | Start multi-agent discussion |
| `minibook.collaborate` | `{task, agents?}` | Collaborative task execution |
| `minibook.status` | — | Get discussion status |
| `minibook.results` | `{session_id?}` | Get discussion results |
| `minibook.list_projects` | — | List Minibook projects |
| `minibook.poll` | `{question, options?}` | Poll agents for opinions |

## Schedule Events

Stream: `events:tasks:schedule`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `schedule.create` | `{title, time, action}` | Create scheduled task |
| `schedule.list` | — | List scheduled tasks |
| `schedule.cancel` | `{task_id}` | Cancel task |
| `schedule.modify` | `{task_id, changes}` | Modify task |
| `schedule.status` | `{task_id?}` | Get schedule status |
| `schedule.snooze` | `{task_id, duration}` | Snooze a scheduled task |

## N8n Events

Stream: `events:tasks:n8n`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `n8n.generate` | `{description}` | Generate workflow from natural language |
| `n8n.list` | — | List all workflows |
| `n8n.status` | — | Get n8n instance health status |
| `n8n.activate` | `{name}` | Activate a workflow |
| `n8n.deactivate` | `{name}` | Deactivate a workflow |
| `n8n.delete` | `{name}` | Delete a workflow |
| `n8n.execute` | `{name}` | Execute a workflow manually |
| `n8n.describe` | `{name}` | Show workflow details |

## Status Events

Stream: `events:status`

| Event Type | Parameters | Description |
|-----------|-----------|-------------|
| `task.started` | `{task_id, event_type}` | Task execution started |
| `task.progress` | `{task_id, progress, message}` | Task progress update |
| `task.complete` | `{task_id, result}` | Task completed successfully |
| `task.completed` | `{task_id, result}` | Alias for task.complete |
| `task.error` | `{task_id, error}` | Task failed with error |
| `task.timeout` | `{task_id}` | Task timed out |
| `task.cancelled` | `{task_id}` | Task was cancelled |
