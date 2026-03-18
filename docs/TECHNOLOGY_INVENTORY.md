# VibeMind — Technology Inventory

> Vollständige Technologie-Übersicht aller Spaces, Submodule und externen Projekte.
> Erstellt für AI Nation Grant Frage 2.6: "What technologies are you using—or plan to use—to build this product?"

---

## 1. Main VibeMind Backend (`python/`)

**Source:** `requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **AI/LLM** | `openai >=2.0.0` (Realtime API, GPT-4o), `sentence-transformers` (all-MiniLM-L6-v2, 384-dim), `torch`, `transformers`, `accelerate` |
| **Multi-Agent** | `autogen-agentchat ~=0.4`, `autogen-core >=0.4.0`, `autogen-ext[grpc,ollama] >=0.4.0` |
| **Voice** | `sounddevice`, `librosa` (Audio-Analyse) |
| **Computer Vision** | `mediapipe` (Hand Motion Detection), `opencv-python`, `pytesseract` (OCR) |
| **Desktop Automation** | `pyautogui`, `pyperclip` |
| **Web/HTTP** | `httpx`, `requests`, `beautifulsoup4`, `websockets` |
| **Database** | SQLite (stdlib), `redis`, `pymongo` |
| **Image** | `Pillow`, `numpy` |
| **3D/Graphics** | `glfw`, `pybind11` |
| **Scheduling** | `APScheduler` |
| **Memory** | `supermemory[aiohttp]` |
| **Config** | `python-dotenv` |

**Eigenentwicklung:**
- Intent Classification Pipeline (LLM-basiert, kein Keyword-Matching)
- 3-Stage Input Enhancement (CollectorAgent → IntentEnhancer → ExecutionValidator)
- DroPE Reference Resolution (SakanaAI/DroPE-SmolLM-135M-32K)
- RAG Intent Classifier (Supermemory + LLM)
- Event Router + Event Bus (Redis Streams / Sync-Fallback)
- BaseBackendAgent Framework (8 Domain-Agents)
- Notification Queue, Question Queue, System Context Store

---

## 2. Electron App + UI (`electron-app/`)

### 2a. Electron Main

**Source:** `electron-app/package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **Runtime** | `electron ^25.0.0` |
| **3D Rendering** | `three ^0.128.0` (Three.js — WebGL) |
| **Build** | `electron-builder ^24.0.0` |
| **Config** | `dotenv ^17.3.1` |

**Eigenentwicklung:**
- 3D Multiverse (10 navigierbare Szenen: Bubbles, Coding, Desktop, Brain, AgentFarm, etc.)
- Glass Bubble Rendering (Fresnel Shader, bloom, wireframe)
- Python IPC (stdin/stdout JSON, <100ms Latenz)
- BrowserView Mutual Exclusion (4 Manager: Dashboard, Rowboat, SweDesign, ClawPort)

### 2b. ClawPort Dashboard (`electron-app/dashboard/`)

**Source:** `dashboard/package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **UI** | `react ^19.1.0`, `react-dom ^19.1.0` |
| **Icons** | `lucide-react ^0.575.0` |
| **Build** | `vite ^6.3.0`, `typescript ~5.7.0`, `@vitejs/plugin-react` |

**4 Tabs:** Schedule Monitor, Agent Status, Chat Panel, Memory Browser

### 2c. ClawPort UI v2 (`electron-app/clawport-ui/`)

**Source:** `clawport-ui/package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **Framework** | `next 16.1.6` (Next.js) |
| **UI** | `react 19.2.3`, `radix-ui ^1.4.3`, `shadcn ^3.8.5` |
| **CSS** | `tailwindcss ^4`, `tw-animate-css` |
| **Flow** | `@xyflow/react ^12.10.1`, `@dagrejs/dagre ^2.0.4` |
| **AI** | `openai ^6.25.0` (routed to Claude) |
| **Utilities** | `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react` |
| **Test** | `vitest ^4.0.18`, `@testing-library/react ^16.3.2`, `jsdom` |

---

## 3. Ideas & Bubbles Space (`python/spaces/ideas/`)

**Source:** Imports aus `agents/`, `tools/`, `broadcast/`

| Kategorie | Technologien |
|-----------|-------------|
| **AI/LLM** | `openai` (via OpenRouter Multi-Model), `sentence-transformers` (Embedding-basierte Suche) |
| **Database** | SQLite via `IdeasRepository`, `CanvasRepository` |
| **Serialization** | `json` (stdlib) |

