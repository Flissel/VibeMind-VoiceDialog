# Brain Space (Tahlamus)

Neuroscience-inspired cognitive routing system. Standalone submodule with its own microservices architecture.

## Overview

The Brain space is not a traditional VibeMind backend agent. It's a standalone system (`the_brain/` git submodule) providing:

- **5-Ring Radial Attention Network** — Sensory → Pattern → Semantic → Abstract → Meta
- **10 Neuromodulation Bridges** — Neuromod, Cortex, Limbic, Sleep/Wake, Motor, etc.
- **Thalamic Gating** — 10 modalities (6 sensory + 4 conversation trace)
- **Multi-CTM Ensemble** — Spatial, Logic, Temporal, Value (4 domains)
- **3-Layer Hierarchical Routing** — TaskFeature → ConversationPath → Decision
- **43 Neuroscience Modules** (Phases C–F) — PFC, ACC, Amygdala, Hippocampus, etc.
- **14 Cognitive Agents** via AutoGen swarm
- **77% routing accuracy** with continuous Hebbian learning

## Architecture

```
5 Microservices:
    ├── Brain Server     (port 5000)  — Central unified brain + dashboards
    ├── Swarm Server     (port 5002)  — 14 cognitive agents (AutoGen)
    ├── Memory API       (port 8001)  — Supermemory integration
    ├── Production API   (port 5001)  — Legacy REST API
    └── Dashboard        (port 5000)  — Brain visualization + chat
```

## LLM Integration

| Model | Role |
|-------|------|
| GPT-4o | Communication |
| DeepSeek R1 | Reasoning |
| Claude 3.5 | Planning |
| Gemini Flash | Memory |

## 9-Phase Cognitive Loop

Perceive → Appraise → Remember → Attend → Modulate → Reason → Reflect → Learn → Consolidate

## Dashboards

| URL | View |
|-----|------|
| `http://localhost:5000` | Main dashboard |
| `http://localhost:5000/brain` | Brain visualization |
| `http://localhost:5000/radial` | Radial dashboard |

## Startup

```bash
cd python/spaces/brain/the_brain
python -m web.brain_server     # Port 5000
```

## 3D UI (Electron)

Dedicated 3D scene in multiverse: organic deformed brain mesh, 60 neuron particles, synaptic connections, brain stem, floating thought bubbles with pulsing animation.

## Directory

```
python/spaces/brain/
└── the_brain/               # Git submodule (github.com/Flissel/the_brain)
    ├── web/                 # Brain Server (Flask)
    ├── agents/              # 14 cognitive agents
    ├── core/                # Routing, gating, modulation
    ├── memory/              # Supermemory integration
    └── dashboards/          # Web visualizations
```

## Key Differences from Other Spaces

| Aspect | Standard Space | Brain Space |
|--------|---------------|-------------|
| Agent | BaseBackendAgent subclass | Standalone microservices |
| Stream | Redis stream | HTTP APIs (ports 5000–5002) |
| Tools | Python functions | 14 cognitive agents |
| Integration | IPC via Electron | Submodule with own dashboards |
