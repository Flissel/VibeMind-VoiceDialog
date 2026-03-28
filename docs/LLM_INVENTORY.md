# LLM Inventory — VibeMind Voice Dialog

> Vollständiges Inventar aller LLM-Modelle, Provider und Konfigurationen.
> Stand: 2026-03-10 | 60+ aktive Stellen | 40+ verschiedene Modelle | 40+ Env-Vars

---

## Provider-Übersicht

| Provider | Stellen | Auth Env-Var | Base URL |
| --- | --- | --- | --- |
| **OpenRouter** | ~35 | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| **OpenAI Direct** | ~5 | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| **Anthropic SDK** | ~8 | `ANTHROPIC_API_KEY` | SDK default |
| **Google Gemini** | ~1 | `GOOGLE_API_KEY` / `GEMINI_API_KEY` | Google GenAI SDK |
| **Ollama lokal** | ~3 | `OLLAMA_HOST` | `http://localhost:11434` |
| **HuggingFace lokal** | ~1 | — | transformers (lokal) |
| **sentence-transformers** | ~3 | — | lokal |
| **OpenAI Embeddings** | ~3 | `OPENAI_API_KEY` | OpenAI/OpenRouter |
| **Grok** | ~1 | — | Grok API |

---

## Voice Layer

| Zweck | Modell | Provider | Env-Var | Datei:Zeile |
| --- | --- | --- | --- | --- |
| Speech-to-Speech (Rachel) | `gpt-4o-realtime-preview` | OpenAI Direct | `OPENAI_REALTIME_MODEL` | `python/voice/session_config.py:15` |

---

## Swarm Orchestration (15 Stellen)

| Zweck | Modell | Provider | Env-Var | Datei:Zeile |
| --- | --- | --- | --- | --- |
| Intent Classifier | `anthropic/claude-3.5-haiku` | OpenRouter | `CLASSIFIER_MODEL` | `python/swarm/orchestrator/intent_classifier.py:549` |
| RAG Classifier | `anthropic/claude-opus-4.5` | OpenRouter | `RAG_CLASSIFIER_MODEL` | `python/swarm/orchestrator/rag_intent_classifier.py:192` |
| Response Generator | `anthropic/claude-3.5-haiku` | OpenRouter | `RESPONSE_MODEL` | `python/swarm/orchestrator/response_generator.py:75` |
| Tool Orchestrator | `anthropic/claude-sonnet-4` | OpenRouter | `ORCHESTRATOR_MODEL` | `python/swarm/orchestrator/tool_orchestrator.py:126` |
| Reference Resolver (DroPE) | `SakanaAI/DroPE-SmolLM-135M-32K` | HuggingFace lokal | `DROPE_MODEL` | `python/swarm/orchestrator/reference_resolver.py:56` |
| Cloud Client Default | `anthropic/claude-sonnet-4` | OpenRouter | `OPENROUTER_MODEL` | `python/swarm/cloud_client.py:26` |
| Ollama Fallback | `llama3.1:8b` | Ollama lokal | `OLLAMA_MODEL` | `python/swarm/ollama_client.py:17` |
| Collector Agent | `openai/gpt-4o-mini` | OpenRouter | (hardcoded) | `python/swarm/agents/collector_agent.py:62` |
| Analysis Team | `anthropic/claude-3.5-haiku` | OpenRouter | `ANALYSIS_MODEL` | `python/swarm/analysis/intent_analysis_team.py:79` |
| Conversion AI | `anthropic/claude-3.5-haiku` | OpenRouter | `CONVERSION_MODEL` | `python/swarm/conversion/conversion_ai.py:76` |
| Personality Generator | `anthropic/claude-3.5-haiku` | OpenRouter | `PERSONALITY_MODEL` | `python/swarm/conversion/personality_generator.py:58` |
| Stream Listener | `openai/gpt-4o-mini` | OpenRouter | `STREAM_LISTENER_MODEL` | `python/swarm/stream_listener/base_listener.py:118` |
| Space Agent | `openai/gpt-4o-mini` | OpenRouter | `SPACE_AGENT_MODEL` | `python/swarm/space_agents/base_space_agent.py:37` |
| Broadcast Profiling | `openai/gpt-4o-mini` | OpenRouter | `PROFILING_MODEL` | `python/swarm/broadcast/sub_agents/memory_sub_agent.py:28` |
| Broadcast Context | `openai/gpt-4o-mini` | OpenRouter | `CONTEXT_MODEL` | `python/swarm/broadcast/sub_agents/context_sub_agent.py:25` |

