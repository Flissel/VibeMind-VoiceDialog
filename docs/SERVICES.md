# VibeMind Services – Vollständiges Inventar

Alle Services, die beim Start der Applikation gestartet werden können.
Ziel: Beim Stop der Applikation müssen **alle** sauber heruntergefahren werden.

**Gesamt: 80+ Services/Ressourcen in 14 Kategorien**

---

## 1. Electron-Layer

| # | Service | Gestartet in | Methode | Port | Shutdown | Status |
|---|---------|-------------|---------|------|----------|--------|
| 1 | **Python Backend** | `electron-app/main.js:235` | `spawn(python, [electron_backend.py])` | stdin/stdout | `pythonProcess.kill()` in `will-quit` | OK |
| 2 | **Main BrowserWindow** | `electron-app/main.js:154` | `new BrowserWindow()` | – | `mainWindow.close()` / `app.quit()` | OK |
| 3 | **ClawPort Dashboard** | `electron-app/clawport-manager.js` | BrowserView (React/Vite) | – | `clawportManager.destroy()` in `will-quit` | OK |
| 4 | **Brain Dashboard** | `electron-app/brain-manager.js` | BrowserView + Python FastAPI subprocess | 5000–5002 | `brainManager.destroy()` → `process.kill()` | LÜCKE |
| 5 | **SWE Design Dashboard** | `electron-app/swe-design-manager.js` | BrowserView + Python aiohttp subprocess | 8086–8088 | `sweDesignManager.destroy()` → `process.kill()` | LÜCKE |
| 6 | **Rowboat BrowserView** | `electron-app/rowboat-manager.js` | BrowserView (submodule bundle) | – | `rowboatManager.destroy()` | OK |

---

## 2. Python Daemon Threads (in `electron_backend.py __init__`)

| # | Thread | Gestartet in | Funktion | Shutdown | Status |
|---|--------|-------------|----------|----------|--------|
| 7 | **Rowboat Sync** | `electron_backend.py:360` | Synct Ideas/Bubbles nach Rowboat MongoDB | daemon=True (stirbt mit Prozess) | LÜCKE |
| 8 | **Embedding Preloader** | `electron_backend.py:375` | Lädt sentence-transformers Modell in RAM/GPU | daemon=True | LÜCKE |
| 9 | **Roarboot Autoconnect** | `electron_backend.py:474` | Health-Check alle 60s, kann Docker starten | daemon=True (Endlosloop) | LÜCKE |
| 10 | **Automation UI Auto-start** | `electron_backend.py:497` | Startet FastAPI Backend (Port 8007) per Subprocess | daemon=True | LÜCKE |
| 11 | **Rowboat Update Checker** | `electron_backend.py:481` | Pollt GitHub für Rowboat-Updates | daemon=True | LÜCKE |
| 12 | **Minibook Poller** | `electron_backend.py:1329` | Pollt Minibook für neue Nachrichten | daemon=True | LÜCKE |
| 13 | **Minibook Responder** | `electron_backend.py:1350` | Verarbeitet Minibook Antworten | daemon=True | LÜCKE |
| 14 | **stdin Reader** | `electron_backend.py:3017` | Liest JSON-Messages von Electron IPC | daemon=True | OK |

> **Problem:** Alle Daemon-Threads verlassen sich auf `daemon=True` – kein `join()`, kein graceful shutdown. Subprocess von #10 (Automation UI) wird nie explizit gekillt.

---

## 3. Python Async Init Tasks (in `electron_backend.py`)

| # | Task | Gestartet in | Funktion | Shutdown | Status |
|---|------|-------------|----------|----------|--------|
| 15 | **Prewarm Orchestrator** | `electron_backend.py:1189` | Intent-Classifier vorwärmen | Einmalig, beendet sich | OK |
| 16 | **Init Voice Bridge** | `electron_backend.py:1195` | OpenAI Realtime + Rachel starten | VoiceBridge.shutdown() | LÜCKE – kein Timeout |
| 17 | **Init Minibook** | `electron_backend.py:1201` | MinibookHub registrieren | – | OK |
| 18 | **Init Schedule** | `electron_backend.py:1207` | APScheduler starten, Tasks aus DB laden | scheduler.shutdown() | OK |
| 19 | **Init Messaging Bridge** | `electron_backend.py:1214` | Messaging-Bridge für Desktop Space | – | LÜCKE – kein Cleanup |

