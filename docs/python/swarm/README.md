# Swarm Package

The `python/swarm/` package is the core infrastructure for VibeMind's voice-controlled multi-agent orchestration. It contains 20 subdirectories and 8 top-level modules.

## Subdirectory Index

| Directory | Purpose | Key Files |
|-----------|---------|-----------|
| `agents/` | Input enhancement pipeline (collector, enhancer, validator) | `collector_agent.py`, `intent_enhancer.py`, `execution_validator.py` |
| `analysis/` | Multi-agent intent analysis team | `intent_analysis_team.py`, `context_agent.py`, `reasoning_agent.py`, `semantic_agent.py`, `user_context.py` |
| `backend_agents/` | Base agent class + lazy registry for domain agents | `base_agent.py`, `agent_pool.py`, `__init__.py` |
| `broadcast/` | Event broadcast infrastructure with sub-agents | `base_broadcast_agent.py`, `dispatcher.py`, sub_agents: `context_sub_agent.py`, `memory_sub_agent.py` |
| `context/` | Runtime context providers | `bubble_context_provider.py`, `real_time_state.py`, `session_context.py` |
| `conversion/` | Conversion AI personalities and style generation | `conversion_ai.py`, `personality_generator.py` |
| `debugging/` | Agent execution logging and diagnostics | `agent_execution_logger.py` |
| `evaluation/` | Real-time intent evaluation and quality scoring | `realtime_evaluator.py` |
| `event_team/` | Event routing, job management, task seeding | `event_router.py`, `job_manager.py`, `task_seeder.py` |
| `executive/` | Executive-level conversation memory | `conversation_memory.py` |
| `listeners/` | Redis stream listeners for status and questions | `question_listener.py`, `status_listener.py` |
| `logging/` | Intent and tool execution logging | `intent_logger.py`, `tool_logger.py` |
| `monitoring/` | System health and status monitoring | `system_status.py` |
| `orchestrator/` | Core intent classification and orchestration | See [orchestrator/](orchestrator/) |
| `reasoning/` | Reasoning event tracking | `reasoning_event.py`, `reasoning_logger.py` |
| `sub_agents/` | Base class for sub-agent pattern | `base_sub_agent.py` |
| `tools/` | Swarm-internal tool utilities | `__init__.py` |
| `user_agents/` | User-facing agent base classes | `base.py` |
| `workers/` | Background worker base class | `base_worker.py` |
| `zeroclaw/` | ZeroClaw deep research client and process manager | `client.py`, `process_manager.py` |

## Top-Level Modules

| File | Purpose |
|------|---------|
| `event_bus.py` | Redis-based event bus (publish/subscribe, stream management, SwarmEvent dataclass) |
| `event_buffer.py` | Buffers rapid-fire events for batched processing |
| `navigation.py` | Multiverse navigation state machine (space enter/exit tracking) |
| `ollama_client.py` | Local Ollama LLM client for on-device inference |
| `cloud_client.py` | Cloud LLM client (OpenRouter, OpenAI) for remote inference |
| `tts_queue.py` | Text-to-speech queue for ordered voice output |
| `voice_bridge_v2.py` | VoiceBridgeV2 -- connects voice agents to the swarm backend |
| `__init__.py` | Package init |

## Key Subsystem Details

### event_bus.py

The central nervous system. Provides:
- `EventBus` class with publish/subscribe on Redis streams
- `SwarmEvent` dataclass (stream, event_type, payload, job_id)
- Stream constants: `STREAM_TASKS_IDEAS`, `STREAM_TASKS_CODING`, `STREAM_TASKS_DESKTOP`, `STREAM_STATUS`, `STREAM_QUESTIONS`
- Per-user stream isolation via `get_user_stream()`
- Sync mode fallback when Redis is unavailable

### event_team/

Handles the routing layer between classification and execution:
- `event_router.py` -- Routes classified events to the correct Redis stream based on domain prefix
- `job_manager.py` -- Creates and tracks background jobs
- `task_seeder.py` -- Seeds events into Redis streams for backend agent consumption

### agents/ (Input Enhancement)

Optional preprocessing pipeline that runs before intent classification:
1. `collector_agent.py` -- Accumulates fragmented speech (< 3 words) into complete sentences
2. `intent_enhancer.py` -- Fixes ASR errors using learned rules, normalizes dialects
3. `execution_validator.py` -- Validates results and triggers learning feedback

### analysis/

Multi-agent team for complex intent analysis:
- `intent_analysis_team.py` -- Coordinates the analysis team
- `context_agent.py` -- Provides workspace context
- `reasoning_agent.py` -- Logical reasoning about intent
- `semantic_agent.py` -- Semantic similarity analysis
- `user_context.py` -- User preference and history context

### zeroclaw/

Integration with ZeroClaw deep research engine:
- `client.py` -- HTTP client for ZeroClaw API
- `process_manager.py` -- Manages ZeroClaw subprocess lifecycle
