# Glossary

Project-specific terms used throughout VibeMind documentation.

| Term | Definition |
|------|-----------|
| **Bubble** | A container/folder for ideas. Bubbles can be nested. Rendered as 3D glass spheres in the UI. |
| **Idea** | A content node inside a bubble. Can have a title, description, tags, format, and connections to other ideas. |
| **Space** | A domain module with its own agent, tools, and event types. VibeMind has 8 spaces: Ideas, Coding, Desktop, Rowboat, Research, Minibook, Shuttles, Schedule. |
| **Event Type** | A structured action identifier like `bubble.create` or `idea.auto_link`. Produced by the IntentClassifier from voice input. |
| **Intent Classification** | The LLM-based process of converting natural language ("Erstelle Bubble Marketing") to a structured event type + payload. |
| **Rachel** | The OpenAI Realtime voice agent. The primary voice interface for VibeMind. |
| **Swarm** | The backend agent system that executes tools. Each space has a swarm agent. |
| **Backend Agent** | A Python class (e.g., IdeasAgent) that maps event types to tool functions and executes them. |
| **TOOL_MAP** | A dict in each backend agent mapping event_type strings to tool function names. |
| **PARAM_MAPPING** | A dict that normalizes parameter names from the classifier output to what tool functions expect. |
| **Sync Mode** | Direct tool execution without Redis. Set `FORCE_SYNC_MODE=true`. Default for local development. |
| **Async Mode** | Event processing via Redis streams. Allows distributed agent processing. |
| **Broadcast** | The mechanism by which Python tool results are sent to the Electron UI via `_broadcast_to_electron()`. |
| **IPC** | Inter-Process Communication between Electron (Node.js) and Python via stdin/stdout JSON. |
| **DroPE** | Dynamic reference Position Encoding. Resolves ambiguous references ("das", "es", "nochmal") using conversation context. |
| **Shuttle** | A requirements evaluation pipeline that takes a bubble through stages: mining → requirements → validation → knowledge graph → techstack. |
| **Minibook** | An inter-space collaboration system allowing multiple spaces to work together on a task. |
| **Rowboat** | A knowledge graph and RAG (Retrieval-Augmented Generation) engine used as a space. |
| **ZeroClaw** | A web research engine integrated as the Research space. |
| **Canvas Node** | The visual representation of an idea or project in the Three.js 3D scene. |
| **Canvas Edge** | A visual connection between two canvas nodes. |
| **CollectorAgent** | Optional pipeline stage that accumulates short voice fragments before classification. |
| **IntentEnhancer** | Optional pipeline stage that corrects ASR (speech recognition) errors. |
| **Tool Orchestrator** | An LLM-powered system (Claude Sonnet) that handles multi-step requests requiring multiple tool calls. |
| **Supermemory** | External semantic memory service for cross-session context persistence. |
| **MoireServer** | An OCR/vision server used by the Desktop space for screen element detection. |
| **BubblesAgent** | Backend agent handling `bubble.*` events (separate from IdeasAgent which handles `idea.*` events). |
| **RoarbootBackendAgent** | Backend agent for Rowboat knowledge graph queries (`roarboot.*` events). |
| **ScheduleBackendAgent** | Backend agent for APScheduler-based task scheduling (`schedule.*` events). |
| **MinibookBackendAgent** | Backend agent for inter-space collaboration via Minibook (`minibook.*` events). |
| **ZeroClawResearchAgent** | Backend agent for web research via ZeroClaw engine (`research.*` events). |
| **VoiceBridgeV2** | Async voice architecture where results are delivered on next user input via NotificationQueue, rather than blocking during tool execution. |
| **VoiceProvider** | Configurable voice backend: `openai_realtime` or `elevenlabs`, set via the `VOICE_PROVIDER` env var. |
| **BroadcastMode** | Fan-out architecture where intents are broadcast to all agents for profiling. Non-responsible agents analyze the intent for user profiling insights. |