---

## 4. Python Async Runtime Tasks (Voice/Swarm)

| # | Service | Gestartet in | Methode | Shutdown | Status |
|---|---------|-------------|---------|----------|--------|
| 20 | **OpenAI Realtime Voice** | `python/voice/openai_realtime.py` | `asyncio.create_task(_event_loop, _audio_send_loop)` | `disconnect()` mit 5s Timeout | OK |
| 21 | **Audio Manager** | `python/voice/audio_manager.py` | sounddevice Streams + ThreadPoolExecutor | `cleanup()` + `__del__()` | OK |
| 22 | **Voice Bridge V2** | `python/swarm/voice_bridge_v2.py` | Async orchestration loop | `shutdown()` stoppt Sub-Services | LÜCKE – kein Timeout |
| 23 | **Intent Orchestrator** | `python/swarm/orchestrator/intent_orchestrator.py` | Sync/Async je nach Caller | Wird mit Voice Bridge gestoppt | OK |
| 24 | **Event Bus (Redis)** | `python/swarm/event_bus.py` | Redis-Connection + Listener Tasks | `close()` → setzt `_redis = None` | LÜCKE – kein disconnect() |
| 25 | **Backend Agent Pool** (8 Agents) | `python/swarm/backend_agents/agent_pool.py` | `asyncio.create_task(_process_loop)` | `stop()` setzt `_running = False` | LÜCKE – keine Resource-Cleanup |
| 26 | **Status Listener** | `python/swarm/listeners/status_listener.py` | `asyncio.create_task` | `_running = False` | OK |
| 27 | **Question Listener** | `python/swarm/listeners/` | `asyncio.create_task` | `_running = False` | OK |
| 28 | **TTS Queue** | `python/swarm/tts_queue.py` | `asyncio.create_task` | Cancel Task | LÜCKE – Buffer nicht geflusht |
| 29 | **APScheduler** | `python/spaces/schedule/workers/schedule_worker.py` | `AsyncIOScheduler` | `scheduler.shutdown(wait=False)` | OK |
| 30 | **Stream Listener Dispatcher** | `python/swarm/stream_listener/dispatcher.py:108` | `asyncio.gather()` Fan-out zu 8+ Listenern | Wird mit Bridge gestoppt | OK |

### Die 13 Backend Agents

| Agent | Stream | Datei |
|-------|--------|-------|
| BubblesAgent | `events:tasks:bubbles` | `python/spaces/ideas/agents/bubbles_agent.py` |
| IdeasAgent | `events:tasks:ideas` | `python/spaces/ideas/agents/ideas_agent.py` |
| CodingAgent | `events:tasks:coding` | `python/spaces/coding/agents/coding_agent.py` |
| DesktopAgent | `events:tasks:desktop` | `python/spaces/desktop/agents/desktop_agent.py` |
| RoarbootAgent | `events:tasks:roarboot` | `python/spaces/rowboat/agents/roarboot_agent.py` |
| ZeroClawAgent | `events:tasks:zeroclaw` | `python/spaces/research/agents/zeroclaw_research_agent.py` |
| MinibookAgent | `events:tasks:minibook` | `python/spaces/minibook/agents/minibook_agent.py` |
| ScheduleAgent | `events:tasks:schedule` | `python/spaces/schedule/agents/schedule_agent.py` |
| N8nBackendAgent | `events:tasks:n8n` | `python/spaces/n8n/agents/n8n_agent.py` |
| AgentFarmBackendAgent | `events:tasks:agentfarm` | `python/spaces/autogen/agents/agentfarm_agent.py` |
| VideoBackendAgent | `events:tasks:video` | `python/spaces/video/agents/video_agent.py` |
| MiroFishBackendAgent | `events:tasks:mirofish_pred` | `python/spaces/mirofish/agents/mirofish_agent.py` |
| FlowzenAgent | via submodule | `python/spaces/flowzen/agents/flowzen_agent.py` |

---

## 5. Stream Listeners (Optional, via Dispatcher)

