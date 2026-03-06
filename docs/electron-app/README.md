# Electron App

The Electron app is the desktop UI for VibeMind. It renders a 3D multiverse of bubbles and ideas using Three.js, manages the Python backend process, and integrates external tools via BrowserView embedding.

## Directory Structure

```
electron-app/
├── main.js                     # Main process: Python spawning, IPC routing (64KB)
├── preload.js                  # Context bridge for renderer security (12KB)
├── dashboard-manager.js        # Coding Engine Dashboard BrowserView integration
├── dashboard-preload.js        # Preload script for dashboard BrowserView
├── docker-manager.js           # Docker container management
├── port-allocator.js           # Dynamic port allocation for services
├── rowboat-manager.js          # Rowboat BrowserView embedding
├── rowboat-preload.js          # Preload script for Rowboat BrowserView
├── swe-design-manager.js       # Factory Space (SWE Design) BrowserView embedding
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
- **BrowserView Integration** -- Manages embedded views for Coding Engine Dashboard, Rowboat, and SWE Design.

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

## Renderer

### `index.html` (127KB)

The main HTML entry point for the renderer process. Contains:

- Three.js canvas container
- UI panels for bubbles, ideas, and tools
- Modal dialogs for exploration, formatting, and settings
- Script and style imports

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

# Production builds
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
