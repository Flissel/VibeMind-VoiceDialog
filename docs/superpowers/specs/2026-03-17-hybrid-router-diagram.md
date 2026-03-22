# HybridRouter — Architecture Diagrams

## 1. Hauptfluss: 5-Tier Routing

```mermaid
flowchart TD
    USER["User Voice / Dashboard Chat"] --> ORCH["IntentOrchestrator.process_intent()"]

    ORCH --> SESSION["① Session resolven<br/>IdentityLinks → canonical_id<br/>SessionStore.get_or_create()"]

    SESSION --> CLASSIFY["② IntentClassifier<br/>LLM oder Ollama<br/>→ event_type + payload"]

    CLASSIFY --> CACHE{"Route Cache<br/>Hit?"}
    CACHE -->|Hit| RESULT["RouteResult<br/>(cached=true)"]
    CACHE -->|Miss| T1

    subgraph HYBRID["③ HybridRouter.resolve()"]
        T1{"Tier 1<br/>Prefix Match"}
        T1 -->|"bubble.create → ideas"| MATCH1["✓ binding.prefix"]
        T1 -->|Miss| T2

        T2{"Tier 2<br/>Keyword Match"}
        T2 -->|"'Screenshot' → desktop"| MATCH2["✓ binding.keyword"]
        T2 -->|Miss| T3

        T3{"Tier 3<br/>Context Match"}
        T3 -->|"current_space=coding"| MATCH3["✓ binding.context"]
        T3 -->|Miss| T4

        T4{"Tier 4<br/>LLM SpaceRouter"}
        T4 -->|"Single Space"| MATCH4["✓ binding.llm"]
        T4 -->|"Multi Space"| T5
        T4 -->|Fail| DEFAULT["Default → ideas"]

        T5["Tier 5<br/>Multi-Space"] --> MULTI["MultiSpaceExecutor"]
    end

    MATCH1 --> EXEC
    MATCH2 --> EXEC
    MATCH3 --> EXEC
    MATCH4 --> EXEC
    DEFAULT --> EXEC

    EXEC["④ Direct Tool Execution<br/>_tool_executors[event_type]()"] --> UPDATE

    MULTI --> MINIBOOK["MinibookHub.dispatch()<br/>EnrichmentPipeline"]
    MINIBOOK --> MSE["MultiSpaceExecutor<br/>Pipeline / Parallel / Mixed"]
    MSE --> UPDATE

    UPDATE["⑤ Session Update<br/>last_route + history"] --> BROADCAST

    BROADCAST["⑥ Ergebnis<br/>_broadcast_to_electron()<br/>inject_system_message()"]
    RESULT --> EXEC

    style HYBRID fill:#1a1a2e,stroke:#e94560,color:#fff
    style T1 fill:#0f3460,stroke:#e94560,color:#fff
    style T2 fill:#0f3460,stroke:#e94560,color:#fff
    style T3 fill:#0f3460,stroke:#e94560,color:#fff
    style T4 fill:#0f3460,stroke:#e94560,color:#fff
    style T5 fill:#533483,stroke:#e94560,color:#fff
    style MULTI fill:#533483,stroke:#e94560,color:#fff
    style EXEC fill:#16213e,stroke:#0f3460,color:#fff
    style MSE fill:#533483,stroke:#e94560,color:#fff
```

## 2. Multi-Space Strategien

```mermaid
flowchart LR
    subgraph PARALLEL["Strategy: PARALLEL"]
        direction TB
        P_IN["'Erstelle Idee UND setze Termin'"] --> P_PHASE["Phase 1"]
        P_PHASE --> P_IDEAS["Ideas<br/>idea.create"]
        P_PHASE --> P_SCHED["Schedule<br/>schedule.create"]
        P_IDEAS --> P_MERGE["Merge Results"]
        P_SCHED --> P_MERGE
    end

    subgraph PIPELINE["Strategy: PIPELINE"]
        direction TB
        PI_IN["'Recherchiere KI und erstelle<br/>daraus eine Idee'"] --> PI_P1["Phase 1"]
        PI_P1 --> PI_RES["Research<br/>research.search"]
        PI_RES -->|"findings, sources"| PI_P2["Phase 2"]
        PI_P2 --> PI_IDEAS["Ideas<br/>idea.create<br/>+ Research Context"]
        PI_IDEAS --> PI_MERGE["Merge Results"]
    end

    subgraph MIXED["Strategy: MIXED"]
        direction TB
        M_IN["'Recherchiere KI, erstelle Idee,<br/>plane Meeting'"] --> M_P1["Phase 1"]
        M_P1 --> M_RES["Research"]
        M_P1 --> M_SCHED["Schedule"]
        M_RES -->|findings| M_P2["Phase 2"]
        M_SCHED --> M_MERGE["Merge"]
        M_P2 --> M_IDEAS["Ideas<br/>+ Research Context"]
        M_IDEAS --> M_MERGE
    end

    style PARALLEL fill:#1a1a2e,stroke:#00b4d8,color:#fff
    style PIPELINE fill:#1a1a2e,stroke:#e94560,color:#fff
    style MIXED fill:#1a1a2e,stroke:#f77f00,color:#fff
```

## 3. Session Management + Identity Links