| # | Service | Datei | Shutdown |
|---|---------|-------|----------|
| 31 | Conversational Listener | `python/swarm/stream_listener/listeners/conversational_listener.py` | Stop flag |
| 32 | Shuttles Listener | `python/swarm/stream_listener/listeners/shuttles_listener.py` | Stop flag |
| 33 | Minibook Listener | `python/swarm/stream_listener/listeners/minibook_listener.py` | Stop flag |
| 34 | Research Listener | `python/swarm/stream_listener/listeners/research_listener.py` | Stop flag |
| 35 | Roarboot Listener | `python/swarm/stream_listener/listeners/roarboot_listener.py` | Stop flag |
| 36 | Desktop Listener | `python/swarm/stream_listener/listeners/desktop_listener.py` | Stop flag |
| 37 | Coding Listener | `python/swarm/stream_listener/listeners/coding_listener.py` | Stop flag |
| 38 | Ideas Listener | `python/swarm/stream_listener/listeners/ideas_listener.py` | Stop flag |

---

## 6. Worker Processes

| # | Service | Datei | Methode | Shutdown | Status |
|---|---------|-------|---------|----------|--------|
| 39 | **Claude Worker** | `python/workers/claude_worker.py` | TaskQueue Consumer | SIGINT/SIGTERM Handler | OK |
| 40 | **Browser Worker** | `python/tools/browser_worker.py` | Playwright (on-demand) | `close()` → Browser schließen | OK |
| 41 | **Knowledge Worker** | `python/workers/knowledge_worker.py` | Background Worker | SIGINT/SIGTERM Handler | OK |
| 42 | **Rewrite Worker** | `python/workers/rewrite_worker.py` | Background Worker | SIGINT/SIGTERM Handler | OK |
| 43 | **Summarization Worker** | `python/workers/summarization_worker.py` | Background Worker | SIGINT/SIGTERM Handler | OK |
| 44 | **Worker Queue** | `python/tools/worker_queue.py` | Task/Report Queue | – | LÜCKE – keine stop() Methode |
| 45 | **ZeroClaw Research** | Via VoiceBridgeV2 | Subprocess | Kill on Bridge shutdown | OK |
| 46 | **ZeroClaw Process Manager** | `python/swarm/zeroclaw/process_manager.py:107` | `subprocess.Popen` + Health-Poll | Kill subprocess | OK |

---

## 7. Subprocesses (von Python gestartet)

| # | Service | Gestartet in | Port | Shutdown | Status |
|---|---------|-------------|------|----------|--------|
| 47 | **Automation UI Backend** | `electron_backend.py:520` | 8007 | `self._automation_ui_proc` gespeichert | LÜCKE – nie gekillt |
| 48 | **Hand Tracking Server** | `python/scripts/hand_tracking_server.py` | 8765 | WebSocket close | Optional, manuell |

---

## 8. Docker Container

| # | Service | Docker Compose | Ports | Gestartet | Shutdown | Status |
|---|---------|---------------|-------|-----------|----------|--------|
| 49 | **Minibook Backend** | `docker-compose.minibook.yml` | 3480 | `start_vibemind_*.bat` | `docker compose down` | LÜCKE – kein Stop in Electron |
| 50 | **Minibook Frontend** | `docker-compose.minibook.yml` | 3481 | `start_vibemind_*.bat` | `docker compose down` | LÜCKE – kein Stop in Electron |
| 51 | **Coding Engine API** | `Coding_engine/.../docker-compose.dashboard.yml` | 8000 | `dockerManager.startEngine()` | `dockerManager.stopEngine()` | OK |
| 52 | **Coding Engine PostgreSQL** | (gleiche Compose) | 5433 | mit Engine | mit Engine | OK |
| 53 | **Coding Engine Redis** | (gleiche Compose) | 6380 | mit Engine | mit Engine | OK |
| 54 | **Coding Engine Worker** | (gleiche Compose) | – | mit Engine | mit Engine | OK |
| 55 | **Project Preview Container** | Dynamisch pro Projekt | VNC 6200+, App 3001+ | `dockerManager.startProjectContainer()` | `stopAllContainers()` in `before-quit` | OK |
| 56 | **Claude Runner** | Einzelcontainer | VNC dynamisch | `dockerManager.startClaudeRunner()` | `stopClaudeRunner()` in `stopAllContainers()` | OK |
| 57 | **Code Generation Process** | Innerhalb Container | – | `spawn(python, [run_engine.py])` | Process kill + Container remove | OK |