**Eigenentwicklung:**
- BubblesAgent (14 bubble.* Events)
- IdeasAgent (33 idea.* Events)
- Rachel Voice Agent (OpenAI Realtime, Speech-to-Speech)
- Auto-Linking (semantische Embedding-Distanz)
- Structured Formatting (Actionlists, Mindmaps, Pro/Con, SWOT, etc.)
- AI-Scientist Exploration (Tree-basierte Ideen-Exploration mit Scoring)
- Shuttle Pipeline Integration (bubble.evaluate → swe_design)

**Keine eigene requirements.txt** — nutzt Main VibeMind Dependencies.

---

## 4. Coding Space (`python/spaces/coding/`)

### 4a. Coding Agent (VibeMind-seitig)

**Source:** Imports aus `agents/coding_agent.py`, `tools/coding_tools.py`

| Kategorie | Technologien |
|-----------|-------------|
| **Subprocesses** | `subprocess` (CLI Aufrufe an Coding Engine) |
| **HTTP** | `httpx` (REST API calls) |

**9 code.* Events:** generate, status, preview, list, delete, stop, deploy, logs, explain

### 4b. Coding Engine (Submodul: `Coding_engine/`)

**Source:** `Coding_engine/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Web Framework** | `fastapi 0.109.2`, `uvicorn[standard]` |
| **AI/LLM** | `anthropic 0.40.0`, `claude-agent-sdk 0.1.0`, `openai` |
| **Multi-Agent** | `autogen-agentchat >=0.4.0`, `autogen-ext[mcp,openai]` |
| **Database** | `sqlalchemy 2.0.25`, `asyncpg`, `psycopg2-binary`, `redis`, `alembic` |
| **gRPC** | `grpcio >=1.60.0`, `grpcio-tools` |
| **Container** | `docker 7.0.0`, `kubernetes 28.1.0`, `kopf 1.37.2` (K8s Operator) |
| **Git** | `gitpython 3.1.41` |
| **Vector DB** | `qdrant-client 1.7.3` |
| **Memory** | `supermemory 3.20.0` |
| **Graph** | `networkx 3.2.1` (DAG Operations) |
| **Security** | `hvac 1.2.1` (HashiCorp Vault), `cyclonedx-python-lib` (SBOM) |
| **Logging** | `structlog 24.1.0` |
| **Retry** | `tenacity 8.2.3` |
| **CLI** | `click 8.1.7`, `rich 13.7.0` |
| **Templates** | `jinja2` |
| **System** | `psutil`, `aiofiles` |

### 4c. Coding Engine Dashboard (`Coding_engine/dashboard-app/`)

**Source:** `dashboard-app/package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **Runtime** | `electron ^28.3.3` |
| **UI** | `react ^18.2.0`, `lucide-react` |
| **State** | `zustand ^4.4.7` |
| **CSS** | `tailwindcss ^3.3.6` |
| **Build** | `electron-vite ^2.0.0`, `vite ^5.0.7`, `typescript ^5.3.3` |

### 4d. La Fungus Search (Semantic Code Search)