---

## Workers (3 Stellen)

| Zweck | Modell | Provider | Env-Var | Datei:Zeile |
| --- | --- | --- | --- | --- |
| Summarization | `gpt-4o-mini` | OpenAI Direct | `OPENAI_SUMMARIZATION_MODEL` | `python/workers/summarization_worker.py:81` |
| Rewrite | `gemini-1.5-flash` | Google Gemini | `GEMINI_MODEL` | `python/workers/rewrite_worker.py:87` |
| Claude Worker (Desktop) | `anthropic/claude-opus-4-5-20251101` | OpenRouter | (hardcoded) | `python/workers/claude_worker.py:72` |

---

## Data Layer

| Zweck | Modell | Provider | Datei:Zeile |
| --- | --- | --- | --- |
| Idea/Bubble Embeddings | `all-MiniLM-L6-v2` | sentence-transformers lokal | `python/data/embedding_service.py:55` |

---

## Ideas Space (14 Stellen)

| Zweck | Modell | Provider | Env-Var | Datei:Zeile |
| --- | --- | --- | --- | --- |
| Summarization | `openai/gpt-4o-mini` | OpenRouter | `OPENROUTER_SUMMARY_MODEL` | `ideas/tools/summary_tools.py:169` |
| Rewriting | `google/gemini-2.0-flash-001` | OpenRouter | `OPENROUTER_REWRITE_MODEL` | `ideas/tools/summary_tools.py:221` |
| Whitepaper | `openai/gpt-4o-mini` | OpenRouter | `OPENROUTER_WHITEPAPER_MODEL` | `ideas/tools/summary_tools.py:651` |
| Structure Extraction | `openai/gpt-4o-mini` | OpenRouter | `OPENROUTER_STRUCTURE_MODEL` | `ideas/tools/summary_tools.py:837` |
| Feature Docs | `openai/gpt-4o-mini` | OpenRouter | `OPENROUTER_FEATURE_MODEL` | `ideas/tools/summary_tools.py:1093` |
| Bubble Evaluation | `openai/gpt-4o-mini` | OpenRouter | `OPENROUTER_EVAL_MODEL` | `ideas/tools/bubble_tools.py:1314` |
| Format Dispatch | `anthropic/claude-sonnet-4.5` | OpenRouter | (hardcoded) | `ideas/tools/format_dispatcher.py:56` |
| Structured Formatting | `anthropic/claude-sonnet-4-6` | OpenRouter | (hardcoded) | `ideas/tools/structured_formatting_tools.py:552` |
| Exploration/Paper (6x) | `anthropic/claude-3.5-haiku` | OpenRouter | (hardcoded) | `ideas/tools/exploration_tools.py:868,924,1001,1058,1736,1820` |
| Idea Linking/Expansion | `anthropic/claude-sonnet-4` | OpenRouter | (hardcoded) | `ideas/tools/idea_tools.py:1582` |
| Idea Content Generation | `openai/gpt-4o-mini` | OpenRouter | `SPACE_AGENT_MODEL` | `ideas/tools/idea_tools.py:482` |
| Idea Classification | `openai/gpt-4o-mini` | OpenRouter | `OPENROUTER_SUMMARY_MODEL` | `ideas/tools/idea_tools.py:881` |
| Connection Evaluator | `gpt-4o-mini` | OpenAI-compat | (hardcoded) | `ideas/explorer/connection_evaluator.py:266` |
| AutoGen Research | `gpt-4` | OpenRouter | (hardcoded) | `ideas/tools/autogen_research.py:37` |

---

## Coding Space

### Rollen (llm_models.yml)

