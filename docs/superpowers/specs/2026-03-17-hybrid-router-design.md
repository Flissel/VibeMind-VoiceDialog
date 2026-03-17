# HybridRouter Design Spec

**Date:** 2026-03-17
**Status:** Draft
**Scope:** Tier-based routing + caching + session management for VibeMind intent routing

## Problem Statement

VibeMind routes every intent through MinibookHub's LLM-based pipeline, even deterministic ones like `bubble.create → Ideas`. This adds ~2s latency and unnecessary LLM calls for 90% of intents that have a known, static space mapping. Additionally, VibeMind lacks session state between spaces and cross-channel identity linking.

## Goals

1. **Performance** — Resolve 90% of intents deterministically in <100ms (no LLM, no Minibook roundtrip)
2. **Session Management** — Persistent sessions per space with cross-channel identity linking
3. **Debuggability** — Every route decision includes a `matchedBy` field explaining why
4. **Backward Compatibility** — MinibookHub remains for multi-space collaboration (Tier 5)

## Non-Goals

- Replacing MinibookHub entirely
- Changing IntentClassifier or Backend Agent interfaces
- Modifying Electron IPC message types

---

## Architecture Overview

```
User Voice / Dashboard Chat
         │
         ▼
┌─── IntentOrchestrator.process_intent() ───┐
│                                            │
│  ① Session resolven                        │
│     ├─ Identity Links → canonical_id       │
│     └─ SessionStore.get_or_create()        │
│                                            │
│  ② IntentClassifier → event_type + payload │
│     (unverändert, wie bisher)              │
│                                            │
│  ③ HybridRouter.resolve(event_type, input) │
│     │                                      │
│     ├─ Cache Hit? → RouteResult sofort     │
│     │                                      │
│     ├─ Tier 1: Prefix-Match               │
│     │   "bubble.create" → Ideas ✓          │
│     │                                      │
│     ├─ Tier 2: Keyword-Match              │
│     │   "Screenshot machen" → Desktop ✓    │
│     │                                      │
│     ├─ Tier 3: Context-Match              │
│     │   (aktueller Space als Hint)         │
│     │                                      │
│     ├─ Tier 4: LLM SpaceRouter            │
│     │   mehrdeutig → LLM entscheidet       │
│     │                                      │
│     └─ Tier 5: Multi-Space → MinibookHub  │
│         "Recherchiere + erstelle Idee"     │
│                                            │
│  ④ Execution                               │
│     ├─ Single-Space: Direct execute        │
│     │   (kein Minibook-Roundtrip)          │
│     └─ Multi-Space: MultiSpaceExecutor     │
│                                            │
│  ⑤ Session updaten                         │
│     ├─ last_route speichern                │
│     ├─ conversation_history append         │
│     └─ space_state aktualisieren           │
│                                            │
│  ⑥ Ergebnis                                │
│     ├─ _broadcast_to_electron()            │
│     └─ inject_system_message() → Rachel    │
└────────────────────────────────────────────┘
```

---

## Component 1: Tier-Based Routing

### 5 Tiers (first match wins)

| Tier | Name | Match Condition | Example | Cacheable |
|------|------|-----------------|---------|-----------|
| **1** | `binding.prefix` | event_type prefix known statically | `bubble.create` → Ideas | Yes (permanent) |
| **2** | `binding.keyword` | Keyword regex match | "Screenshot" → Desktop | Yes (permanent) |
| **3** | `binding.context` | Current space as routing hint | In Desktop → prefer Desktop | No |
| **4** | `binding.llm` | SpaceRouter LLM classification | Ambiguous → LLM decides | Yes (5 min TTL) |
| **5** | `binding.minibook` | Multi-space detected | "Recherchiere und erstelle" → MinibookHub | No |

### Bindings Registry

Auto-generated from existing `BaseBackendAgent.EVENT_TO_TOOL` definitions at startup (note: agents use `EVENT_TO_TOOL`, not `TOOL_MAP`):

