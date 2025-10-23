# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Voice Dialog** is a multi-agent AI system with advanced desktop interaction capabilities. It combines:
- Multi-agent orchestration (voice, desktop, research, code agents)
- High-precision desktop element detection (398 icons/elements via MoireTracker)
- Visual feedback system (moiré overlay patterns)
- Windows shared memory IPC for real-time desktop analysis
- Audio-reactive visual simulation (C++/OpenGL + Python via pybind11)

The system enables AI agents to see and interact with the desktop through MoireTracker, a separate C++ application that provides sub-pixel mouse tracking and comprehensive screen element detection.

## Architecture

### Two-Component System

1. **MoireTracker** (C++ Windows application)
   - Location: `C:\Users\User\Desktop\Moire\`
   - Provides: Desktop scanning, mouse tracking, visual overlay
   - Communication: Windows shared memory IPC
   - Must be running for enhanced desktop features

2. **Voice Dialog** (Python multi-agent system)
   - Location: `C:\Users\User\Desktop\voice_dialog\`
   - Coordinates AI agents for desktop tasks
   - Connects to MoireTracker via IPC client

### Agent Architecture

```
AgentOrchestrator
    ├── VoiceOrchestratorAgent (routing/delegation)
    ├── DesktopAgent (screen analysis, MoireTracker integration)
    ├── ResearchAgent (web search, information gathering)
    └── CodeAgent (code analysis, generation)
```

**Key Components:**

- `agent_orchestrator.py`: Main entry point, manages MoireTracker service lifecycle
- `agents/desktop_agent.py`: Enhanced with MoireTracker for 398-element desktop detection
- `tools/moire_client.py`: IPC client using Windows shared memory (mmap)
- `tools/moire_service.py`: Auto-start/stop MoireTracker.exe
- `tools/moire_types.py`: Data structures matching C++ IPC protocol
- `config.py`: Production configuration management with environment variables
- `logger.py`: Structured logging with rotation
- `ipc_auth.py`: Secure IPC authentication tokens
- `health_server.py`: HTTP health check endpoints for monitoring

### IPC Protocol (Critical Implementation Detail)

Communication with MoireTracker uses Windows named shared memory with **8-byte struct alignment**:

**Memory Regions:**
- `MoireTracker_Commands` (4KB): Send commands
- `MoireTracker_Responses` (4MB): Receive results
- `MoireTracker_MouseStream` (21KB): Real-time mouse data

**Struct Padding Rules (MUST follow):**
- Response header: 32 bytes (not 24) - includes padding after uint32 fields
- MousePosition: 24 bytes (not 20) - 4-byte padding before uint64 timestamp
- DesktopElement: 436 bytes (not 433) - 3-byte padding after bool clickable
- element_count: Add 4 bytes padding after to align array

**Format strings:**
```python
# Response header
struct.unpack('I4xQI4xQ', data[:32])  # cmd_type, request_id, status, timestamp

# MousePosition
struct.unpack('fff4xQ', data[32:56])  # x, y, confidence, timestamp

# Element count (uint32) followed by 4-byte padding before array
```

## Common Commands

### Environment Setup

**First-time setup:**
```bash
cd C:\Users\User\Desktop\voice_dialog

# Copy environment template
copy .env.template .env

# Edit .env and add your OpenAI API key
notepad .env
```

**Install Python dependencies:**
```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### Running the System

**Start MoireTracker (required for desktop features):**
```bash
cd C:\Users\User\Desktop\Moire\build\Release
MoireTracker.exe
```

**Run agent system:**
```bash
cd C:\Users\User\Desktop\voice_dialog\python
python agent_orchestrator.py
```

**Run with health monitoring:**
```bash
python integrated_health.py  # Runs agent orchestrator with HTTP health server
```

**Run end-to-end integration test:**
```bash
cd C:\Users\User\Desktop\voice_dialog\python
python tests/test_end_to_end.py
```
This test validates:
- Auto-start MoireTracker
- Desktop element scanning (71+ elements)
- Mouse tracking
- Visual feedback (overlay toggle)
- Natural language commands
- Auto-shutdown

### Building MoireTracker

**Important:** MoireTracker uses a custom CMake located at `C:\Users\User\Desktop\Moire\tools\cmake-3.28.1-windows-x86_64\bin\cmake.exe`

```bash
cd C:\Users\User\Desktop\Moire

# Configure (only needed once or after CMakeLists.txt changes)
"C:\Users\User\Desktop\Moire\tools\cmake-3.28.1-windows-x86_64\bin\cmake.exe" -B build -G "Visual Studio 17 2022" -A x64

# Build
"C:\Users\User\Desktop\Moire\tools\cmake-3.28.1-windows-x86_64\bin\cmake.exe" --build build --config Release --target MoireTracker

# Output: build\Release\MoireTracker.exe
```

**Note:** If build fails with "LNK1104: Datei kann nicht geöffnet werden", MoireTracker.exe is still running:
```bash
powershell -Command "Get-Process MoireTracker -ErrorAction SilentlyContinue | Stop-Process -Force"
```

### Testing IPC Integration

**Quick connection test:**
```bash
cd C:\Users\User\Desktop\voice_dialog\python
python tests/test_mouse_pos.py  # Tests GET_MOUSE_POS
python tests/test_scan_only.py  # Tests desktop scanning
```

**Overlay toggle test:**
```bash
python tests/test_overlay_toggle.py  # Verify visual feedback persists
```

## Key Implementation Details

### MoireTracker Integration Checklist

When modifying IPC code, verify these critical points:

1. **Struct Alignment**: All structs must account for 8-byte alignment padding
2. **Offset Calculations**:
   - Response header starts at offset 8 (not 0)
   - Data follows header at offset 32 (header) + 24 (MousePosition) + 8 (element_count + padding)
