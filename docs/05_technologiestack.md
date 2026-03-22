# Technologiestack

---

## Uebersicht

```
+------------------+     +------------------+     +------------------+
| Frontend         |     | Backend          |     | Externe Engines  |
| Electron ^25     |<--->| Python 3.10+     |<--->| Coding_engine    |
| Three.js ^0.128  |     | SQLite (WAL)     |     | Rowboat (Docker) |
| electron-builder |     | Redis ^4.0       |     | ZeroClaw (Rust)  |
+------------------+     +------------------+     | Minibook API     |
                                                  | Automation_ui    |
                                                  +------------------+
```

---

## Frontend (Electron)

| Abhaengigkeit | Version | Zweck |
|--------------|---------|-------|
| electron | ^25.0.0 | Desktop-App Framework |
| electron-builder | ^24.0.0 | Multi-Platform Packaging (Win/Mac/Linux) |
| three | ^0.128.0 | 3D Multiverse Rendering |
| dotenv | ^17.3.1 | Environment Variablen |

**Build Targets:**
- Windows: NSIS Installer
- macOS: DMG
- Linux: AppImage

**Renderer-Dateien:**
- `multiverse.js` (104KB) — Kern-3D-Engine
- `shuttle_manager.js` (48KB) — Pipeline UI
- `universe_canvas.js` (49KB) — Canvas
- `rich_content_renderer.js` (61KB) — Rich Media
- `exploration_dialog.js` (24KB) — Research UI
- `glass_bubbles.js` — Bootstrap

---

## Backend (Python)

### Kern-Dependencies

| Paket | Version | Zweck |
|-------|---------|-------|
| python-dotenv | >=1.0.0 | Environment Management |
| numpy | >=1.24.0 | Numerische Berechnungen |

### Voice & Audio

| Paket | Version | Zweck |
|-------|---------|-------|
| openai | >=2.0.0 | OpenAI Realtime API (gpt-4o-realtime) — einziger Voice Provider |
| sounddevice | >=0.4.6 | Mikrofon-Input |
| librosa | >=0.10.0 | Audio-Analyse (optional) |

### AI/ML

| Paket | Version | Zweck |
|-------|---------|-------|
| sentence-transformers | >=2.2.0 | Semantische Embeddings |
| torch | >=2.0.0 | Deep Learning (DroPE) |
| transformers | >=4.35.0 | Hugging Face Modelle (DroPE-SmolLM) |
| accelerate | >=0.24.0 | GPU-Optimierung |

### Agent Framework

| Paket | Version | Zweck |
|-------|---------|-------|
| autogen-agentchat | ~0.4 | Multi-Agent System |
| autogen-core | >=0.4.0 | AutoGen Kern |
| autogen-ext[grpc,ollama] | >=0.4.0 | gRPC + Ollama Support |

### Datenbank & Messaging

| Paket | Version | Zweck |
|-------|---------|-------|
| sqlite3 | (builtin) | Lokale Datenbank (WAL Mode, Schema v13) |
| redis | >=4.0.0 | Event Streams (optional, nur fuer async Modus) |
| supermemory[aiohttp] | >=0.1.0 | Semantisches Gedaechtnis |

### Desktop Automation

| Paket | Version | Zweck |
|-------|---------|-------|
| pyautogui | >=0.9.0 | Tastatur/Maus-Kontrolle |
| pyperclip | >=1.8.0 | Clipboard-Zugriff |
| opencv-python | >=4.8.0 | Computer Vision |
| pytesseract | >=0.3.10 | OCR (Bildschirm lesen) |
| Pillow | >=10.0.0 | Bildverarbeitung |
| mediapipe | >=0.10.0 | Hand Motion Detection |

### Web & HTTP

| Paket | Version | Zweck |
|-------|---------|-------|
| httpx | >=0.27.0 | Async HTTP Client |
| requests | >=2.31.0 | HTTP Client |
| beautifulsoup4 | >=4.12.0 | HTML Parsing |
| websockets | >=12.0 | WebSocket Kommunikation |

### Optional (Visual System)

| Paket | Version | Zweck |
|-------|---------|-------|
| glfw | >=2.6.0 | OpenGL Window (C++ Modul) |
| pybind11 | >=2.11.0 | Python/C++ Binding |

---

## LLM-Provider

| Provider | Modell | Einsatz |
|----------|--------|---------|
| **Anthropic** | Claude Sonnet/Opus | Intent-Klassifikation, Tool-Orchestrierung |
| **OpenAI** | GPT-4o Realtime | Voice Session (Speech-to-Speech) |
| **OpenRouter** | Verschiedene | RAG-Klassifikation, Fallback |
| **Ollama** | Lokale Modelle | Relevance Filter (Messaging), DroPE |