### Automation_ui Docker Stack (optional, Desktop Space)

| # | Service | Port | Funktion |
|---|---------|------|----------|
| 58 | Frontend (React/Vite) | 5173 | Desktop Streaming UI |
| 59 | Backend (FastAPI) | 8007 | Automation API |
| 60 | OCR Engine | 8008 | Texterkennung |
| 61 | PostgreSQL | 5432 | Datenbank |
| 62 | Redis | 6379 | Cache/PubSub |
| 63 | Qdrant (HTTP) | 6333 | Vektor-DB |
| 64 | Qdrant (gRPC) | 6334 | Vektor-DB gRPC |

---

## 9. Persistent Connections (HTTP/DB Clients)

| # | Client | Datei | Typ | Shutdown | Status |
|---|--------|-------|-----|----------|--------|
| 65 | **MongoDB Client** | `python/publishing/rowboat_mongo_publisher.py:61` | `MongoClient()` persistent | – | LÜCKE – kein close() |
| 66 | **httpx.Client (Automation UI)** | `python/spaces/desktop/automation_ui_client.py:50` | Sync HTTP, persistent | – | LÜCKE – kein close() |
| 67 | **httpx.AsyncClient (Ollama)** | `python/swarm/ollama_client.py:130` | Async HTTP | – | LÜCKE – kein close() |
| 68 | **aiohttp.ClientSession (ZeroClaw)** | `python/swarm/zeroclaw/client.py:72` | Async HTTP | – | LÜCKE – kein close() |
| 69 | **aiohttp.ClientSession (ZeroClaw Health)** | `python/swarm/zeroclaw/process_manager.py:174` | Health-Check Polling | – | LÜCKE – kein close() |
| 70 | **httpx.Client (Summary Tools)** | `python/spaces/ideas/tools/summary_tools.py` | Mehrere Instanzen pro LLM-Call | Kurzlebig (per-call) | OK |
| 71 | **SQLite Connection** | `python/data/database.py:636` | Context-Manager pro Query | `close()` vorhanden | OK |
| 72 | **Redis Connection** | `python/tools/task_status_tools.py:30` | Lazy `redis.Redis()` | – | LÜCKE – kein close() |

---

## 10. Resource Holders (RAM/GPU/Files)

| # | Resource | Datei | Typ | Shutdown | Status |
|---|----------|-------|-----|----------|--------|
| 73 | **Embedding Model** | `python/data/embedding_service.py` | sentence-transformers in RAM/GPU | – | LÜCKE – kein Unload |
| 74 | **DroPE SmallLM Model** | `python/swarm/orchestrator/reference_resolver.py:49` | transformers Model (wenn USE_DROPE_RESOLVER) | – | LÜCKE – kein Unload |
| 75 | **Embedding ThreadPoolExecutor** | `python/data/embedding_service.py:72` | `ThreadPoolExecutor(max_workers=1)` | – | LÜCKE – kein shutdown() |
| 76 | **Voice ThreadPoolExecutor** | `python/voice/openai_realtime.py` | `ThreadPoolExecutor(max_workers=8)` | – | LÜCKE – kein shutdown() |
| 77 | **Space Logger FileHandlers** | `python/swarm/logging/space_logger.py:218` | `logging.FileHandler()` pro Space | – | LÜCKE – bleiben offen |

---

## 11. Externe Services (nicht von VibeMind verwaltet)

