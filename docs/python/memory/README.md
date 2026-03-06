# Memory Services

The `python/memory/` package provides persistent memory capabilities via the Supermemory API. All services are optional and enabled through environment variables.

## File Index

| File | Purpose |
|------|---------|
| `task_memory_service.py` | Track task execution history and store TaskEvent records |
| `conversation_memory_service.py` | Store conversation context for cross-session recall (v4 API) |
| `user_profile_service.py` | Learn user preferences and habits over time |
| `conversation_router.py` | Route intents using past conversation context (RAG-based) |
| `supermemory_client.py` | Legacy HTTP client for Supermemory API (backward compatibility) |
| `__init__.py` | Package init -- re-exports all services, models, and singletons |

## Configuration

Enable via `.env`:

```bash
USE_TASK_MEMORY=true
USE_CONVERSATION_MEMORY=true
USE_USER_PROFILES=true
USE_RAG_CLASSIFIER=true
SUPERMEMORY_API_KEY=xxx
FAST_STARTUP=true             # Skip Supermemory API calls at startup
```

## task_memory_service.py

Tracks task execution events. Each task action (create, start, complete, fail) is recorded as a `TaskEvent` and stored in Supermemory for semantic retrieval.

Key exports:
- `TaskMemoryService` -- Main service class
- `TaskEvent` -- Dataclass representing a task event
- `get_task_memory_service()` -- Singleton accessor
- `reset_task_memory_service()` -- Reset singleton (for testing)

## conversation_memory_service.py

Stores conversation context for cross-session recall using Supermemory's v4 API. Allows Rachel to remember what was discussed in previous sessions and retrieve relevant context.

Key exports:
- `ConversationMemoryService` -- Main service class
- `get_conversation_memory_service()` -- Singleton accessor
- `reset_conversation_memory_service()` -- Reset singleton (for testing)

## user_profile_service.py

Learns user preferences and habits over time. Tracks patterns like preferred language, common commands, and workspace organization preferences.

Key exports:
- `UserProfileService` -- Main service class
- `UserProfile` -- Dataclass representing a user's learned profile
- `get_user_profile_service()` -- Singleton accessor
- `reset_user_profile_service()` -- Reset singleton (for testing)

## conversation_router.py

Routes intents using past conversation context via RAG (Retrieval-Augmented Generation). Searches stored conversations for similar past intents to improve classification accuracy.

Key exports:
- `ConversationRouter` -- Main router class
- `PastIntent` -- Dataclass for previously classified intents
- `get_conversation_router()` -- Singleton accessor
- `reset_conversation_routers()` -- Reset singleton (for testing)

## supermemory_client.py

Legacy HTTP client wrapping the Supermemory REST API. Provides basic CRUD operations for memories. Retained for backward compatibility; newer services use the v4 API directly.

Key export:
- `SupermemoryClient` -- HTTP client class

## Architecture

```
Voice Input
    |
    v
ConversationRouter -----> Supermemory (search past intents)
    |                          |
    |  PastIntent matches      |
    v                          v
IntentClassifier <---- Similar past classifications
    |
    v
Tool Execution
    |
    v
TaskMemoryService -----> Supermemory (store task event)
ConversationMemoryService -> Supermemory (store conversation)
UserProfileService --------> Supermemory (update preferences)
```
