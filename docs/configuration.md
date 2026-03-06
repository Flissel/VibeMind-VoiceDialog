# Configuration Reference

All configuration is via environment variables in `.env` (copied from `.env.example`).

## Voice Provider Selection

| Variable | Default | Description |
|----------|---------|-------------|
| `VOICE_PROVIDER` | `openai_realtime` | Voice backend: `openai_realtime` or `elevenlabs` |
| `OPENAI_REALTIME_MODEL` | `gpt-4o-realtime-preview` | Realtime API model |
| `OPENAI_REALTIME_VOICE` | `alloy` | Voice: alloy, ash, ballad, coral, echo, sage, shimmer, verse |

## OpenAI Realtime

| Variable | Example | Description |
|----------|---------|-------------|
| `OPENAI_API_KEY` | `sk-xxx` | OpenAI API key for Realtime voice + intent classification |

## ElevenLabs

| Variable | Default | Description |
|----------|---------|-------------|
| `ELEVENLABS_API_KEY` | --- | ElevenLabs key (if using elevenlabs provider) |
| `AGENT_MULTIVERSE` | --- | ElevenLabs Rachel agent ID |
| `ELEVENLABS_AGENT_ID` | --- | Fallback ElevenLabs agent ID |

## Voice Bridge V2

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_VOICE_BRIDGE_V2` | `false` | Enable async voice architecture where results are delivered on next user input via NotificationQueue |

## VNC Live Preview

| Variable | Default | Description |
|----------|---------|-------------|
| `VNC_BASE_URL` | --- | Cloud reverse proxy URL for VNC preview (e.g., `https://preview.vibemind.io/vnc`) |
| `VNC_HOST` | --- | Remote server IP/hostname for direct VNC connection. If neither set, uses localhost |

## Coding Engine

| Variable | Default | Description |
|----------|---------|-------------|
| `CODING_ENGINE_PATH` | --- | Path to Coding_engine submodule (auto-detected if not set) |

## Database (Supabase)

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPABASE_URL` | --- | Supabase project URL (e.g., `https://your-project.supabase.co`) |
| `SUPABASE_KEY` | --- | Supabase anonymous key |

## Req-Orchestrator

| Variable | Default | Description |
|----------|---------|-------------|
| `REQ_ORCHESTRATOR_URL` | `http://localhost:8087` | URL of the req-orchestrator service (Shuttle pipeline) |
| `REQ_SCORE_THRESHOLD` | `0.7` | Score threshold for passing validation (0.0 - 1.0) |
| `USE_KG_API` | `false` | Enable Knowledge Graph API calls in Shuttle pipeline |
| `USE_TECHSTACK_API` | `false` | Enable TechStack API calls in Shuttle pipeline |

## OpenRouter (LLM)

| Variable | Default | Description |
|----------|---------|-------------|
| `OPENROUTER_API_KEY` | --- | Alternative LLM provider for classification and summarization |
| `RAG_CLASSIFIER_MODEL` | `openai/gpt-4o` | LLM model for RAG intent classification (via OpenRouter) |

## Supermemory

| Variable | Default | Description |
|----------|---------|-------------|
| `SUPERMEMORY_API_KEY` | --- | Supermemory API key for semantic memory and RAG classification |
| `USE_RAG_CLASSIFIER` | `false` | Enable RAG-based intent classification using Supermemory semantic search |

## Memory Services

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_TASK_MEMORY` | `false` | Track task events across sessions |
| `USE_CONVERSATION_MEMORY` | `false` | Persist conversation context |
| `USE_USER_PROFILES` | `false` | Learn user preferences |

## Performance

| Variable | Default | Description |
|----------|---------|-------------|
| `FAST_STARTUP` | `true` | Skip Supermemory API calls at startup |
| `FORCE_SYNC_MODE` | `true` | `true` = direct tool execution (no Redis). `false` = async via Redis streams |

## Broadcast Mode

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_BROADCAST_MODE` | `false` | Fan-out architecture: every intent is broadcast to ALL agents for profiling. Requires Supermemory for profiling storage |

