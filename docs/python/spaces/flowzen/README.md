# Flowzen Space (Blaue Rose)

> Circadian-aware activity tracking, daily journaling, and Brain integration for passive intelligence.

## Overview

Flowzen is a passive intelligence space that monitors user activity patterns, provides circadian-aware task recommendations, and maintains a diary/journal interface. The implementation lives in a Git submodule — all top-level files are proxies. It integrates with the Brain space via `FlowzenBrainBridge` for cognitive feedback.

## Architecture

```
Voice / ClawPort Chat
        ↓
FlowzenAgent (via submodule proxy)
        ↓
flowzen_tools.py
   ├── ActivityTracker (circadian matrix)
   ├── FlowzenBrainBridge (Brain ↔ Flowzen)
   └── FlowzenConfig
        ↓
Electron BrowserView (flowzen-diary.html — page-flip UI)
```

## Backend Agent

**File:** `python/spaces/flowzen/agents/flowzen_agent.py` (proxy → submodule)
**Class:** `FlowzenAgent`
**Pattern:** Proxy to `spaces.flowzen.flowzen.agents.flowzen_agent`

## Tools

**File:** `python/spaces/flowzen/tools/flowzen_tools.py` (proxy → submodule)

| Tool | Description |
|------|-------------|
| `recommend_task()` | Generate activity recommendation based on circadian rhythm + history |
| `accept_recommendation()` | Confirm and log a recommended activity |
| `get_flowzen_status()` | Get current activity state |
| `set_electron_sender()` | Set IPC callback for Electron messaging |

## Core Components

### ActivityTracker (`python/spaces/flowzen/activity_tracker.py`)

Monitors user activity with circadian awareness.

- **CIRCADIAN_MATRIX** — Time-of-day to activity-type scoring
- **CATEGORY_DESCRIPTIONS** — Contextual descriptions per time window
- **get_time_window()** — Current circadian phase
- **get_circadian_category()** — Optimal activity category for current time

### FlowzenBrainBridge (`python/spaces/flowzen/brain_bridge.py`)

Bridge between Flowzen and the Brain (Tahlamus) cognitive system.

- **Class:** `FlowzenBrainBridge`
- **Singleton:** `get_brain_bridge()`
- Provides cognitive feedback loop between activity patterns and brain state

### FlowzenConfig (`python/spaces/flowzen/config.py`)

- **Class:** `FlowzenConfig`
- **Singleton:** `get_config()`

## Data Layer

Uses the Flowzen-specific tables in SQLite:

| Table | Purpose |
|-------|---------|
| `flowzen_checkins` | Daily check-in entries |
| `flowzen_activities` | Activity log with timestamps |
| `flowzen_diary_entries` | Diary/journal entries |

**Repository:** `python/data/flowzen_repository.py`

## Electron UI

| Component | File |
|-----------|------|
| BrowserView Manager | `electron-app/flowzen-manager.js` |
| Preload | `electron-app/flowzen-preload.js` |
| Diary HTML | `electron-app/flowzen-diary.html` |

### Diary UI (Blaue Rose Journal)

- Page-flip book interface for daily diary entries
- Loads local HTML file (not a React app)
- On show: requests fresh diary data from Python

### IPC API (`window.flowzenDiary`)

| Method | Description |
|--------|-------------|
| `recommend()` | Request a circadian-aware task recommendation |
| `register(handlers)` | Register UI update handlers |

**Incoming Events:**

| Event | Handler | Description |
|-------|---------|-------------|
| `flowzen-diary-data` | `setEntries(entries[])` | Full diary data |
| `flowzen-diary-entry` | `addEntry(entry)` | New diary entry |
| `flowzen-status` | `updateStatus(data)` | Activity status update |
| `flowzen-recommend-result` | `recommendDone(data)` | Recommendation result |

Message queue pattern: events queued until handlers are registered.

## Directory Structure

```
python/spaces/flowzen/
├── agents/
│   └── flowzen_agent.py         # Proxy → submodule
├── tools/
│   └── flowzen_tools.py         # Proxy → submodule
├── activity_tracker.py           # Proxy → submodule (circadian tracking)
├── brain_bridge.py               # Proxy → submodule (Brain integration)
├── config.py                     # Proxy → submodule
└── flowzen/                      # Git submodule (actual implementation)
    ├── agents/flowzen_agent.py   # Real FlowzenAgent
    ├── tools/flowzen_tools.py    # Real tool functions
    ├── activity_tracker.py       # Real ActivityTracker
    ├── brain_bridge.py           # Real FlowzenBrainBridge
    └── config.py                 # Real FlowzenConfig
```