| # | Service | Port | Konfiguration | Benötigt |
|---|---------|------|---------------|----------|
| 78 | **MoireServer** (OCR) | 8766 | `start_vibemind_*.bat` | Optional |
| 79 | **Redis Server** | 6379 | Extern oder Docker | Nur wenn `FORCE_SYNC_MODE=false` |
| 80 | **Rowboat** | 3000 | `rowboat/docker-compose.yml` | Optional |
| 81 | **MongoDB** | 27017 | `ROWBOAT_MONGODB_URI` | Optional (Rowboat Publishing) |
| 82 | **OpenAI Realtime API** | 443 (WSS) | `OPENAI_API_KEY` | Ja (Voice) |
| 83 | **Supermemory API** | Cloud | `SUPERMEMORY_API_KEY` | Optional |
| 84 | **ZeroClaw Binary** | 42618 | `USE_ZEROCLAW=true` | Optional |

---

## 12. File Watchers & Timers

| # | Service | Datei | Shutdown |
|---|---------|-------|----------|
| 85 | Rowboat Workspace Watcher | `rowboat-services.cjs` | `stopWorkspaceWatcher()` in `will-quit` |
| 86 | Rowboat Runs Watcher | `rowboat-services.cjs` | `stopRunsWatcher()` in `will-quit` |
| 87 | Rowboat Services Watcher | `rowboat-services.cjs` | `stopServicesWatcher()` in `will-quit` |

---

## 13. Port-Übersicht

| Port | Service | Typ |
|------|---------|-----|
| 3000 | Rowboat | Docker |
| 3001–3020 | App Previews (dynamisch) | Docker |
| 3480 | Minibook Backend | Docker |
| 3481 | Minibook Frontend | Docker |
| 5000–5002 | Brain (Tahlamus) FastAPI | Subprocess |
| 5173 | Automation_ui Frontend | Docker |
| 5432 | PostgreSQL (Automation_ui) | Docker |
| 5433 | PostgreSQL (Coding Engine) | Docker |
| 6200–6219 | VNC Previews (dynamisch) | Port Allocator |
| 6333 | Qdrant HTTP | Docker |
| 6334 | Qdrant gRPC | Docker |
| 6379 | Redis (Event Bus / Automation_ui) | Extern/Docker |
| 6380 | Redis (Coding Engine) | Docker |
| 8000 | Coding Engine API | Docker |
| 8007 | Automation_ui Backend | Docker/Subprocess |
| 8008 | OCR Engine | Docker |
| 8086–8088 | SWE Design Dashboard | Subprocess |
| 8765 | Hand Tracking Server | Subprocess |
| 8766 | MoireServer | Extern |
| 9223 | Electron DevTools CDP | Electron |
| 27017 | MongoDB (Rowboat) | Extern |
| 42618 | ZeroClaw | Subprocess |

---

## 14. Shutdown-Sequenz (Ist-Zustand)

```
1. User schließt Electron / app.quit()

2. before-quit:
   └── dockerManager.stopAllContainers()
       ├── Alle project-* Container: docker rm -f
       └── claude-runner: docker rm -f

3. will-quit:
   ├── pythonProcess.kill()
   ├── Rowboat Watchers stoppen (3x)
   ├── clawportManager.destroy()
   ├── brainManager.destroy() → process.kill()
   ├── sweDesignManager.destroy() → process.kill()
   └── rowboatManager.destroy()

4. Python Process Termination (durch kill):
   ├── VoiceBridgeV2.shutdown()
   │   ├── TTS Queue stoppen
   │   ├── 13 Backend Agents stoppen
   │   ├── ZeroClaw stoppen
   │   ├── Status Listener stoppen
   │   ├── Question Listener stoppen
   │   └── Event Bus schließen
   ├── Voice Session disconnect
   │   ├── Audio Streams stoppen
   │   ├── WebSocket schließen
   │   └── Tasks canceln
   └── Database Connection schließen

5. NICHT gestoppt (Gaps):
   ├── 7 Daemon Threads (verlassen sich auf daemon=True)
   ├── Automation UI Subprocess (Port 8007)
   ├── MongoDB Client (rowboat_mongo_publisher)
   ├── httpx/aiohttp Clients (4+ Instanzen)
   ├── ThreadPoolExecutors (2x, nie shutdown())
   ├── Embedding/DroPE Models (RAM/GPU)
   ├── Space Logger FileHandlers
   ├── Redis Connection (task_status_tools)
   ├── Minibook Docker Container (3480/3481)
   └── MoireServer (Port 8766)
```

---

## 15. Shutdown-Lücken (Gaps)