```python
SPACE_BINDINGS = {
    # Tier 1: Event-Type Prefix → Space (deterministic)
    "bubble.*":    SpaceBinding(space="ideas",    agent="BubblesAgent"),
    "idea.*":      SpaceBinding(space="ideas",    agent="IdeasAgent"),
    "code.*":      SpaceBinding(space="coding",   agent="CodingAgent"),
    "desktop.*":   SpaceBinding(space="desktop",  agent="DesktopAgent"),
    "web.*":       SpaceBinding(space="desktop",  agent="DesktopAgent"),
    "messaging.*": SpaceBinding(space="desktop",  agent="DesktopAgent"),
    "openclaw.*":  SpaceBinding(space="desktop",  agent="DesktopAgent"),
    "roarboot.*":  SpaceBinding(space="rowboat",  agent="RoarbootAgent"),
    "research.*":  SpaceBinding(space="research", agent="ZeroClawAgent"),
    "minibook.*":  SpaceBinding(space="minibook", agent="MinibookAgent"),
    "schedule.*":  SpaceBinding(space="schedule", agent="ScheduleAgent"),
    "n8n.*":       SpaceBinding(space="n8n",      agent="N8nAgent"),

    # Tier 2: Keyword → Space (deterministic)
    "screenshot|bildschirm|klick|browser":  SpaceBinding(space="desktop", ...),
    "workflow|automatisierung|n8n":          SpaceBinding(space="n8n", ...),
    "termin|erinnerung|wecker|timer":        SpaceBinding(space="schedule", ...),
}
```

The registry is built automatically by scanning all `BaseBackendAgent` subclasses and extracting prefix patterns from their `EVENT_TO_TOOL` keys. No manual maintenance required.

> **Note:** The example above is illustrative. The actual registry is auto-generated at startup and will include all registered agents (including `video` and any future spaces).

### RouteResult

Every routing decision produces a `RouteResult` with debugging metadata:

```python
@dataclass
class RouteResult:
    space: str                          # "ideas", "desktop", etc.
    agent: str                          # "IdeasAgent", "DesktopAgent", etc.
    event_type: str                     # "bubble.create"
    matched_by: str                     # "binding.prefix:bubble.*" or "binding.llm"
    cached: bool                        # Was this served from cache?
    tier: int                           # Which tier matched (1-5)
    multi_space: MultiSpaceStrategy | None  # For Tier 5 only
```

### HybridRouter.resolve() Signature

```python
class HybridRouter:
    def resolve(
        self,
        event_type: str,
        user_input: str,
        session: SessionEntry | None = None,
        force_reclassify: bool = False,    # Bypass ClassificationCache
    ) -> RouteResult:
        """
        Resolve an intent to a space via 5-tier matching.

        force_reclassify=True skips ClassificationCache (Tier 4)
        but still uses EventTypeCache (Tier 1).
        """
```

---

## Component 2: Route Cache

Two cache layers:

| Cache | Key | Value | TTL | Max Entries | Invalidation |
|-------|-----|-------|-----|-------------|--------------|
| **EventTypeCache** | `event_type` string | `SpaceBinding` | Permanent | ~80 (all known event_types) | Config reload |
| **ClassificationCache** | `hash(normalize(user_input))` | `{event_type, space, confidence}` | 5 min | 2000 | TTL-based |

**Overflow behavior:** When max entries reached, clear entire cache and restart (same as OpenClaw — simple, no LRU overhead).

**Cache bypass:** Requests with `force_reclassify=True` skip the ClassificationCache but still use EventTypeCache.

---

## Component 3: Session Management

### SessionKey

```python
@dataclass
class SessionKey:
    agent_id: str        # "IdeasAgent", "DesktopAgent"
    channel: str         # "voice", "chat", "dashboard"
    scope: str           # "direct" (1 user), "shared" (dashboard)
    peer_id: str         # User-ID or "anonymous"
    thread_id: str|None  # Optional sub-conversation

    @property
    def key(self) -> str:
        """agent:ideas:voice:direct:user123"""
        base = f"agent:{self.agent_id}:{self.channel}:{self.scope}:{self.peer_id}"
        if self.thread_id:
            return f"{base}:thread:{self.thread_id}"
        return base

    @property
    def main_key(self) -> str:
        """agent:ideas:main — cross-channel main key"""
        return f"agent:{self.agent_id}:main"
```

### 3 Session Scopes

| Scope | Key Format | Use Case |
|-------|-----------|----------|
| `"main"` | `agent:{id}:main` | Default — all channels share one session per space |
| `"per-channel"` | `agent:{id}:{channel}:direct:{peer}` | Voice and chat have separate sessions |
| `"per-peer"` | `agent:{id}:direct:{peer}` | Cross-channel, but isolated per user |

Default is `"main"` — same context regardless of voice or dashboard input.

### Identity Links

Map different channel-specific peer IDs to a single canonical identity:

```python
IDENTITY_LINKS = {
    ("voice", "user_voice_123"): "canonical:felix",
    ("chat",  "dashboard_user"):  "canonical:felix",
}
```

Stored in SQLite `identity_links` table. When building a SessionKey, the peer_id is resolved to its canonical form first, enabling cross-channel session continuity.

### SessionStore

SQLite-backed, stores per-session state:

```python
class SessionStore:
    def get_or_create(self, key: SessionKey) -> SessionEntry
    def update_last_route(self, key: SessionKey, route: RouteResult)
    def get_cross_space_context(self, canonical_id: str) -> List[SessionEntry]
```

Each session tracks:

- **Last Route** — For "mach das nochmal" (DroPE integration)
- **Space State** — Current bubble, active project, etc.
- **User Preferences** — Language, format preferences

> **Relationship to existing `conversation_history` table:** The existing `conversation_history` table remains the authoritative voice transcript store (linked to `conversation_sessions`). The new `session_history` table tracks **routing-level turns** — it logs which event_type was routed where, per session_key. It is NOT a replacement for conversation_history but a per-routing-session audit log. The SessionStore's `get_or_create()` reads from `session_history` for routing context (last 20 routing turns) while conversation_history continues to serve the voice/chat transcript.

---

## Component 4: Multi-Space Coordination

### Strategy Selection

The SpaceRouter LLM determines dependencies between spaces and selects an execution strategy:

```python
@dataclass
class MultiSpaceStrategy:
    strategy: Literal["pipeline", "parallel", "mixed"]
    steps: List[ExecutionStep]

@dataclass
class ExecutionStep:
    space: str
    depends_on: List[str]       # Spaces that must complete first
    context_fields: List[str]   # Fields to carry from predecessors
```

### 3 Strategies

**PARALLEL** — No dependencies:
```
"Erstelle eine Idee und setze einen Termin"

steps:
  - {space: "ideas",    depends_on: []}
  - {space: "schedule", depends_on: []}

→ Both execute simultaneously, results independent
```

**PIPELINE** — Sequential dependency:
```
"Recherchiere KI-Trends und erstelle daraus eine Idee"

steps:
  - {space: "research", depends_on: []}
  - {space: "ideas",    depends_on: ["research"],
     context_fields: ["findings", "sources"]}

→ Research first, output becomes Ideas input
```

**MIXED** — Combination:
```
"Recherchiere KI, erstelle Idee daraus, und plane Meeting dafür"

steps:
  - {space: "research",  depends_on: []}              # Phase 1
  - {space: "ideas",     depends_on: ["research"]}     # Phase 2
  - {space: "schedule",  depends_on: []}               # Phase 1 (parallel to Research)

Execution:
  Phase 1: Research ║ Schedule  (parallel)
  Phase 2: Ideas (waits for Research)
```

### Dependency Detection

LLM prompt extension for the existing SpaceRouter:

```
Analyze the user intent and determine:
1. Which spaces are involved
2. Whether dependencies exist (signal words: "daraus", "damit",
   "basierend auf", "und dann", "danach")
3. Which data fields need to flow between spaces

Output as JSON:
{
  "strategy": "pipeline|parallel|mixed",
  "steps": [
    {"space": "research", "depends_on": [], "context_fields": []},
    {"space": "ideas", "depends_on": ["research"], "context_fields": ["findings"]}
  ]
}
```

### MultiSpaceExecutor (replaces MinibookHub's ResultAggregator.track_multi)

**Tier 5 execution path:** When HybridRouter returns Tier 5, `MinibookHub.dispatch()` delegates to `MultiSpaceExecutor` instead of the existing `ResultAggregator.track_multi()`. The existing ResultAggregator only supports parallel fan-out; MultiSpaceExecutor adds pipeline and mixed strategies. MinibookHub's enrichment (ContextGather, TaskEnricher) still runs before MultiSpaceExecutor — only the execution/coordination layer is replaced.

```python
class MultiSpaceExecutor:
    async def execute(self, strategy: MultiSpaceStrategy, payload: dict) -> dict:
        results = {}
        phases = self._build_phases(strategy.steps)

        for phase in phases:
            tasks = []
            for step in phase:
                enriched_payload = self._inject_context(payload, step, results)
                tasks.append(self._execute_space(step.space, enriched_payload))

            phase_results = await asyncio.gather(*tasks)
            for step, result in zip(phase, phase_results):
                results[step.space] = result

        return self._merge_results(results)
```

### Context Injection

How data flows from Space A to Space B in a pipeline:

```python
def _inject_context(self, payload, step, prior_results):
    enriched = {**payload}
    for dep_space in step.depends_on:
        dep_result = prior_results[dep_space]
        for field in step.context_fields:
            if field in dep_result:
                enriched[f"from_{dep_space}_{field}"] = dep_result[field]
        enriched["prior_context"] = (
            f"Ergebnis aus {dep_space}: {dep_result.get('summary', '')}"
        )
    return enriched
```

### Error Handling

| Scenario | Behavior |
|----------|----------|
| Pipeline step fails | Dependent steps skipped, partial result returned |
| Parallel step fails | Other steps continue, error marked in result |
| Timeout (120s total) | Cancel running steps, return partial results |