Config: `python/spaces/coding/Coding_engine/config/llm_models.yml`
Loader: `python/spaces/coding/Coding_engine/src/llm_config.py`

| Rolle | Modell | Provider | Env-Var | Zweck |
| --- | --- | --- | --- | --- |
| primary | `claude-sonnet-4-6` | Anthropic SDK | `LLM_MODEL_PRIMARY` | Base agent, vision, monitor |
| cli | `anthropic/claude-opus-4-6` | OpenRouter | `LLM_MODEL_CLI` | Claude/Kilo CLI |
| mcp_standard | `claude-sonnet-4-6` | Anthropic SDK | `LLM_MODEL_MCP_STANDARD` | AutoGen teams, task executor |
| mcp_agent | `claude-sonnet-4-6` | Anthropic SDK | `LLM_MODEL_MCP_AGENT` | MCP plugin agents |
| judge | `claude-haiku-4-5` | Anthropic SDK | `LLM_MODEL_JUDGE` | Fungus agents, diff analysis, MCMP |
| reasoning | `claude-sonnet-4-6` | Anthropic SDK | `LLM_MODEL_REASONING` | Architecture analysis |
| enrichment | `claude-sonnet-4-6` | Anthropic SDK | `LLM_MODEL_ENRICHMENT` | Phase 30 schema discovery |

### Free Models Fallback (free_models.yml)

Config: `python/spaces/coding/Coding_engine/config/free_models.yml`

| Kategorie | Primary | Fallback 1 | Fallback 2 |
| --- | --- | --- | --- |
| Coding | `mistralai/devstral-2512:free` | `qwen/qwen3-coder:free` | `deepseek/deepseek-r1-0528:free` |
| Reasoning | `xiaomi/mimo-v2-flash:free` | `nvidia/nemotron-3-nano-30b-a3b:free` | `deepseek/deepseek-r1-0528:free` |
| Vision | `nvidia/nemotron-nano-12b-v2-vl:free` | `qwen/qwen-2.5-vl-7b-instruct:free` | `allenai/molmo-2-8b:free` |
| General | `meta-llama/llama-3.3-70b-instruct:free` | `google/gemini-2.0-flash-exp:free` | `meta-llama/llama-3.1-405b-instruct:free` |

### Weitere Modelle

| Zweck | Modell | Datei |
| --- | --- | --- |
| MCP Default | `anthropic/claude-sonnet-4.5` | `mcp_plugins/models/model.json` |
| Fungus Judge (Society) | `anthropic/claude-sonnet-4.5` | `config/society_defaults.json:54` |
| MCMP Judge + Steering | via `get_openrouter_model("judge")` | `src/services/mcmp_background.py:47-48` |
| Fungus Embeddings (primary) | `all-MiniLM-L6-v2` | `src/agents/fungus_context_agent.py:529` |
| Fungus Embeddings (quality) | `all-mpnet-base-v2` | `src/agents/fungus_context_agent.py` |
| Fungus Embeddings (API) | `text-embedding-3-small` | `src/agents/fungus_context_agent.py:500,520` |
| Completeness Embeddings | `text-embedding-3-small` | `src/agents/fungus_completeness_agent.py:72` |
| Claude Monitor | via `get_model("primary")` | `src/monitoring/claude_monitor.py:34` |

### La Fungus Search LLM Config

Config: `la_fungus_search/src/embeddinggemma/llm/config.py`

| Provider | Default-Modell | Zeile |
| --- | --- | --- |
| Ollama | `qwen2.5-coder:7b` | :8 |
| OpenAI | `gpt-4o-mini` | :19 |
| Google | `gemini-1.5-pro` | :27 |
| Grok | `grok-2-latest` | :35 |

### Model Info Registry

Datei: `mcp_plugins/servers/shared/model_utils.py:85-156`

Bekannte Modelle mit Capability-Flags (vision, tool_use, max_tokens):