**LLM-Konfiguration (Rowboat):**
Automatische Priorisierung: ANTHROPIC_API_KEY > OPENROUTER_API_KEY > OPENAI_API_KEY

---

## Externe Engines

### Coding_engine (Git Submodul)

| Eigenschaft | Wert |
|------------|------|
| Pfad | `python/spaces/coding/Coding_engine/` |
| Typ | Git Submodul |
| Agents | 40+ spezialisierte AutoGen Agents |
| Features | Society of Mind, Docker Sandbox, VNC Preview |
| Memory | Fungus Memory (RAG via Qdrant) |
| Dashboard | Eigene Dashboard-App |

### Rowboat (Git Submodul)

| Eigenschaft | Wert |
|------------|------|
| Pfad | `python/spaces/roarboot/rowboat/` |
| Typ | Git Submodul |
| Stack | Rowboat:3000, MongoDB:27017, Redis:6379, Qdrant:6333 |
| Integration | BrowserView in Electron, esbuild CJS Bundle |

### ZeroClaw

| Eigenschaft | Wert |
|------------|------|
| Typ | Rust Binary (Subprocess) |
| Pfad | Konfigurierbar via ENV |
| Features | Web Research, Scraping, Summarization |
| Aktivierung | `USE_ZEROCLAW=true` |

### Automation_ui (Git Submodul)

| Eigenschaft | Wert |
|------------|------|
| Pfad | `python/spaces/desktop/Automation_ui/` |
| Typ | Git Submodul |
| Features | Custom Desktop Automation Framework |
| Integration | `automation_ui_client.py` Bridge |

### Minibook API

| Eigenschaft | Wert |
|------------|------|
| URL | `http://localhost:3480` |
| Typ | Externe API |
| Features | Inter-Space Collaboration |
| Aktivierung | `MINIBOOK_ENABLED=true` |

### SWE Design Factory (Git Submodul)

| Eigenschaft | Wert |
|------------|------|
| Pfad | `python/spaces/shuttles/swe_desgine/` |
| Typ | Git Submodul |
| API | ArchitectTeam auf `localhost:8087` |
| Features | Requirements Pipeline, Spezifikationsgenerierung |

---

## DevOps & Infrastructure

### Docker

| Container | Port | Space |
|-----------|------|-------|
| Coding Sandbox | dynamisch | Coding |
| Rowboat | 3000 | Roarboot |
| MongoDB | 27017 | Roarboot |
| Redis (Rowboat) | 6379 | Roarboot |
| Qdrant | 6333 | Roarboot / Coding |
| ArchitectTeam | 8087 | Shuttles |
| Minibook | 3480 | Minibook |

### Electron Build Pipeline

```bash
# Development
cd electron-app && npm start

# Production Builds
npm run build:win    # Windows NSIS Installer
npm run build:mac    # macOS DMG
npm run build:linux  # Linux AppImage

# Rowboat Bundle
npm run build:rowboat  # esbuild CJS Bundle
```

### Debug Infrastructure

| Tool | Port | Zweck |
|------|------|-------|
| CDP Remote Debugging | 9223 | Electron DevTools |
| Debug Agent | — | Automatisches CDP Logging |
| MoireServer | 8766 | Desktop Automation |

---

## Datenbank

### SQLite Konfiguration

| Eigenschaft | Wert |
|------------|------|
| Datei | `python/vibemind.db` |
| Schema Version | 13 |
| WAL Mode | Aktiviert |
| Migrations | Automatisch in `database.py` |

### Tabellen

| Tabelle | Zweck |
|---------|-------|
| `ideas` | Bubbles und Ideen (parent_id fuer Hierarchie) |
| `projects` | Code-Generierungs-Projekte |
| `canvas_nodes` | Visuelle Knoten im 3D-Raum |
| `canvas_edges` | Verbindungen zwischen Knoten |
| `conversation_history` | Voice Dialog Nachrichten |
| `shuttles` | Requirements Pipeline Stages |
| `mermaid_diagrams` | Visualisierungs-Spezifikationen |

### Repository Pattern

```python
from data import IdeasRepository, CanvasRepository

ideas_repo = IdeasRepository()
idea = ideas_repo.create(title="Meine Idee")
ideas_repo.get_by_title_fuzzy("meine idee")  # Akzent-insensitiv
```

**Dateien:**
- `python/data/database.py` — Schema, Migrations, Verbindung
- `python/data/models.py` — Dataclasses
- `python/data/repository.py` — CRUD Operations