---

## Database Changes

Three new tables added to the existing SQLite schema:

```sql
CREATE TABLE sessions (
    session_key   TEXT PRIMARY KEY,
    agent_id      TEXT NOT NULL,
    channel       TEXT NOT NULL,
    canonical_id  TEXT,
    space_state   TEXT,          -- JSON
    last_route    TEXT,          -- JSON (RouteResult)
    last_active   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE session_history (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    session_key   TEXT NOT NULL REFERENCES sessions(session_key),
    speaker       TEXT NOT NULL,  -- "user" | "agent"
    text          TEXT NOT NULL,
    event_type    TEXT,
    timestamp     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE identity_links (
    channel       TEXT NOT NULL,
    peer_id       TEXT NOT NULL,
    canonical_id  TEXT NOT NULL,
    PRIMARY KEY (channel, peer_id)
);
```

Schema version bump to **v17** in `database.py` (current is v16 with `plugin_state` table). Migration v16→v17 adds these three tables.

---

## New Files

| File | Purpose |
|------|---------|
| `python/swarm/routing/__init__.py` | Public API: `HybridRouter`, `SessionStore`, `RouteResult` |
| `python/swarm/routing/hybrid_router.py` | HybridRouter — tier matching, cache, `resolve()` |
| `python/swarm/routing/bindings_registry.py` | Auto-generates `SPACE_BINDINGS` from Agent `EVENT_TO_TOOL` dicts |
| `python/swarm/routing/route_cache.py` | EventTypeCache + ClassificationCache |
| `python/swarm/routing/session_store.py` | SessionKey, SessionEntry, SQLite-backed store |
| `python/swarm/routing/identity_links.py` | Cross-channel user mapping |
| `python/swarm/routing/multi_space_executor.py` | MultiSpaceStrategy, phase execution, context injection |

## Modified Files

| File | Change |
|------|--------|
| `python/swarm/orchestrator/intent_orchestrator.py` | Replace MinibookHub exclusive-mode block (lines ~1239-1263): instead of returning error when MinibookHub returns None, fall through to HybridRouter for Tier 1-4. Only invoke MinibookHub when HybridRouter returns Tier 5. The current `if USE_MINIBOOK_HUB: return minibook_result` pattern becomes `if hybrid_result.tier == 5: return minibook_dispatch(...)` |
| `python/spaces/minibook/minibook_hub.py` | Only invoked for Tier 5 (multi-space) requests. `dispatch()` delegates to `MultiSpaceExecutor` for pipeline/mixed strategies instead of its current parallel-only `ResultAggregator.track_multi()` |
| `python/spaces/minibook/enrichment/space_router.py` | Deprecate `_route_by_event_type()` / `EVENT_TYPE_TO_SPACE` dict — this logic moves to HybridRouter Tier 1. SpaceRouter retains only its LLM-based routing (used by Tier 4) and the new dependency detection (Tier 5) |
| `python/data/database.py` | New tables: `sessions`, `session_history`, `identity_links` (schema v16→v17) |
| `python/swarm/orchestrator/reference_resolver.py` | DroPE reads `last_route` from SessionStore |

## Unchanged

- **IntentClassifier** — Still produces event_type + payload
- **Backend Agents** — No changes to EVENT_TO_TOOL or execution logic
- **Electron IPC** — Same broadcast message types
- **Tools** — No changes to tool functions

---

## Performance Expectations

| Scenario | Current (MinibookHub) | With HybridRouter |
|----------|----------------------|-------------------|
| `bubble.create` | ~2s (LLM + Minibook + Space) | ~100ms (Tier 1 cached + direct) |
| "Screenshot machen" | ~2s | ~200ms (Tier 2 keyword) |
| Ambiguous intent | ~2s | ~2s (Tier 4, LLM as before) |
| Multi-space | ~5-10s (Minibook async) | ~5-10s (Tier 5, strategy-dependent) |

---

## Configuration

New `.env` variables:

```bash
# HybridRouter
USE_HYBRID_ROUTER=true              # Enable HybridRouter (default: true)
HYBRID_ROUTER_CACHE_TTL=300         # Classification cache TTL in seconds (default: 300)
HYBRID_ROUTER_CACHE_MAX=2000        # Max classification cache entries (default: 2000)
HYBRID_ROUTER_SESSION_SCOPE=main    # "main", "per-channel", "per-peer" (default: "main")
HYBRID_ROUTER_DEBUG=false           # Log all tier decisions (default: false)
```

When `USE_HYBRID_ROUTER=false`, the system falls back to the existing MinibookHub-only path — full backward compatibility.
