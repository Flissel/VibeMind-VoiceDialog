# Electron App

The Electron app is the desktop UI for VibeMind. It renders a 3D multiverse of bubbles and ideas using Three.js, manages the Python backend process, and integrates external tools via BrowserView embedding.

## Directory Structure

```
electron-app/
├── main.js                     # Main process: Python spawning, IPC routing (137KB)
├── preload.js                  # Context bridge for renderer security (14KB)
├── agentfarm-manager.js        # AgentFarm BrowserView (Next.js dashboard)
├── agentfarm-preload.js        # Preload for AgentFarm (team mgmt, video, n8n IPC)
├── brain-manager.js            # Brain/Tahlamus BrowserView embedding
├── clawport-manager.js         # ClawPort Dashboard BrowserView integration
├── clawport-preload.js         # Preload script for ClawPort Dashboard
├── dashboard-manager.js        # Coding Engine Dashboard BrowserView integration
├── dashboard-preload.js        # Preload script for dashboard BrowserView
├── docker-manager.js           # Docker container management
├── eyeterm-manager.js          # EyeTerm (eye tracking) BrowserView embedding
├── flowzen-manager.js          # Flowzen diary BrowserView (Blaue Rose journal)
├── flowzen-preload.js          # Preload for Flowzen diary (recommend, register)
├── mirofish-manager.js         # MiroFish BrowserView (Vue frontend, localhost:3001)
├── port-allocator.js           # Dynamic port allocation for services
├── rowboat-manager.js          # Rowboat BrowserView embedding
├── rowboat-preload.js          # Preload script for Rowboat BrowserView
├── swe-design-manager.js       # Factory Space (SWE Design) BrowserView embedding
├── video-manager.js            # Video Production BrowserView (React wizard UI)
├── video-preload.js            # Preload for Video (tools, gallery, projects IPC)
├── dashboard/                  # ClawPort Dashboard (Vite + React)
│   ├── package.json            # Dashboard dependencies (React 19, Vite 6)
│   ├── vite.config.ts          # Vite build config (base: './')
│   ├── tsconfig.json           # TypeScript config
│   ├── index.html              # Entry HTML
│   └── src/
│       ├── main.tsx            # React root
│       ├── App.tsx             # Tab router (Schedule, Agents, Chat, Memory)
│       ├── types.ts            # Shared TypeScript interfaces
│       ├── styles/globals.css  # CSS custom properties design system
│       ├── hooks/useIPC.ts     # IPC query hooks + Python message listener
│       └── features/
│           ├── ScheduleMonitor.tsx  # APScheduler task management
│           ├── AgentStatus.tsx      # 8 agent status cards with live dots
│           ├── ChatPanel.tsx        # Text input → IntentOrchestrator
│           └── MemoryBrowser.tsx    # Supermemory service overview + search
├── main-simple.js              # Simplified main process (for testing)
├── test-main.js                # Test entry point
├── package.json                # Dependencies and build configuration
├── start.sh                    # Unix startup script
├── launch_debug.bat            # Debug startup (Windows)
├── launch_electron.bat         # Production startup (Windows)
├── scripts/                    # Build and utility scripts
└── renderer/                   # Renderer process files
    ├── index.html              # Main HTML entry point (127KB)
    ├── multiverse.js           # 3D multiverse rendering with Three.js (106KB)
    ├── universe_canvas.js      # Canvas management and interaction (50KB)
    ├── rich_content_renderer.js # Rich content display and formatting (63KB)
    ├── shuttle_manager.js      # Shuttle pipeline UI (49KB)
    ├── exploration_dialog.js   # Idea exploration dialog UI (24KB)
    ├── glass_bubbles.js        # 3D glass bubble rendering
    ├── styles.css              # Application styling (67KB)
    └── lib/                    # Third-party libraries
```

## Main Process (`main.js`)

The main process is the core of the Electron app (64KB). It handles:

- **Python Backend Spawning** -- Launches the Python backend (`python/electron_backend.py`) as a child process, communicating via stdin/stdout JSON messages.
- **IPC Routing** -- Routes messages between the renderer process and the Python backend.
- **Window Management** -- Creates and manages the main BrowserWindow.
- **BrowserView Integration** -- Manages 10 embedded views: AgentFarm, Brain, ClawPort, Dashboard, EyeTerm, Flowzen, MiroFish, Rowboat, SWE Design, and Video. Views are mutually exclusive — showing one hides the others.

### Python Communication Protocol

```
Electron Main ──spawn──> Python Backend (stdin/stdout JSON)
     |                            |
 Renderer (Three.js)      Tool Execution + DB
```

Messages from Python to Electron follow this format:

```json
{"type": "node_added", "node": {"id": "abc", "title": "My Idea", "x": 100, "y": 200}}
```

| Message Type | Purpose |
|-------------|---------|
| `node_added` | New bubble/idea created |
| `node_removed` | Bubble/idea deleted |
| `edge_added` | Connection created |
| `space_changed` | Navigate to a bubble |
| `node_structured_update` | Rich content update |

## Preload Script (`preload.js`)

The preload script (12KB) establishes a secure context bridge between the main process and the renderer. It exposes a controlled API surface to the renderer via `window.electronAPI`, including:

- IPC send/receive methods
- File system access (sandboxed)
- Configuration access

## Manager Modules

### Dashboard Manager (`dashboard-manager.js`)

Manages the Coding Engine Dashboard as a BrowserView embedded in the main window. Handles:

- BrowserView lifecycle (create, show, hide, destroy)
- Navigation to the Coding Engine dashboard URL
- Communication between the dashboard and the main process

### Docker Manager (`docker-manager.js`)

Manages Docker containers for services like Rowboat. Provides:

- Container start/stop/restart
- Health check monitoring
- Container log access
- Port mapping management

### Port Allocator (`port-allocator.js`)

Dynamically allocates available ports for services. Features:

- Async port scanning to find available ports
- Port reservation and release
- Conflict detection and resolution

### Rowboat Manager (`rowboat-manager.js`)

Embeds the Rowboat UI in a BrowserView within the main window. Handles:

- BrowserView lifecycle for the Rowboat interface
- URL routing to the Rowboat web UI
- Communication between Rowboat and VibeMind

### SWE Design Manager (`swe-design-manager.js`)

Embeds the Factory Space (SWE Design) UI in a BrowserView. Handles:

- BrowserView lifecycle for the SWE Design interface
- Shuttle pipeline visualization
- Communication with the SWE Design backend
- Graceful degradation when SWE Design submodule is not available

### ClawPort Manager (`clawport-manager.js`)

Embeds the ClawPort Dashboard (a standalone Vite + React app) as a BrowserView overlay. Follows the same pattern as `RowboatManager`. Handles:

- BrowserView lifecycle (create, show, hide, destroy)
- Loads from `dashboard/dist/index.html` (production) or dev server URL
- Resize tracking with titlebar + tab bar offset
- Mutual exclusion with all other BrowserView managers

The dashboard provides 4 features accessible via tabs:

| Tab | Feature | Python IPC Messages |
|-----|---------|-------------------|
| Schedule | APScheduler task management | `get_scheduled_tasks`, `update_task_status` |
| Agents | 13 backend agent status cards | `get_agent_status` |
| Chat | Text input → IntentOrchestrator | `chat_text_input`, `get_conversation_history` |
| Memory | Supermemory service overview | `get_memory_overview`, `search_memory`, `get_recent_memory` |

**IPC Flow (ClawPort → Python):**

```
ClawPort React App
  → window.vibemindDashboard.invoke('clawport:get-agent-status')
    → ipcRenderer.invoke (clawport-preload.js)
      → ipcMain.handle (main.js)
        → sendToPythonAndWait({type: 'get_agent_status'}, 'agent_status_list')
          → Python electron_backend.py → _handle_get_agent_status_sync()
            → Returns JSON via stdout
```

