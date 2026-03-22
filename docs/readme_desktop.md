# Desktop.Space

**Intelligente Desktop-Kontexterkennung und -Automation mit Eye-Tracking, Messaging-Pipeline und Moire-Vision.**

## Overview

Desktop.Space gibt Vibemind Augen und Hände auf dem Desktop des Users. Der Space operiert über mehrere integrierte Systeme: Eye/Gaze-Tracking via Webcam (MediaPipe), Screen-Analyse, automatisierte Maus/Tastatur-Steuerung, und eine Messaging-Pipeline für Chat-Automation. Das eyeterm-Subsystem allein umfasst 15 Subdirectories.

## Backend-Agent: DesktopAgent (21 Events)

**Datei:** `python/spaces/desktop/agents/desktop_agent.py`

### Desktop-Operationen (7 Events)

| Event | Tool-Funktion | Beschreibung |
|-------|--------------|-------------|
| `desktop.open_app` | `open_app` | Anwendung öffnen |
| `desktop.click` | `click_element` | Element klicken |
| `desktop.type` | `type_text` | Text eingeben |
| `desktop.press_key` | `press_key` | Taste drücken |
| `desktop.screenshot` | `take_screenshot` | Screenshot erstellen |
| `desktop.scroll` | `scroll_screen` | Scrollen |
| `desktop.task` | `execute_desktop_task` | Desktop-Task ausführen |

### Task-Management (3 Events)

| Event | Tool-Funktion |
|-------|--------------|
| `desktop.task.create` | `create_task_node` |
| `desktop.task.update` | `update_task_status` |
| `desktop.task.list` | `get_task_list` |

### Moire Vision (2 Events)

| Event | Tool-Funktion |
|-------|--------------|
| `desktop.moire.scan` | `moire_scan` |
| `desktop.moire.find` | `moire_find_element` |

### Messaging / Clawdbot-Bridge (7 Events)

| Event | Tool-Funktion |
|-------|--------------|
| `messaging.whatsapp` | `send_whatsapp` |
| `messaging.telegram` | `send_telegram` |
| `messaging.send` | `send_message` |
| `web.search` | `web_search` |
| `web.fetch` | `web_fetch` |
| `openclaw.status` | `get_clawdbot_status` |
| `openclaw.notifications` | `get_notifications` |

### eyeterm-Steuerung (2 Events)

| Event | Tool-Funktion |
|-------|--------------|
| `desktop.eyeterm.toggle` | `eyeterm_toggle` |
| `desktop.eyeterm.calibrate` | `eyeterm_calibrate` |

## eyeterm-Subsystem (15 Directories)

Vollständiges Eye-Tracking-System unter `python/spaces/desktop/eyeterm/`:

| Directory | Zweck |
|-----------|-------|
| `vision/` | Gaze-Tracking (gaze.py 21.2KB), Wink-Detection (wink.py 4.8KB), PolynomialMapper (9.2KB), Camera, Calibrate |
| `action/` | Action-Execution |
| `ai/` | AI-basierte Entscheidungen |
| `audio/` | Audio-Integration |
| `claude/` | Claude-API Integration |
| `cursor/` | Gaze-to-Cursor Mapping |
| `editor/` | Editor-Integration |
| `models/` | Datenmodelle |
| `routing/` | Command-Routing |
| `screen/` | Screen-State-Analyse |
| `stream/` | Stream-Verarbeitung |
| `ui/` | UI-Rendering |
| `app.py` | Haupt-App (22.8KB) |
| `headless.py` | Headless-Modus (38.6KB) |
| `state.py` | State-Management (5.4KB) |

### Vision-Stack im Detail

- **gaze.py** (21.2KB): MediaPipe FaceMesh (478-Landmark Model), Iris-basiertes Gaze-Tracking, Head-Pose aus Nase/Ohren
- **wink.py** (4.8KB): Eye Aspect Ratio (EAR) Berechnung, Links=Confirm / Rechts=Cancel, 600ms Cooldown
- **polynomial_mapper.py** (9.2KB): Quadratische Gaze-to-Screen Koordinaten-Mapping, Click-Learning Kalibrierung, Adaptive Fusion (Iris+Head)

## Messaging-Pipeline

Vollständige Messaging-Verarbeitung unter `python/spaces/desktop/messaging/`:

| Datei | Zweck |
|-------|-------|
| `incoming_handler.py` (8.8KB) | Eingehende Nachrichten verarbeiten |
| `messaging_pipeline.py` (11.9KB) | Pipeline-Orchestrierung |
| `relevance_filter.py` (7.3KB) | Relevanz-Filterung |

## Key Components

| Komponente | Datei | Zweck |
|-----------|-------|-------|
| Backend-Agent | `agents/desktop_agent.py` | 21 Events → 19 Tools |
| Desktop-Tools | `tools/desktop_tools.py` | Maus/Tastatur-Automation |
| Task-Tools | `tools/task_tools.py` | Task-Node-Management |
| Moire-Tools | `tools/moire_tools.py` | MoireTracker Vision |
| Adapted Tools | `tools/adapted_desktop_tools.py` | Typisierte Wrapper |
| Automation UI | `Automation_ui/` (Submodul) | FastAPI Backend für Vision-Agents |

## Current Status

### Implementiert

- Eye/Gaze-Tracking via MediaPipe voll funktional (478-Landmark, Iris+Head)
- PolynomialMapper für Gaze-to-Screen Mapping (quadratisch, click-learning)
- Wink-Detection (EAR-basiert, Links/Rechts-Unterscheidung)
- Kamera-Integration und Kalibrierung
- 21 Events mit vollständigem Tool-Mapping
- Messaging-Pipeline mit Relevance-Filtering (WhatsApp, Telegram)
- Moire Tracker Vision-Integration
- Desktop-Automation (Maus, Tastatur, App-Steuerung)
- Task-Node-Management
- Automation UI (FastAPI Backend)
- eyeterm App mit 15 Subsystemen

- OCR-Engine für Text-Extraktion aus Screen-Captures
- Video-Agent für kontinuierliche Action-Verifizierung
- ML-basiertes Workflow-Learning (Eye-Tracking-Daten als Grundlage)
- Agent-Team für Screen-Validierung

## Roadmap

- Multi-monitor support and complex desktop layouts
- Privacy-preserving facial analysis (on-device processing)
- Erweiterte Workflow-Automation basierend auf gelernten User-Patterns
- Cross-Application Context-Sharing zwischen Desktop-Anwendungen

## Ecosystem-Fit

Desktop.Space ist Vibeminds Augen und Hände auf dem Computer des Users. Es liefert Kontext an Ideas.Space über den aktuellen Screen-Inhalt. Es erkennt User-Aktivitätsmuster für The Brain.Space. Es führt Aktionen aus, die andere Spaces orchestrieren. Es validiert, dass Deployments von Coding.Space korrekt funktionieren. Die gesamte Vibemind-Plattform wird kontextbewusst durch Desktop.Space.