3. **Memory Sizes**: Must match C++ definitions exactly (see `moire_client.py:27-40`)
4. **Security Attributes**: C++ creates shared memory with NULL DACL for cross-process access

### Desktop Agent Enhancement Pattern

The DesktopAgent automatically detects MoireTracker availability:

```python
self.moire = MoireTrackerClient()
self.moire_connected = self.moire.connect()

if self.moire_connected:
    # Enhanced mode: 398 desktop elements, high-precision mouse
    elements = await self.scan_desktop_elements()
else:
    # Fallback mode: Basic pyautogui
    x, y = pyautogui.position()
```

**Visual Feedback API:**
```python
await desktop_agent.set_visual_feedback(True)   # Show moiré overlay
await desktop_agent.set_visual_feedback(False)  # Hide overlay
```

### Service Lifecycle Management

The `MoireTrackerService` class handles automatic startup/shutdown:

```python
service = MoireTrackerService()
service.start()  # Starts MoireTracker.exe, waits 7s for initialization
# ... use desktop features ...
service.stop()   # Graceful shutdown
```

**Initialization timing:**
- Shared memory creation: ~2 seconds
- Desktop auto-scan: Triggers after 5 seconds
- **Total wait: 7 seconds** to ensure scan completes before IPC commands

### Common Pitfalls

1. **Unicode in Console Output**: Windows console (cp1252) cannot display UTF-8 checkmarks (✓, ✗). Use ASCII: `[OK]`, `[FAIL]`, `[WARN]`

2. **Response Timeout**: If `scan_desktop()` times out, MoireTracker may still be initializing. The service manager handles this automatically with 7-second wait.

3. **Empty Element Data**: If elements return with x=0, y=0, empty text, the desktop scan hasn't completed. Wait longer or trigger manual scan.

4. **Overlay Appears But Stays Blank**: The `moire_enabled_` flag in C++ must be true for rendering. IPC SET_ACTIVE command now sets this flag (fixed in `main.cpp:920-949`).

5. **Struct Unpack Errors**: Always check struct padding. Example: `struct.unpack('IQIQ', data[:24])` fails - needs `'I4xQI4xQ'` (32 bytes with padding).

## Project Structure

```
voice_dialog/
├── python/
│   ├── agent_orchestrator.py          # Main entry, MoireTracker lifecycle
│   ├── agents/
│   │   ├── voice_orchestrator.py      # Routes commands to specialized agents
│   │   ├── desktop_agent.py           # MoireTracker integration (398 elements)
│   │   ├── research_agent.py          # Web search capabilities
│   │   └── code_agent.py              # Code analysis
│   ├── tools/
│   │   ├── moire_client.py            # IPC client (shared memory)
│   │   ├── moire_service.py           # Auto-start/stop MoireTracker
│   │   └── moire_types.py             # Data structures for IPC
│   └── tests/
│       ├── test_end_to_end.py         # Full integration test (8 tests)
│       ├── test_overlay_toggle.py     # Visual feedback validation
│       ├── test_mouse_pos.py          # Mouse tracking test
│       └── test_scan_only.py          # Desktop scanning test
├── cpp/                               # Audio-reactive visual system (OpenGL)
│   ├── include/
│   │   ├── audio_reactive_sim.hpp
│   │   └── particle.hpp
│   └── src/
│       ├── audio_reactive_sim.cpp
│       └── bindings.cpp               # pybind11 Python bindings
├── shaders/                           # GLSL shaders for visuals
│   ├── particle.vert/frag
│   └── fisheye.vert/frag
├── CMakeLists.txt                     # Build C++ module
└── requirements.txt
```

## Testing Strategy

**Integration Test Coverage** (`test_end_to_end.py`):
1. Orchestrator auto-starts MoireTracker
2. DesktopAgent connects to IPC
3. Desktop scan (71+ elements detected)
4. Find element (by name search)
5. Mouse position tracking (high precision)
6. Visual feedback (overlay show/hide)
7. Natural language command processing
8. Orchestrator auto-stops MoireTracker

**Run all tests:**
```bash
cd python
python tests/test_end_to_end.py        # Full integration (8/8 tests)
python tests/test_overlay_toggle.py    # Visual feedback only
python tests/test_mouse_pos.py         # Mouse tracking only
```

## MoireTracker Configuration

MoireTracker settings are in `C:\Users\User\Desktop\Moire\build\Release\config.json`:

```json
{
  "grating": {
    "freq1_x": 0.200,
    "freq2_x": 0.20390625,
    "contrast": 0.30
  },
  "roi": {
    "width": 256,
    "height": 256
  }
}
```

Symbol definitions in `C:\Users\User\Desktop\Moire\config\symbols_config.json`.

**Desktop Scan Results:** Typically detects 71-398 elements depending on desktop state:
- OCR-detected text labels
- Visually detected icons (template matching)
- Window elements
- Desktop shortcuts

## Windows-Specific Notes

- **Shared Memory IPC**: Uses Windows `mmap` with named memory regions (not available on Linux/Mac)
- **Process Management**: `subprocess.CREATE_NO_WINDOW` flag for background MoireTracker
- **Console Encoding**: cp1252 requires ASCII symbols, not UTF-8
- **Build Tools**: Visual Studio 2022 required for MoireTracker C++ compilation

## Related Repositories

- **MoireTracker**: `C:\Users\User\Desktop\Moire\` (see `Moire/CLAUDE.md` for details)
  - High-performance DirectX 11 rendering
  - OCR-based desktop scanning
  - GPU-accelerated phase extraction
  - Sub-pixel mouse tracking (0.05 px RMS precision target)