**Source:** `la_fungus_search/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Embeddings** | `sentence-transformers >=3.0.0`, EmbeddingGemma (lokales .safetensors Modell) |
| **Deep Learning** | `torch >=2.0.0`, `transformers >=4.35.0` |
| **Vector Search** | `faiss-cpu >=1.7.0`, `qdrant-client >=1.7.0` |
| **Text Search** | `rank-bm25 >=0.2.2`, `python-simhash` |
| **LLM** | `ollama >=0.1.0`, `llama-index >=0.9.0` |
| **ML** | `scikit-learn`, `scikit-learn-extra` |
| **Tokenization** | `sentencepiece` |
| **Graph** | `networkx >=3.0` |
| **UI** | `streamlit >=1.28.0`, `plotly >=5.0.0` |
| **Data** | `pandas`, `numpy`, `matplotlib` |
| **Git** | `gitpython` |

**La Fungus Search Frontend:** `react ^18.3.1`, `plotly.js-dist-min`, `react-plotly.js`, `axios`, `vite`, `@playwright/test`

### 4e. MCP Plugin Servers (18 Server)

**Source:** `Coding_engine/mcp_plugins/`

| Server | Technologie |
|--------|-------------|
| filesystem | MCP SDK |
| git | MCP SDK + gitpython |
| github | MCP SDK + GitHub API |
| postgres | MCP SDK + psycopg2 |
| redis | MCP SDK + redis |
| qdrant | MCP SDK + qdrant-client |
| supabase | MCP SDK + supabase |
| supermemory | MCP SDK + supermemory |
| brave-search | MCP SDK + Brave API |
| tavily | MCP SDK + Tavily API |
| playwright | MCP SDK + playwright |
| desktop | MCP SDK + pyautogui |
| fetch | MCP SDK + httpx |
| context7 | MCP SDK + Context7 API |
| n8n | MCP SDK + n8n API |
| npm | MCP SDK + npm CLI |
| docker | MCP SDK + docker SDK |
| time | MCP SDK |

**gRPC Host:** `grpcio`, `protobuf`, `psycopg2-binary`, `redis`, `docker`, `structlog`

---

## 5. Desktop Space (`python/spaces/desktop/`)

### 5a. Desktop Agent (VibeMind-seitig)

**Source:** Imports aus `agents/`, `tools/`, `adapted/`

| Kategorie | Technologien |
|-----------|-------------|
| **Automation** | `pyautogui` (Fallback), `moire_external` (MoireTracker v2 Bridge) |
| **HTTP** | `httpx` (Automation_ui REST API, Port 8007) |
| **WebSocket** | `websockets` (MoireServer, ws://localhost:8766) |
| **Multi-Agent** | `autogen_agentchat` (Desktop Swarm Agent) |
| **LLM** | `httpx` → OpenRouter (Relevance Filter) |

**19 desktop.* Events + messaging.* + web.* Events**

### 5b. Automation_ui Backend (Submodul)

**Source:** `Automation_ui/backend/requirements.txt` + weitere

| Kategorie | Technologien |
|-----------|-------------|
| **Web Framework** | `fastapi 0.104.1`, `uvicorn[standard]`, `starlette` |
| **OCR (3 Engines!)** | `pytesseract`, `easyocr`, `paddlepaddle 2.5.2` + `paddleocr 2.7.0.3` |
| **Computer Vision** | `opencv-python 4.6.0.66`, `opencv-python-headless`, `scikit-image` |
| **Desktop Automation** | `pyautogui 0.9.54`, `pynput` (Keyboard/Mouse Listener) |
| **Screenshots** | `Pillow`, `mss 9.0.1` (Fast Cross-Platform), `screeninfo` (Multi-Monitor) |
| **HTTP** | `httpx`, `requests`, `aiohttp` |
| **WebSocket** | `websockets 12.0` |
| **WebRTC** | `aiortc >=1.6.0` |
| **SSH** | `asyncssh 2.14.2`, `paramiko 3.4.0` |
| **MQTT** | `asyncio-mqtt 0.16.1` |
| **Database** | `redis`, `psycopg2-binary`, `asyncpg`, `sqlalchemy[asyncio]`, `alembic` |
| **Cloud DB** | `supabase >=2.0.0` |
| **Logging** | `loguru 0.7.2`, `structlog` |
| **JSON** | `orjson 3.9.10` |
| **PDF** | `pdf2image`, `PyPDF2` |
| **File Watch** | `watchdog 3.0.0` |
| **Retry** | `backoff 2.2.1` |
| **System** | `psutil 5.9.6` |
| **MCP** | `mcp >=1.0.0` |
| **Data** | `numpy`, `pandas` |
| **Config** | `pydantic`, `pydantic-settings`, `python-dotenv`, `pyyaml` |

### 5c. Automation_ui — AutoGen Service

**Source:** `Automation_ui/backend/autogen_service/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Multi-Agent** | `autogen-agentchat`, `autogen-ext`, `autogen-core`, `autogen-ext[video-surfer]` |
| **Video** | `ffmpeg-python`, `av` (VideoSurfer Agent) |
| **AI** | `openai` |
| **Cloud** | `supabase >=2.0.0` |
| **Validation** | `jsonschema` |

### 5d. Automation_ui — Moire Agents

**Source:** `Automation_ui/backend/moire_agents/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Multi-Agent** | `autogen-agentchat`, `autogen-ext[openai,grpc]`, `pyautogen` |
| **gRPC** | `grpcio`, `grpcio-tools`, `protobuf` |

### 5e. Automation_ui — Voice Module

**Source:** `Automation_ui/backend/moire_agents/voice/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **STT** | `openai` (Whisper API), `sounddevice` |
| **TTS** | `pyttsx3` (Offline), `edge-tts` (Microsoft Edge), `playsound` |
| **Intent** | `anthropic` (Claude API) |

### 5f. Automation_ui — Desktop Client

