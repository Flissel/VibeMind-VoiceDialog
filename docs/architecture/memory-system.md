# Memory System

## Overview

VibeMind has an optional semantic memory layer powered by [Supermemory](https://supermemory.ai). It provides cross-session context, task tracking, and user preference learning.

## Services

| Service | File | Enable | Purpose |
|---------|------|--------|---------|
| TaskMemory | `python/memory/task_memory_service.py` | `USE_TASK_MEMORY=true` | Track task events across sessions |
| ConversationMemory | `python/memory/conversation_memory_service.py` | `USE_CONVERSATION_MEMORY=true` | Persist and recall conversation context |
| UserProfile | `python/memory/user_profile_service.py` | `USE_USER_PROFILES=true` | Learn user preferences and patterns |
| ConversationRouter | `python/memory/conversation_router.py` | `USE_RAG_CLASSIFIER=true` | RAG-based intent routing |

## Configuration

```bash
# Enable individual services
USE_TASK_MEMORY=true
USE_CONVERSATION_MEMORY=true
USE_USER_PROFILES=true
USE_RAG_CLASSIFIER=true

# Required for any memory service
SUPERMEMORY_API_KEY=xxx

# Performance
FAST_STARTUP=true   # Skip memory API calls at startup
```

## How It Works

### Task Memory
Records every tool execution as a memory item. When a similar task comes up later, the system can recall how it was handled before.

### Conversation Memory
Stores conversation summaries after each session. On new sessions, retrieves relevant past context to improve classification accuracy.

### User Profile
Tracks user preferences (language, common commands, preferred formats) and adapts the system behavior over time.

### RAG-based Classification
Uses semantic search over past intents to improve classification of ambiguous inputs. Compares the current input against stored examples.

## Without Memory

All memory services are optional. With all disabled, VibeMind still works fully — it just doesn't retain context between sessions. Each session starts fresh.