- `anthropic/claude-opus-4.5`, `anthropic/claude-opus-4`, `anthropic/claude-opus-4-20250514`
- `anthropic/claude-sonnet-4.5`, `anthropic/claude-haiku-4.5`, `anthropic/claude-sonnet-4`
- `anthropic/claude-3.5-sonnet`, `anthropic/claude-3-opus`
- `google/gemini-2.0-flash`, `meta-llama/llama-3.3-70b-instruct`

---

## Desktop Space (13 Stellen)

| Zweck | Modell | Provider | Env-Var | Datei |
| --- | --- | --- | --- | --- |
| LLM Primary | `anthropic/claude-opus-4` | OpenRouter | `LLM_MODEL` | `Automation_ui/backend/app/config.py:82` |
| Vision | `nvidia/nemotron-nano-12b-v2-vl:free` | OpenRouter | `VISION_MODEL` | `Automation_ui/backend/app/config.py:83` |
| Compaction | `anthropic/claude-sonnet-4` | OpenRouter | `COMPACTION_MODEL` | `Automation_ui/backend/app/config.py:84` |
| AutoGen Default | `google/gemini-flash-1.5` | OpenRouter | `AUTOGEN_MODEL` | `autogen_service/config.py:64` |
| AutoGen Vision | `google/gemini-flash-1.5` | OpenRouter | `AUTOGEN_VISION_MODEL` | `autogen_service/config.py:71` |
| Moire Reasoning | `anthropic/claude-sonnet-4` | OpenRouter | (hardcoded) | `moire_agents/core/openrouter_client.py:49` |
| Moire Vision | `anthropic/claude-sonnet-4` | OpenRouter | (hardcoded) | `moire_agents/core/openrouter_client.py:50` |
| Moire Vision Fast | `google/gemini-2.0-flash-exp:free` | OpenRouter | (hardcoded) | `moire_agents/core/openrouter_client.py:51` |
| Moire Quick | `anthropic/claude-3.5-sonnet` | OpenRouter | (hardcoded) | `moire_agents/core/openrouter_client.py:52` |
| Classification | `google/gemini-2.0-flash-001` | OpenRouter | (hardcoded) | `classification_agent.py` |
| Task Decomposer | `anthropic/claude-sonnet-4-20250514` | OpenRouter | (hardcoded) | `task_decomposer.py` |
| Subagents (bg/plan/vision) | `openai/gpt-4o-mini` | OpenRouter | (hardcoded) | `background_subagent.py` etc. |
| Messaging Filter | `qwen2.5:3b` | Ollama lokal | `MESSAGING_OLLAMA_MODEL` | `desktop/messaging/relevance_filter.py:23` |

---

## Minibook Space

| Zweck | Modell | Provider | Env-Var | Datei |
| --- | --- | --- | --- | --- |
| Space Routing/Enrichment | `openai/gpt-4o-mini` | OpenRouter | `MINIBOOK_ENRICHMENT_MODEL` | `minibook/enrichment/space_router.py:86` |

---

## Rowboat Space (4 Stellen)

| Zweck | Modell | Provider | Env-Var | Datei |
| --- | --- | --- | --- | --- |
| Priority 1 (Anthropic) | `claude-sonnet-4-20250514` | Anthropic SDK | `ROWBOAT_MODEL` | `electron-app/main.js:100` |
| Priority 2 (OpenRouter) | `anthropic/claude-sonnet-4` | OpenRouter | `ROWBOAT_MODEL` | `rowboat/config.py` |
| Priority 3 (OpenAI) | `gpt-4.1` | OpenAI Direct | `ROWBOAT_MODEL` | `electron-app/main.js:112` |
| Simulation Runner | `gpt-4.1` | OpenAI Direct | (hardcoded) | `rowboat/.../simulation.py:14` |

---

## Shuttles Space — AI Scientist

Verfügbare Modelle: 92 in `ai_scientist/llm.py:13-92`
Verfügbare VLMs: 15+ in `ai_scientist/vlm.py:13-40`