**Source:** `Automation_ui/desktop-client/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Input** | `pynput >=1.7.6` (Mouse/Keyboard Listener) |
| **Screenshots** | `mss >=9.0.1`, `screeninfo >=0.8.1` |
| **Automation** | `pyautogui` |
| **Vision** | `opencv-python`, `numpy`, `Pillow` |
| **WebSocket** | `websockets >=11.0` |

### 5g. Automation_ui — React Frontend

**Source:** `Automation_ui/package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **UI** | `react ^18.3.1`, 30+ `@radix-ui/*` Komponenten |
| **State** | `@tanstack/react-query ^5.56.2`, `zustand ^4.5.7` |
| **Flow** | `@xyflow/react ^12.8.2` |
| **Charts** | `recharts ^2.12.7` |
| **Forms** | `react-hook-form ^7.53.0`, `@hookform/resolvers`, `zod` |
| **Animation** | `framer-motion ^10.18.0` |
| **Routing** | `react-router-dom ^6.26.2` |
| **HTTP** | `axios ^1.10.0` |
| **WebSocket** | `ws ^8.18.3` |
| **Backend** | `express ^5.1.0`, `pg ^8.16.3` (PostgreSQL), `cors` |
| **Browser Automation** | `playwright ^1.54.1` |
| **CSS** | `tailwindcss ^3.4.11`, `tailwindcss-animate` |
| **Date** | `date-fns ^3.6.0` |
| **Carousel** | `embla-carousel-react` |
| **Build** | `vite ^5.4.1`, `typescript ^5.5.3` |

### 5h. Automation_ui — Electron App

**Source:** `Automation_ui/electron-app/package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **Runtime** | `electron ^28.0.0`, `electron-builder`, `electron-is-dev` |

**Externe Runtime-Services:**
- MoireTracker v2 (`C:/Users/User/Desktop/Moire_tracker_v1/MoireTracker_v2/python`)
- MoireServer (WebSocket Port 8766)
- Automation_ui FastAPI (Port 8007)

---

## 6. Research Space (`python/spaces/research/`)

**Source:** Imports aus `agents/zeroclaw_research_agent.py`, `tools/zeroclaw_tools.py`

| Kategorie | Technologien |
|-----------|-------------|
| **Web Scraping** | `beautifulsoup4`, `requests` |
| **LLM** | `openai` (via OpenRouter — Zusammenfassung, Analyse) |
| **Database** | SQLite via Repository Pattern |

**5 research.* Events:** search, summarize, deep_dive, research_to_idea, research_to_rowboat

**Eigenentwicklung:**
- ZeroClawResearchAgent (Web-Recherche mit LLM-Synthese)
- Chained Operations (Research → Idea, Research → Rowboat)

**Keine eigene requirements.txt** — nutzt Main VibeMind Dependencies.

---

## 7. Rowboat Space (`python/spaces/rowboat/`)

### 7a. Rowboat Agent (VibeMind-seitig)

**Source:** Imports aus `agents/roarboot_agent.py`, `tools/roarboot_tools.py`

| Kategorie | Technologien |
|-----------|-------------|
| **HTTP** | `httpx`, `requests` (Rowboat REST API) |
| **Database** | `pymongo` (MongoDB), `redis` |

**13 roarboot.* Events**

### 7b. Rowboat Submodul — Main App (`rowboat/apps/rowboat/`)

**Source:** `package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **Framework** | `next 15.3.8` (Next.js) |
| **UI** | `react 19.1.0`, `@heroicons/react`, `@heroui/react`, `@primer/react` |
| **AI SDKs** | `@ai-sdk/openai`, `@google/generative-ai`, `ai ^4.3.13` (Vercel AI SDK) |
| **Agent** | `@openai/agents`, `@openai/agents-extensions` |
| **MCP** | `@modelcontextprotocol/sdk` |
| **LangChain** | `@langchain/core`, `@langchain/textsplitters` |
| **Vector DB** | `@qdrant/js-client-rest` |
| **Database** | `mongodb ^6.8.0`, `ioredis` |
| **Auth** | `@auth0/nextjs-auth0`, `jose` (JWT) |
| **AWS** | `@aws-sdk/client-s3`, `@aws-sdk/s3-request-presigner` |
| **Web Scraping** | `@mendable/firecrawl-js` |
| **Composio** | `@composio/core` (Tool Integrations) |
| **DnD** | `@dnd-kit/core`, `@dnd-kit/sortable` |
| **Rich Text** | `quill`, `quill-mention` |
| **Diagrams** | `mermaid` |
| **Markdown** | `react-markdown`, `remark-gfm` |
| **CSS** | `tailwindcss ^4` |
| **Analytics** | `posthog-js` |
| **Communication** | `twilio` |
| **Validation** | `zod`, `zod-to-json-schema` |
| **IoC** | `awilix` |

### 7c. Rowboat X — Desktop App (Renderer)

**Source:** `rowboat/apps/x/apps/renderer/package.json`