**Agent Status Tracking:**

The Python backend tracks the last event per agent in-memory via `_agent_last_events`. Every `tool_action` message updates the corresponding agent's status (started → completed/error) using the `_EVENT_PREFIX_TO_AGENT` mapping:

```python
_EVENT_PREFIX_TO_AGENT = {
    "bubble.": "bubbles", "idea.": "ideas", "code.": "coding",
    "desktop.": "desktop", "roarboot.": "roarboot", "research.": "zeroclaw",
    "minibook.": "minibook", "schedule.": "schedule",
}
```

## BrowserView Mutual Exclusion

All 4 BrowserView managers (Dashboard, Rowboat, SweDesign, ClawPort) are mutually exclusive. When any view is shown, all others are hidden:

```javascript
// In each show-* handler:
if (dashboardManager && dashboardManager.getIsVisible()) dashboardManager.hide();
if (rowboatManager && rowboatManager.getIsVisible()) rowboatManager.hide();
if (sweDesignManager && sweDesignManager.getIsVisible()) sweDesignManager.hide();
if (clawportManager && clawportManager.getIsVisible()) clawportManager.hide();
```

## Renderer

### `index.html` (127KB)

The main HTML entry point for the renderer process. Contains:

- Three.js canvas container
- UI panels for bubbles, ideas, and tools
- Modal dialogs for exploration, formatting, and settings
- Script and style imports
- Dashboard tab button for ClawPort navigation

### `multiverse.js` (106KB)

The core 3D rendering engine. Built on Three.js, it renders:

- The 3D multiverse space with navigable bubbles
- Bubble hierarchies with parent/child relationships
- Camera controls and navigation
- Animations and transitions between spaces

### `universe_canvas.js` (50KB)

Canvas management and interaction layer. Handles:

- Mouse/touch input processing
- Bubble selection and interaction
- Drag-and-drop operations
- Context menus

### `rich_content_renderer.js` (63KB)

Renders rich content within bubbles and ideas. Supports:

- Structured content (action lists, tables, timelines)
- Markdown rendering
- Code syntax highlighting
- Embedded media

### `shuttle_manager.js` (49KB)

Manages the shuttle pipeline UI in the renderer. Displays:

- Pipeline stages and progression
- Evaluation results
- Promotion controls
- Stage history

### `exploration_dialog.js` (24KB)

UI for the idea exploration feature. Provides:

- Exploration session management
- Clarification dialogs
- Connection visualization
- Journal view for idea evolution

### `glass_bubbles.js`

3D glass bubble rendering with Three.js. Creates the visual bubble objects with:

- Glass material and refraction effects
- Label rendering
- Size and color coding
- Animation states

### `styles.css` (67KB)

Application-wide styling including:

- 3D canvas layout
- Panel and dialog styles
- Responsive design
- Theme and color definitions
- Animation keyframes

## Build Commands

```bash
cd electron-app

# Development
npm start                    # Start in development mode

# Dashboard development (hot-reload)
npm run dashboard:dev        # Start Vite dev server for ClawPort dashboard

# Build dashboard (required before production builds)
npm run dashboard:build      # Build ClawPort dashboard to dashboard/dist/

# Production builds (auto-builds dashboard first)
npm run build:win            # Windows installer (.exe)
npm run build:mac            # macOS DMG
npm run build:linux          # Linux AppImage

# Debug
./launch_debug.bat           # Windows debug with CDP port 9222
./launch_electron.bat        # Windows production launch
```

## Startup Scripts

- **`start_vibemind_debug.bat`** (project root) -- Launches with Chrome DevTools Protocol on port 9222 for remote debugging.
- **`start_vibemind_production.bat`** (project root) -- Launches in headless/production mode.
