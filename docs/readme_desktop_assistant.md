# Desktop Assistant

**Unified AI operating system bringing coordinated multi-agent intelligence to the desktop**

## Overview

The Desktop Assistant folder represents the top-level container and project root for Vibemind—the comprehensive AI-powered desktop assistant platform. It encompasses the entire product architecture, serving as the parent directory for all specialized spaces and coordinating their operations into a cohesive intelligence augmentation system.

Rather than offering single-purpose AI capabilities, Vibemind's Desktop Assistant architecture delegates different workstreams to specialized agents and spaces, each optimized for specific domains: software engineering, creative ideation, knowledge management, desktop automation, workflow generation, and more. The Desktop Assistant tier orchestrates these specialized systems, routing user requests to appropriate spaces and synthesizing their outputs into unified, actionable intelligence.

## Key Features & Contents

- **Ideas.Space**: Creative brainstorming, bubble/idea management, and voice-driven intention capture
- **Coding.Space**: Software engineering platform with LLM-driven code generation and preview environments
- **Desktop.Space**: System-level integration, eye tracking, screen analysis, and desktop automation
- **Rowboat.Space**: Knowledge graph, data orchestration, and business data integration
- **AgentFarm.Space**: Electron UI shell for agent orchestration; backend runtime is Captain Cook (`spaces/captain_cook`), tool-only by design (no chat agent) — see note below
- **N8n.Space**: Workflow automation and integration generation with 200+ connectors
- **Research.Space**: ZeroClaw web research, scraping, and summarization
- **Minibook.Space**: Inter-space collaboration hub for cross-domain tasks
- **Schedule.Space**: APScheduler-based task scheduling and time management
- **Software_Design.Space**: Requirements analysis and architectural design (Shuttles/SWE Design submodule)
- **The_Brain.Space**: Neuroscience-inspired cognitive system with standalone microservices
- **Video.Space**: Video-Produktion mit Team-Videos, Vision-Videos (Sora AI), Product-Demos und Deepfake/Lipsync
- **Context Layer**: Supermemory-based persistent memory system supporting all spaces
- **Infrastructure Stack**: DSGVO-compliant deployment options (local Ollama, cloud, custom endpoints)

> **Hinweis:** 13 Spaces haben dedizierte Backend-Agents (Bubbles, Ideas, Coding, Desktop, Roarboot, Research, Minibook, Schedule, N8n, AgentFarm, Video, MiroFish, Flowzen). Brain läuft als standalone Microservices.
>
> **Nachtrag (2026-09-22):** Diese 13 Namen sind exakt die `__all__`-Liste der
> alten, Python-lokalen Backend-Agents in
> `voice/python/swarm/backend_agents/__init__.py`. Am 2026-06-16 (Commit
> `ec98a0c6`) wurde der Python-Code für mehrere davon entfernt — bestätigt für
> Desktop, Coding, Bubbles/Ideas; die lazy-Imports zeigen seither auf nicht
> mehr vorhandene Pfade. Das ist aber keine Lücke: die aktuelle Routing-SoT
> `config/space_agent_registry.yml` (Stand 2026-09-08) führt praktisch
> dieselben Spaces mit `enabled: true` und einem eigenen OpenFang-Agenten
> (`brain-bubbles`, `brain-ideas`, `brain-coder`, `brain-desktop`,
> `brain-researcher`, `brain-knowledge`, `brain-scheduler`, `brain-n8n`,
> `brain-video`, `rowboat-chat` für Rowboat/Roarboot, `brain-forecaster` für
> MiroFish, `brain-wellness` für Flowzen) — „dedizierter Backend-Agent" stimmt
> für diese 12 weiterhin, nur über einen anderen Mechanismus als 2026-04-02
> beschrieben (OpenFang statt `python/swarm/backend_agents/`). Die einzige
> echte Ausnahme ist AgentFarm: dort führt die Registry `agent: null` — laut
> dortigem Kommentar bewusst „tool-only: no chat agent", weil Captain Cook
> (`spaces/captain_cook`, aktiver Dienst) die Orchestrierung übernimmt, ohne
> dass ein Chat-Agent dafür gebraucht wird. Details:
> `docs/operations/2026-08-18-p1-agentfarm-captain-cook-befund.md`.

## Current Status

- **Core Architecture**: Operational with 15 domain spaces and 13 dedicated backend agents
- **Orchestration**: Multi-space routing and coordination system functional for standard workflows
- **UI Integration**: 3D Multiverse (Three.js) with 9 visual spaces; ClawPort React Dashboard (5 Tabs: Schedule, Agents, Chat, Memory, Plugins)
- **Voice Interface**: Rachel as single voice agent routing through IntentOrchestrator
- **Documentation & Licensing**: Ongoing evaluation of open-source strategy

## Roadmap

- **Phase 1** (Q2 2026): Optimize inter-space communication patterns and reduce latency for multi-space workflows
- **Phase 2** (Q3 2026): Implement automated space selection algorithm to route tasks to optimal space based on context
- **Phase 3** (Q4 2026): Develop space marketplace infrastructure allowing third-party space creation and integration
- **Phase 4** (2027): Enable collaborative space instances for team-based problem solving with shared context
- **Phase 5** (2027+): Build specialized vertical spaces (legal, healthcare, finance) through partnerships

## Ecosystem Fit

Vibemind's Desktop Assistant is a reimagining of how AI integrates into knowledge work. Rather than a general assistant that does everything adequately, it's a specialized team of AI agents, each expert in their domain, working together toward the user's goals. This architecture addresses the enterprise need for depth without losing coordination.

The platform creates multiple value streams:

- **For knowledge workers**: A capable team of AI specialists always available
- **For enterprises**: Deployable intelligence augmentation without vendor lock-in (GDPR-compliant local options)
- **For developers**: A modular, extensible platform for building AI-native applications
- **For researchers**: A testbed for multi-agent coordination and specialized AI evaluation