| Kategorie | Technologien |
|-----------|-------------|
| **Rich Text** | `@tiptap/*` (8 Extensions — Tiptap Editor) |
| **UI** | 14× `@radix-ui/*`, `cmdk` (Command Menu), `sonner` (Toasts) |
| **AI** | `ai ^5.0.117` (Vercel AI SDK v5) |
| **Animation** | `motion` |
| **Streaming** | `streamdown` (Streaming Markdown) |
| **Token** | `tokenlens` (Token Counting) |
| **Build** | `vite ^7.2.4`, `tailwindcss ^4`, `zod ^4.2.1` |

### 7d. Rowboat X — CLI/Backend (`rowboat/apps/cli/`)

**Source:** `package.json` (rowboatx v0.16.0)

| Kategorie | Technologien |
|-----------|-------------|
| **AI SDKs** | `@ai-sdk/anthropic`, `@ai-sdk/google`, `@ai-sdk/openai`, `@ai-sdk/openai-compatible`, `@openrouter/ai-sdk-provider`, `ollama-ai-provider-v2` |
| **MCP** | `@modelcontextprotocol/sdk` |
| **Web Framework** | `hono`, `hono-openapi`, `@hono/node-server` |
| **Google** | `googleapis`, `google-auth-library`, `@google-cloud/local-auth` |
| **Terminal UI** | `ink`, `ink-select-input`, `ink-spinner`, `ink-text-input` (React for CLI) |
| **HTML→MD** | `node-html-markdown` |
| **SSE** | `eventsource-parser` |
| **CLI** | `yargs`, `yaml` |
| **Validation** | `zod ^4.1.12`, `json-schema-to-zod` |

### 7e. Rowboat Python SDK

**Source:** `rowboat/apps/python-sdk/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **SDK** | `pydantic 2.10.5`, `requests`, `typing_extensions` |

### 7f. Docker-Services (Rowboat Stack)

| Service | Port | Technologie |
|---------|------|-------------|
| Rowboat App | 3000 | Next.js |
| MongoDB | 27017 | MongoDB (WiredTiger) |
| Redis | 6379 | Redis |
| Qdrant | 6333 | Qdrant Vector DB |

---

## 8. Minibook Space (`python/spaces/minibook/`)

### 8a. Minibook Agent (VibeMind-seitig)

**Source:** Imports aus `agents/`, `tools/`, `workers/`, `enrichment/`

| Kategorie | Technologien |
|-----------|-------------|
| **LLM** | `openai` (via OpenRouter — Space Routing, EnrichmentPipeline) |
| **HTTP** | `httpx`, `requests` (Minibook REST API, Port 3480) |
| **Database** | SQLite via Repository Pattern |
| **Async** | `asyncio`, `aiohttp` |

**6 minibook.* Events**

**Eigenentwicklung:**
- MinibookHub (Central Dispatch für alle Intents)
- 4-Stage EnrichmentPipeline (ContextGather → IntentClassifier → SpaceRouter → TaskEnricher)
- ResultAggregator (Sync ≤10s / Async-Poll)
- DiscussionPollerWorker (2s Polling, 120s Timeout)
- SpaceMinibookResponder (Per-Space @mention Handler)
- 9 registrierte Space-Agents in Minibook

### 8b. Minibook External Service (`external/minibook/`)

**Source:** `requirements.txt` + `frontend/package.json`

**Backend:**

| Kategorie | Technologien |
|-----------|-------------|
| **Web Framework** | `fastapi >=0.100.0`, `uvicorn` |
| **Database** | `sqlalchemy >=2.0.0`, SQLite |
| **HTTP** | `httpx >=0.27.0` |
| **Config** | `pyyaml` |

**Frontend:**

| Kategorie | Technologien |
|-----------|-------------|
| **Framework** | `next 16` (Next.js) |
| **UI** | `react 19`, `radix-ui`, `shadcn` |
| **CSS** | `tailwindcss ^4` |

---

## 9. Schedule Space (`python/spaces/schedule/`)

**Source:** Imports aus `agents/schedule_agent.py`, `tools/schedule_tools.py`

| Kategorie | Technologien |
|-----------|-------------|
| **Scheduling** | `APScheduler` (CronTrigger, DateTrigger, IntervalTrigger) |
| **NLP** | Custom Regex-Parser für deutsche Zeitausdrücke |
| **LLM** | `openai` (via OpenRouter — Complex Schedule Parsing) |
| **Database** | SQLite (`scheduled_tasks` Tabelle) |

**6 schedule.* Events:** create, list, pause, resume, delete, status

**Eigenentwicklung:**
- NLP Time Parser (Regex: "jeden Montag um 9", "in 2 Stunden", "morgen früh")
- Dual-Mode: Simple (Regex) vs. Complex (LLM-Parsing)
- APScheduler Integration mit SQLite Persistence

**Keine eigene requirements.txt** — nutzt Main VibeMind Dependencies.

---

## 10. Shuttles / SWE Design Space (`python/spaces/shuttles/`)

### 10a. VibeMind-seitig

Kein eigener Agent — Events (`bubble.evaluate`, `bubble.promote`) werden von BubblesAgent gehandhabt.

### 10b. SWE Design Submodul (`shuttles/swe_desgine/`)

**Source:** `swe_desgine/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **AI/LLM** | `openai`, `anthropic`, `google-generativeai` (3 LLM Provider) |
| **PDF** | `pypdf`, `pymupdf` |
| **LaTeX** | `latex` (Paper Generation) |
| **ML** | `torch`, `transformers`, `datasets` |
| **NLP** | `nltk`, `spacy` |
| **Data** | `numpy`, `pandas`, `scipy`, `scikit-learn` |
| **Visualization** | `matplotlib`, `seaborn`, `plotly` |
| **Git** | `gitpython` |
| **HTTP** | `aiohttp`, `requests`, `beautifulsoup4` |
| **Config** | `pyyaml`, `python-dotenv` |