## DroPE Resolution

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_DROPE_RESOLVER` | `false` | Resolve ambiguous references ("das", "nochmal") using conversation context |
| `DROPE_MODEL` | `SakanaAI/DroPE-SmolLM-135M-32K` | Model for reference resolution |

## Roarboot Space

| Variable | Default | Description |
|----------|---------|-------------|
| `ROWBOAT_MODEL` | --- | Override default LLM model for Rowboat (e.g., `anthropic/claude-sonnet-4`) |
| `ROWBOAT_UPDATE_CHECK_INTERVAL` | `21600` | Auto-update check interval in seconds (default: 6 hours) |
| `ROWBOAT_PUBLISH_ENABLED` | `true` | Publish space metadata to Rowboat knowledge graph (`~/.rowboat/`) |

## Research Space (ZeroClaw)

| Variable | Default | Description |
|----------|---------|-------------|
| `USE_ZEROCLAW` | `false` | Enable ZeroClaw web research space |
| `ZEROCLAW_BINARY` | --- | Path to zeroclaw binary (default: searches PATH and `external/zeroclaw`) |
| `ZEROCLAW_PORT` | `42618` | Gateway port for ZeroClaw subprocess |
| `ZEROCLAW_CONFIG_PATH` | --- | Custom config file path for ZeroClaw |

## Minibook Space

| Variable | Default | Description |
|----------|---------|-------------|
| `MINIBOOK_ENABLED` | `false` | Enable Minibook inter-space collaboration |
| `MINIBOOK_URL` | `http://localhost:3480` | Minibook API URL |
| `MINIBOOK_AUTO_REGISTER` | `true` | Auto-register VibeMind spaces as Minibook agents on startup |
| `MINIBOOK_POLL_INTERVAL` | `2.0` | Polling interval for collaboration responses (seconds) |
| `MINIBOOK_COLLABORATION_TIMEOUT` | `120.0` | Timeout for multi-space collaboration (seconds) |
| `USE_MINIBOOK_HUB` | `false` | Route ALL intents through Minibook instead of direct execution |
| `MINIBOOK_HUB_SYNC_TIMEOUT` | `10` | Timeout for single-space sync-wait (seconds) |
| `MINIBOOK_HUB_ASYNC_TIMEOUT` | `120` | Timeout for multi-space async-poll (seconds) |
| `MINIBOOK_ENRICHMENT_MODEL` | `openai/gpt-4o-mini` | LLM model for SpaceRouter (via OpenRouter) |
| `MINIBOOK_ENRICHMENT_LLM` | `true` | Enable LLM-based routing (false = keyword-only fallback) |
| `MINIBOOK_RACHEL_PROMPT` | `true` | Enable Rachel prompt metadata (agent status, tasks in system prompt) |

## Schedule Space

| Variable | Default | Description |
|----------|---------|-------------|
| `SCHEDULE_ENABLED` | `false` | Enable APScheduler-based task scheduling |
| `SCHEDULE_TIMEZONE` | `Europe/Berlin` | Default timezone for scheduled tasks |
| `SCHEDULE_MAX_CONCURRENT` | `5` | Maximum concurrent APScheduler jobs |
| `SCHEDULE_MISFIRE_GRACE` | `60` | Misfire grace time in seconds (how late a job can fire) |

## Debugging

| Variable | Default | Description |
|----------|---------|-------------|
| `DEBUG` | `false` | Enable debug mode (verbose logging) |

## Minimal Configuration

For the fastest setup with fewest dependencies:

```bash
OPENAI_API_KEY=sk-your-key
FORCE_SYNC_MODE=true
FAST_STARTUP=true
```

This gives you: voice input, Ideas space, basic intent classification, Electron UI. No Redis, no memory services, no optional spaces.