| Zweck | Modell | Provider | Datei |
| --- | --- | --- | --- |
| Writeup/Review | `openrouter/anthropic/claude-sonnet-4` | OpenRouter | `run_writeup_only.py:29,32` |
| Writeup Small/Agg/Citation | `openrouter/google/gemini-3-flash-preview` | OpenRouter | `run_writeup_only.py:28,30,31` |
| BFTS Default | `openrouter/anthropic/claude-sonnet-4` | OpenRouter | `launch_scientist_bfts.py:109,133` |
| Plotting Reflection | `o1-2024-12-17` | OpenAI Direct | `perform_plotting.py:137` |

---

## Shuttles Space — Requirements Engineer (30+ Stellen)

Config: `python/spaces/shuttles/swe_desgine/requirements_engineer/re_config.yaml`

### Generatoren

| Generator | Modell | Fallback |
| --- | --- | --- |
| NFR Generator | `openai/gpt-5.2-codex` | `openai/gpt-4o-mini` |
| User Story Generator | `openai/gpt-5.2-codex` | `openai/gpt-4o-mini` |
| API Spec Generator | `openai/gpt-5.2-codex` | `openai/gpt-4o-mini` |
| Test Case Generator | `openai/gpt-5.2-codex` | `openai/gpt-4o-mini` |
| Task Generator | `openai/gpt-5.2-codex` | `openai/gpt-4o-mini` |
| UI Design Generator | `openai/gpt-5.2-codex` + `anthropic/claude-opus-4.6` | `openai/gpt-4o-mini` |
| Tech Stack Generator | `openai/gpt-5.2-codex` | `openai/gpt-4o-mini` |
| Realtime Spec Generator | `anthropic/claude-sonnet-4` | `openai/gpt-4o-mini` |
| Architecture Generator | `anthropic/claude-sonnet-4` | `openai/gpt-4o-mini` |
| State Machine Generator | `anthropic/claude-sonnet-4` | `openai/gpt-4o-mini` |
| Component Composition | `anthropic/claude-sonnet-4` | `openai/gpt-4o-mini` |
| Layout Orchestrator | `anthropic/claude-sonnet-4` | `anthropic/claude-sonnet-4` |
| Data Dictionary Generator | — | `openai/gpt-4o-mini` |
| UX Design Generator | — | `openai/gpt-4o-mini` |

### Feedback und Analyse

| Zweck | Modell | Datei |
| --- | --- | --- |
| Feedback Model | `google/gemini-3-flash-preview` | `re_config.yaml:72` |
| Summary Model | `google/gemini-3-flash-preview` | `re_config.yaml:78` |
| Propagation Analyzer | `anthropic/claude-haiku-4.5` | `re_config.yaml:520`, `llm_analyzer.py:43` |
| Refinement LLM | `google/gemini-3-flash-preview` | `re_config.yaml:683` |
| Refinement Embeddings | `text-embedding-3-small` | `re_config.yaml:695`, `semantic_matcher.py:30` |
| Self-Critique | `google/gemini-2.0-flash-exp:free` | `self_critique.py:397` |
| Draft Engine | `openai/gpt-4o-mini` | `re_draft_engine.py:284` |
| Improver | `google/gemini-2.0-flash-exp:free` | `re_improver.py:272` |

### Presentation Agents (re_config.yaml)

| Agent-Gruppe | Modell |
| --- | --- |
| Scaffold Agents (Phase 2) | `anthropic/claude-opus-4.6` + `google/gemini-3-flash-preview` |
| Screen Design Agents (Phase 3) | `anthropic/claude-opus-4.6` + `google/gemini-3-flash-preview` |
| HTML/Content Agents | `anthropic/claude-opus-4.6` |
| Base Presentation Default | `anthropic/claude-3.5-sonnet` |

### Wizard Agents (AutoGen SocietyOfMind)

| Team | Modell | Datei:Zeile |
| --- | --- | --- |
| StakeholderTeam | `google/gemini-2.5-flash-preview` | `wizard_agents.py:273` |
| ContextEnricherTeam | `google/gemini-2.5-flash-preview` | `wizard_agents.py:400` |
| RequirementGapTeam | `anthropic/claude-opus-4.6` | `wizard_agents.py:496` |
| ConstraintTeam | `google/gemini-2.5-flash-preview` | `wizard_agents.py:610` |