**Eigenentwicklung:**
- AI-Scientist Pipeline (Automated Paper Generation)
- LLM Review System (`perform_llm_review.py` — Originality/Quality/Clarity/Significance 1-4, Overall 1-10, Accept/Reject)
- Requirements Engineering Pipeline (5-Pass mit Quality Gates, Gherkin Test Cases)
- Shuttle Stage System (Requirements → Design → Implementation → Review)

---

## 11. Brain / Tahlamus Space (`python/spaces/brain/`)

### 11a. Brain Core (`the_brain/`)

**Source:** `requirements.txt`, `requirements-full.txt`, `requirements-tahlamus.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Deep Learning** | `torch >=2.0.0`, `torchvision` |
| **JAX** | `jax >=0.3.0`, `jaxlib` (Alternative Backend für ATM-R) |
| **State Space** | `mamba-ssm` (Mamba State Space Model, CUDA), `causal-conv1d` |
| **ML/Science** | `numpy`, `scipy`, `pandas`, `scikit-learn`, `matplotlib` |
| **Dimensionality** | `umap-learn 0.5.11`, `pynndescent 0.6.0` (Neural Manifold Visualization) |
| **Web Framework** | `flask`, `flask-cors`, `fastapi`, `uvicorn[standard]` |
| **WebSocket** | `websockets` |
| **Templates** | `jinja2` |
| **LLM APIs** | `openai` (GPT-4o), `anthropic` (Claude 3.5), `pyautogen` (14 Cognitive Agents) |
| **Web Search** | `ddgs` (DuckDuckGo) |
| **Cloud** | `boto3` (AWS S3) |
| **Config** | `pyyaml`, `python-dotenv` |
| **Build** | `ninja >=1.11.0` (C++ Build System für Mamba) |

### 11b. Brain — Swarm

**Source:** `requirements-swarm.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Multi-Agent** | `autogen-agentchat >=0.4.0`, `autogen-ext` |
| **Async** | `aiohttp`, `asyncio` |

### 11c. Brain — Memory