```mermaid
flowchart TD
    subgraph CHANNELS["Eingabekanäle"]
        VOICE["🎤 Voice<br/>peer: voice_user_123"]
        CHAT["💬 Dashboard Chat<br/>peer: dashboard_felix"]
        API["🔌 API<br/>peer: api_client_1"]
    end

    subgraph IDENTITY["IdentityLinkResolver"]
        VOICE -->|resolve| IL["identity_links DB<br/>voice + voice_user_123 → canonical:felix<br/>chat + dashboard_felix → canonical:felix"]
        CHAT -->|resolve| IL
        API -->|resolve| IL
        IL --> CANONICAL["canonical:felix"]
    end

    CANONICAL --> SK["SessionKey<br/>agent:orchestrator:voice:direct:felix"]

    subgraph STORE["SessionStore (SQLite)"]
        SK --> SESSIONS["sessions<br/>─────────────<br/>session_key<br/>agent_id<br/>channel<br/>canonical_id<br/>space_state (JSON)<br/>last_route (JSON)<br/>last_active"]

        SK --> HISTORY["session_history<br/>─────────────<br/>session_key<br/>speaker<br/>text<br/>event_type<br/>timestamp<br/>(last 20 turns)"]
    end

    SESSIONS -->|last_route| DROPE["DroPE Resolver<br/>'Mach das nochmal'<br/>→ Wiederhole: bubble.create"]

    style CHANNELS fill:#1a1a2e,stroke:#00b4d8,color:#fff
    style IDENTITY fill:#16213e,stroke:#e94560,color:#fff
    style STORE fill:#0f3460,stroke:#00b4d8,color:#fff
```

## 4. Cache-Architektur

```mermaid
flowchart LR
    INPUT["event_type +<br/>user_input"] --> EC{"EventTypeCache<br/>~80 Einträge<br/>Permanent"}

    EC -->|Hit: 0.001ms| RESULT["RouteResult"]
    EC -->|Miss| CC{"ClassificationCache<br/>max 2000 Einträge<br/>TTL: 5min"}

    CC -->|Hit| RESULT
    CC -->|Miss| LLM["LLM SpaceRouter<br/>~300ms"]

    LLM -->|Speichern| CC
    LLM --> RESULT

    subgraph PERF["Performance"]
        direction TB
        P1["Tier 1 cached: 0.001ms"]
        P2["Tier 2 keyword: 0.001ms"]
        P3["Tier 4 LLM cached: 0.001ms"]
        P4["Tier 4 LLM uncached: ~300ms"]
        P5["Tier 5 multi-space: 5-120s"]
    end

    style EC fill:#0f3460,stroke:#00b4d8,color:#fff
    style CC fill:#0f3460,stroke:#f77f00,color:#fff
    style LLM fill:#533483,stroke:#e94560,color:#fff
    style PERF fill:#1a1a2e,stroke:#00b4d8,color:#fff
```

## 5. Dateistruktur

```mermaid
graph TD
    subgraph ROUTING["python/swarm/routing/"]
        INIT["__init__.py<br/>Public API"]
        TYPES["types.py<br/>SpaceBinding, RouteResult,<br/>SessionKey, SessionEntry,<br/>MultiSpaceStrategy"]
        BIND["bindings_registry.py<br/>Auto-gen from EVENT_TO_TOOL<br/>+ Keyword patterns"]
        CACHE["route_cache.py<br/>EventTypeCache +<br/>ClassificationCache"]
        HR["hybrid_router.py<br/>5-Tier resolve()"]
        SS["session_store.py<br/>SQLite sessions"]
        IL["identity_links.py<br/>Cross-channel mapping"]
        MSE["multi_space_executor.py<br/>Pipeline/Parallel/Mixed"]
        KC["keyword_classifier.py<br/>Deterministic fallback"]
    end

    subgraph MODIFIED["Geänderte Dateien"]
        IO["intent_orchestrator.py<br/>Phase 0 HybridRouter"]
        RR["reference_resolver.py<br/>DroPE + last_route"]
        DB["database.py<br/>Schema v17"]
        ENV[".env.example<br/>USE_HYBRID_ROUTER"]
    end

    HR --> TYPES
    HR --> BIND
    HR --> CACHE
    HR --> MSE
    SS --> TYPES
    IL --> SS
    IO --> HR
    IO --> SS
    RR --> SS

    style ROUTING fill:#1a1a2e,stroke:#e94560,color:#fff
    style MODIFIED fill:#16213e,stroke:#f77f00,color:#fff
```

## 6. Tier-Entscheidungsmatrix

```mermaid
graph LR
    subgraph EXAMPLES["Beispiele pro Tier"]
        direction TB
        E1["<b>Tier 1 — Prefix</b><br/>'Erstelle Bubble Marketing'<br/>→ bubble.create → ideas<br/>⏱ 0.001ms"]
        E2["<b>Tier 2 — Keyword</b><br/>'Mach einen Screenshot'<br/>→ regex: screenshot → desktop<br/>⏱ 0.001ms"]
        E3["<b>Tier 3 — Context</b><br/>'Zeig mir alles' (in Coding)<br/>→ current_space=coding<br/>⏱ 0.001ms"]
        E4["<b>Tier 4 — LLM</b><br/>'Hilf mir beim Programmieren'<br/>→ SpaceRouter → coding<br/>⏱ ~300ms"]
        E5["<b>Tier 5 — Multi-Space</b><br/>'Recherchiere und erstelle Idee'<br/>→ Research + Ideas Pipeline<br/>⏱ 5-120s"]
    end

    E1 --> |"90% aller<br/>Intents"| FAST["⚡ Deterministisch<br/>Kein LLM nötig"]
    E2 --> FAST
    E3 --> FAST
    E4 --> |"~8%"| MEDIUM["🧠 LLM-basiert<br/>Cached nach 1. Aufruf"]
    E5 --> |"~2%"| SLOW["🔄 Multi-Space<br/>MinibookHub Pipeline"]

    style FAST fill:#00b894,stroke:#00b894,color:#fff
    style MEDIUM fill:#fdcb6e,stroke:#fdcb6e,color:#000
    style SLOW fill:#e17055,stroke:#e17055,color:#fff
```