### Weitere RE-Konfigurationen

| Zweck | Modell | Datei |
| --- | --- | --- |
| BFTS (alle Stages) | `openrouter/anthropic/claude-3.5-haiku` | `bfts_config.yaml:26,57,63,69,80,84` |
| gRPC Worker Main | `anthropic/claude-sonnet-4-20250514` | `grpc_worker/config.yaml:23` |
| gRPC Worker Fallback | `openai/gpt-4o-mini` | `grpc_worker/config.yaml:26` |
| Dashboard Server | `anthropic/claude-haiku-4.5` | `dashboard/server.py:1792` |
| Kilo Agent | `gpt-4o-mini` | `kilo/run_kilo_agent.py:15` |
| Multi-Agent Default | `anthropic/claude-3.5-sonnet` | `re_config.yaml:319` |
| Kilo Agent (config) | `openai/gpt-5.2-codex` | `re_config.yaml:115` |
| run_re_system UI Design | `anthropic/claude-opus-4.5` | `run_re_system.py:2920` |

### External Arch Team

| Zweck | Modell | Datei |
| --- | --- | --- |
| Arch Team Default | `google/gemini-2.5-flash:nitro` | `external/arch_team/backend/core/settings.py:28` |
| Arch Team MCP Server | `gpt-4o-mini` | `external/arch_team/mcp_server/config.py:27` |
| Arch Team Importer | `anthropic/claude-haiku-4.5` | `importers/arch_team_importer.py:80` |

---

## Schedule Space

Kein LLM-Einsatz (rein APScheduler).

## Research Space

Kein direkter LLM-Einsatz (delegiert an ZeroClaw Gateway).

---

## Alle Environment Variables (40+)

### API Keys (8)

| Variable | Provider |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI Direct (Voice, Summarization) |
| `OPENROUTER_API_KEY` | OpenRouter (Hauptprovider, ~35 Stellen) |
| `ANTHROPIC_API_KEY` | Anthropic SDK (Coding Engine) |
| `GOOGLE_API_KEY` | Google Gemini (Rewrite Worker) |
| `GEMINI_API_KEY` | Google Gemini (AI Scientist) |
| `DEEPSEEK_API_KEY` | DeepSeek (AI Scientist) |
| `HUGGINGFACE_API_KEY` | HuggingFace (AI Scientist) |
| `OLLAMA_API_KEY` | Ollama lokal |

### Modell-Overrides

| Gruppe | Variables |
| --- | --- |
| Voice (1) | `OPENAI_REALTIME_MODEL` |
| Swarm (11) | `CLASSIFIER_MODEL`, `RAG_CLASSIFIER_MODEL`, `RESPONSE_MODEL`, `ORCHESTRATOR_MODEL`, `DROPE_MODEL`, `ANALYSIS_MODEL`, `CONVERSION_MODEL`, `PERSONALITY_MODEL`, `STREAM_LISTENER_MODEL`, `SPACE_AGENT_MODEL`, `OPENROUTER_MODEL` |
| Broadcast (2) | `PROFILING_MODEL`, `CONTEXT_MODEL` |
| Workers (3) | `OPENAI_SUMMARIZATION_MODEL`, `GEMINI_MODEL`, `OLLAMA_MODEL` |
| Ideas (6) | `OPENROUTER_SUMMARY_MODEL`, `OPENROUTER_REWRITE_MODEL`, `OPENROUTER_WHITEPAPER_MODEL`, `OPENROUTER_STRUCTURE_MODEL`, `OPENROUTER_FEATURE_MODEL`, `OPENROUTER_EVAL_MODEL` |
| Coding Engine (7) | `LLM_MODEL_PRIMARY`, `LLM_MODEL_CLI`, `LLM_MODEL_MCP_STANDARD`, `LLM_MODEL_MCP_AGENT`, `LLM_MODEL_JUDGE`, `LLM_MODEL_REASONING`, `LLM_MODEL_ENRICHMENT` |
| Desktop (5) | `LLM_MODEL`, `VISION_MODEL`, `COMPACTION_MODEL`, `AUTOGEN_MODEL`, `AUTOGEN_VISION_MODEL` |
| Spaces (3) | `MINIBOOK_ENRICHMENT_MODEL`, `ROWBOAT_MODEL`, `MESSAGING_OLLAMA_MODEL` |
| RE (1) | `PROPAGATION_MODEL` |