| # | Lücke | Datei | Problem | Empfehlung |
|---|-------|-------|---------|------------|
| 1 | **EventBus Redis** | `event_bus.py:440` | `_redis = None` ohne `disconnect()` | `await _redis.close()` vor Reset |
| 2 | **Backend Agents** | `base_agent.py:471` | `stop()` setzt nur Flag | Resource-Cleanup in `stop()` |
| 3 | **Worker Queue** | `worker_queue.py` | Keine `stop()`/`cleanup()` Methode | `stop()` Methode hinzufügen |
| 4 | **Brain Server** | `brain-manager.js:312` | `process.kill()` ohne graceful shutdown | SIGTERM senden, dann Timeout + kill |
| 5 | **SWE Design Server** | `swe-design-manager.js` | `process.kill()` ohne graceful shutdown | SIGTERM senden, dann Timeout + kill |
| 6 | **VoiceBridge Shutdown** | `electron_backend.py:1806` | Kein Timeout-Wrapper | `asyncio.wait_for(shutdown(), timeout=10)` |
| 7 | **TTS Queue** | `tts_queue.py:151` | Buffer nicht geflusht vor Cancel | Queue leeren vor Task-Cancel |
| 8 | **Memory Services** | Memory-Module | Keine `close()` Methode | Shutdown-Hook für HTTP-Clients |
| 9 | **Minibook Docker** | `start_vibemind_*.bat` | Wird per Bat gestartet, kein Stop in Electron | `docker compose down` in `before-quit` |
| 10 | **MoireServer** | `start_vibemind_*.bat` | Extern gestartet, kein Stop-Mechanismus | Port-Check + Process-Kill bei Quit |
| 11 | **Daemon Threads** | `electron_backend.py:360–497` | 7 Threads nur daemon=True, kein join() | Stop-Flags + join(timeout=2) |
| 12 | **Automation UI Subprocess** | `electron_backend.py:520` | `_automation_ui_proc` nie gekillt | `proc.terminate()` in Cleanup |
| 13 | **MongoDB Client** | `rowboat_mongo_publisher.py:61` | `MongoClient()` ohne `close()` | `client.close()` bei Shutdown |
| 14 | **httpx/aiohttp Clients** | Diverse (4+ Dateien) | Persistent Clients ohne close() | `close()` / `__aexit__` |
| 15 | **ThreadPoolExecutors** | `embedding_service.py:72`, `openai_realtime.py` | Nie `shutdown()` aufgerufen | `executor.shutdown(wait=False)` |
| 16 | **Space Logger FileHandlers** | `space_logger.py:218` | FileHandler bleiben offen | `handler.close()` bei Shutdown |
| 17 | **Redis (task_status)** | `task_status_tools.py:30` | Lazy Redis ohne close() | `close()` bei Shutdown |
| 18 | **Messaging Bridge** | `electron_backend.py:1214` | Init ohne Cleanup-Pendant | Cleanup-Methode ergänzen |

---

## 16. Umgebungsvariablen für Service-Steuerung

| Variable | Default | Steuert |
|----------|---------|---------|
| `FORCE_SYNC_MODE` | `true` | Redis-basierte Async-Execution aus |
| `USE_VOICE_BRIDGE_V2` | `false` | Async Voice Bridge |
| `MINIBOOK_ENABLED` | `false` | Minibook Docker Stack |
| `SCHEDULE_ENABLED` | `false` | APScheduler |
| `USE_ZEROCLAW` | `false` | ZeroClaw Research |
| `USE_TASK_MEMORY` | `true` | Task Memory Service |
| `USE_CONVERSATION_MEMORY` | `true` | Conversation Memory |
| `USE_RAG_CLASSIFIER` | `true` | Semantic Classification |
| `USE_DROPE_RESOLVER` | `false` | Reference Resolution + SmallLM Model |
| `FAST_STARTUP` | `true` | Supermemory API beim Start |
| `ROWBOAT_PUBLISH_ENABLED` | `true` | Rowboat Knowledge Graph |
| `ROWBOAT_ENABLED` | `false` | Rowboat Autoconnect Health-Check |
| `SPACE_LOG_FILES` | `false` | Per-Space FileHandler Logging |