**Source:** `requirements-memory.txt`, `requirements-memory-api.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **Memory** | `supabase >=2.3.0`, Supermemory Integration |
| **API** | `fastapi`, `uvicorn` |

### 11d. Brain — Custom Neural Architectures (Eigenentwicklung!)

| Modul | Beschreibung |
|-------|-------------|
| **TransformerCTM** | Custom `nn.Module` mit HaltPredictor (GELU), LoRA Fine-Tuning auf Qwen2.5-0.5B |
| **4 CTM Domains** | Spatial, Logic, Temporal, Value — jeweils eigener Trainings-Loop |
| **Trainierte Checkpoints** | `logic_brain_epoch_1-24.pth`, `best_model.pth`, `final_model.pth` |
| **ATM-R** | Adaptive Thalamic Multimodal Router — differentierbares PyTorch-Modul mit Backprop durch Routing Gates |
| **Hebbian Plasticity** | Online Correlation-based Learning für RadialAttentionNetwork (<1ms pro Update, kein Gradient) |
| **5-Ring Radial Attention** | Sensory (64D) → Pattern (128D) → Semantic (256D) → Abstract (256D) → Meta (128D) |
| **10 Neuromodulation Bridges** | Neuromod, Cortex, Limbic, Sleep/Wake, Motor, Defense, Memory, Integration, Visceral, Social |
| **Thalamic Gating** | 10 Modalitäten (6 sensory + 4 conversation trace) |
| **3-Layer Hierarchical Routing** | TaskFeature → ConversationPath → Decision |
| **43 Neuroscience Modules** | PFC, ACC, OFC, Amygdala, VTA, LC, Raphe, Claustrum, Hippocampus, Cerebellum, etc. |
| **Dream Mode CTM Trainer** | Per-Domain Training Strategies mit NeuroSymbolicBrain Integration |
| **9-Phase Cognitive Loop** | Perceive → Appraise → Remember → Attend → Modulate → Reason → Reflect → Learn → Consolidate |

### 11e. Brain — Moltbook (Knowledge System)

**Source:** `the_brain/core/moltbook.py`, `moltbook_pipeline.py`

| Modul | Beschreibung |
|-------|-------------|
| **Moltbook Graph** | Spreading Activation Network, Ebbinghaus Forgetting Curve |
| **Semantic Index** | numpy-basierter ANN (Approximate Nearest Neighbor) |
| **Thinker-Talker Pipeline** | Inspiriert von MIRROR (arxiv 2506.00430) |

### 11f. Brain — External CTM Reference

**Source:** `external/continuous-thought-machines/requirements.txt`

| Kategorie | Technologien |
|-----------|-------------|
| **RL** | `gymnasium`, `minigrid` |
| **HuggingFace** | `datasets`, `huggingface_hub`, `safetensors` |
| **Gradient** | `autoclip` (Gradient Clipping) |
| **Vision** | `imageio`, `seaborn` |

### 11g. Brain — Dashboards

| URL | Technologie |
|-----|-------------|
| `localhost:5000` | Flask + Jinja2 + JavaScript |
| `localhost:5000/brain` | Brain Visualization (Canvas/WebGL) |
| `localhost:5000/radial` | Radial Dashboard (Bridges, Rings, Hooks) |

### 11h. Brain — 3D UI (Electron)

Eigene 3D-Szene im VibeMind Multiverse:
- Organic deformed brain mesh (vertex displacement)
- 60 neuron particles mit synaptischen Connections
- Brain stem + floating thought bubbles
- Pulsing Animation + Synapse Flicker Effects

---

## Konsolidierte Zusammenfassung für Grant Q2.6

### AI & Machine Learning

| Technologie | Einsatz |
|-------------|---------|
| **OpenAI GPT-4o** | Voice (Realtime API Speech-to-Speech), Intent Classification, Communication |
| **Claude 3.5 (Anthropic)** | Planning, Code Generation (claude-agent-sdk) |
| **DeepSeek R1** | Reasoning (via OpenRouter) |
| **Gemini Flash (Google)** | Memory, generative-ai SDK |
| **Ollama** | Local LLM Inference |
| **DroPE-SmolLM-135M-32K** | Transformer-basierte Referenzauflösung (Sakana AI) |
| **Qwen2.5-0.5B + LoRA** | CTM Fine-Tuning Base Model |
| **EmbeddingGemma** | Lokales Embedding-Modell (.safetensors) |
| **sentence-transformers** | all-MiniLM-L6-v2 (384-dim Semantic Embeddings) |
| **OpenAI Whisper** | Speech-to-Text |
| **Edge TTS / pyttsx3** | Text-to-Speech (Online/Offline) |

### Custom Neural Architectures (Eigenentwicklung)

| Architektur | Beschreibung |
|-------------|-------------|
| **TransformerCTM** | 4 Custom-trainierte PyTorch-Modelle (Spatial, Logic, Temporal, Value) mit HaltPredictor |
| **ATM-R** | Adaptive Thalamic Multimodal Router (differentierbares PyTorch-Modul) |
| **Hebbian Plasticity** | Online Correlation-based Learning (<1ms, gradientenfrei) |
| **5-Ring Radial Attention** | Sensory→Pattern→Semantic→Abstract→Meta (64D–256D) |
| **Mamba SSM Integration** | State Space Model mit ATM-R Routing (CUDA) |
| **Moltbook Graph** | Spreading Activation + Ebbinghaus Forgetting Curve |

### Deep Learning Frameworks

| Framework | Einsatz |
|-----------|---------|
| **PyTorch** | CTM Training, ATM-R, Hebbian Learning, DroPE |
| **JAX/JAXlib** | Alternative ATM-R Backend |
| **HuggingFace Transformers** | Model Loading, Tokenization |
| **FAISS** | Vector Similarity Search |
| **scikit-learn** | ML Algorithms, Clustering |

### Multi-Agent Orchestration

| Framework | Einsatz |
|-----------|---------|
| **AutoGen 0.4** | 8 Backend-Agents (autogen-agentchat), 14 Cognitive Agents (Brain), Moire Agents, VideoSurfer |
| **Vercel AI SDK** | Rowboat Streaming (v4 + v5) |
| **OpenAI Agents SDK** | Rowboat Agent Extensions |
| **MCP (Model Context Protocol)** | 18 Plugin-Server im Coding Engine |
| **LangChain** | Text Splitting, Rowboat Integration |
| **LlamaIndex** | Code Search Integration |

### Voice & Audio

| Technologie | Einsatz |
|-------------|---------|
| **OpenAI Realtime API** | Speech-to-Speech mit VAD + Native Function Calling |
| **sounddevice + librosa** | Audio Capture + Analysis |
| **MediaPipe** | Hand Motion Detection |

### Computer Vision & OCR

| Technologie | Einsatz |
|-------------|---------|
| **OpenCV** | Image Processing, Screenshot Analysis |
| **pytesseract** | Classical OCR |
| **EasyOCR** | Deep Learning OCR |
| **PaddlePaddle + PaddleOCR** | Baidu OCR Engine |
| **MediaPipe** | Hand/Gesture Recognition |

### Web Frameworks

| Framework | Einsatz |
|-----------|---------|
| **FastAPI** | Automation_ui, Brain, Minibook, Coding Engine |
| **Flask** | Brain Dashboards |
| **Next.js 15–16** | Rowboat App, Minibook Frontend, ClawPort UI |
| **Hono** | Rowboat X CLI/Backend |
| **Express** | Automation_ui Node.js Backend |

### Frontend & 3D

| Technologie | Einsatz |
|-------------|---------|
| **React 18/19** | Alle Frontends |
| **Three.js** | 3D Multiverse (WebGL, Fresnel Shader, Bloom) |
| **Radix UI** | Headless UI Components (ClawPort, Automation_ui, Rowboat X) |
| **Tailwind CSS 3/4** | Styling (alle Frontends) |
| **Tiptap** | Rich Text Editor (Rowboat X) |
| **React Flow (@xyflow)** | Flow Diagrams (ClawPort, Automation_ui) |
| **Recharts** | Charts (Automation_ui) |
| **Framer Motion** | Animation (Automation_ui) |
| **Mermaid** | Diagram Rendering (Rowboat) |

### Database & Storage

| Technologie | Einsatz |
|-------------|---------|
| **SQLite** | Main VibeMind DB (19 Tabellen, Schema v14) |
| **MongoDB** | Rowboat Knowledge Graph |
| **PostgreSQL** | Coding Engine, Automation_ui |
| **Redis** | Event Streams, Caching, Queuing |
| **Qdrant** | Vector Search (Coding Engine, Rowboat) |
| **Supabase** | Cloud Database (optional) |
| **Supermemory** | Semantic Memory Service |
| **FAISS** | Vector Similarity (La Fungus Search) |

### DevOps & Infrastructure

| Technologie | Einsatz |
|-------------|---------|
| **Electron** | Desktop App Runtime (3 Apps: VibeMind, Coding Engine, Automation_ui) |
| **Docker** | Container Orchestration (Rowboat Stack, Coding Engine) |
| **Kubernetes** | Container Management (kopf K8s Operator) |
| **gRPC + Protobuf** | Inter-Service Communication |
| **Vite** | Frontend Build Tool |
| **HashiCorp Vault** | Secret Management |

### Networking & Protocols

| Technologie | Einsatz |
|-------------|---------|
| **WebSocket** | Real-time Communication (MoireServer, Brain) |
| **WebRTC** | aiortc (Desktop Streaming) |
| **SSH** | asyncssh, paramiko (Remote Automation) |
| **MQTT** | asyncio-mqtt (IoT/Event Protocol) |
| **SSE** | Server-Sent Events (Automation_ui) |

### NLP & Search

| Technologie | Einsatz |
|-------------|---------|
| **NLTK + spaCy** | NLP (SWE Design) |
| **BM25 (rank-bm25)** | Text Search (La Fungus Search) |
| **DuckDuckGo (ddgs)** | Web Search (Brain) |
| **Brave Search + Tavily** | Web Search APIs (MCP Plugins) |

### Desktop Automation

| Technologie | Einsatz |
|-------------|---------|
| **pyautogui** | Mouse/Keyboard Automation |
| **pynput** | Input Listener |
| **Playwright** | Browser Automation + E2E Testing |
| **MoireTracker v2** | Custom OCR-basierte UI-Automation |

---

> **Gesamtumfang:** ~70.000 Zeilen eigenentwickelter Code (Python + JS/TS), 200+ externe Dependencies, 5 Submodule, 18 MCP-Server, 3 Electron-Apps, 4 Datenbank-Engines, 6+ LLM-Provider, 4 custom-trainierte Neural Networks.