---

## Hardcoded Modelle (ohne Env-Var Override)

| Modell | Stellen | Wo |
| --- | --- | --- |
| `anthropic/claude-3.5-haiku` | 6x | Ideas `exploration_tools.py` |
| `anthropic/claude-sonnet-4.5` | 1x | Ideas `format_dispatcher.py` |
| `anthropic/claude-sonnet-4-6` | 1x | Ideas `structured_formatting_tools.py` |
| `anthropic/claude-sonnet-4` | 2x | Ideas `idea_tools.py`, Desktop Moire (2x) |
| `anthropic/claude-3.5-sonnet` | 1x | Desktop Moire Quick |
| `anthropic/claude-opus-4-5-20251101` | 1x | `claude_worker.py` |
| `gpt-4` | 1x | Ideas `autogen_research.py` |
| `gpt-4o-mini` | 1x | Ideas `connection_evaluator.py` |
| `openai/gpt-4o-mini` | 2x | Swarm `collector_agent.py`, Desktop subagents |
| `google/gemini-2.0-flash-001` | 1x | Desktop `classification_agent.py` |
| `anthropic/claude-sonnet-4-20250514` | 1x | Desktop `task_decomposer.py` |
| `gpt-4.1` | 1x | Rowboat `simulation.py` |
| RE-Modelle in `re_config.yaml` | 30+ | Shuttles Requirements Engineer |
| AI Scientist Modelle | 92+ | Shuttles `ai_scientist/llm.py` |

---

## Veraltete Modelle

| Modell | Empfohlener Nachfolger | Stellen |
| --- | --- | --- |
| `claude-3.5-haiku` | `claude-haiku-4.5` | 6x exploration_tools, 4x swarm |
| `claude-3.5-sonnet` | `claude-sonnet-4` | 1x Moire Quick, 1x RE base_presentation |
| `gpt-4` | `gpt-4o-mini` | 1x autogen_research |
| `claude-sonnet-4.5` | `claude-sonnet-4-6` | 1x format_dispatcher |

---

## Modell-Statistik

| Modell | Verwendungen | Typischer Einsatz |
| --- | --- | --- |
| `openai/gpt-4o-mini` | ~15x | Lightweight (Routing, Summarization, Fallback) |
| `anthropic/claude-3.5-haiku` | ~10x | Classification, Analysis, Exploration |
| `anthropic/claude-sonnet-4` | ~8x | Reasoning, Orchestration, Architecture |
| `claude-sonnet-4-6` | ~6x | Coding Engine (Primary) |
| `openai/gpt-5.2-codex` | ~18x | Requirements Engineer (Code/Spec Generation) |
| `anthropic/claude-opus-4.6` | ~12x | Requirements Engineer (Presentation/Complex) |
| `google/gemini-3-flash-preview` | ~8x | Requirements Engineer (Feedback/Analysis) |
| `google/gemini-2.0-flash-001` | ~3x | Rewriting, Desktop Classification |
| `anthropic/claude-haiku-4.5` | ~4x | RE Propagation, Dashboard, Arch Team |
| `google/gemini-2.5-flash-preview` | ~3x | Wizard Agents |
| `gpt-4o-realtime-preview` | 1x | Voice (Rachel) |
| `anthropic/claude-opus-4.5` | 1x | RAG Classification |
| `gemini-1.5-flash` | 1x | Rewrite Worker |
| `qwen2.5:3b` | 1x | Messaging Filter (lokal) |
| `llama3.1:8b` | 1x | Ollama Fallback |
| `all-MiniLM-L6-v2` | ~3x | Embeddings |
| `text-embedding-3-small` | ~3x | API Embeddings |
| `grok-2-latest` | 1x | Fungus Search Config |
