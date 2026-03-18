# Multiverse (Main UI)

**3D-Orchestrierungsplattform mit Three.js, 9 visuellen Spaces und Voice-Dialog-Routing.**

## Overview

Multiverse ist die Haupt-UI und der Orchestrierungs-Hub von Vibemind. Es rendert 9 visuelle Spaces als 3D-Objekte mit Three.js und bietet Voice-Dialog als primären Interaktionsmodus. Das Voice-Interface routet die User-Intention via IntentClassifier an den passenden Space-Agent — jeder Space ist unabhängig und übernimmt die Execution eigenständig. Der Voice-Agent sendet nur die Absicht des Users an den richtigen Agent weiter.

## 3D-Multiverse: 9 visuelle Spaces

Definiert in `electron-app/renderer/multiverse.js`:

| Space | Icon | Agent-Name | Rolle | Position | Farbe |
|-------|------|-----------|-------|----------|-------|
| ideas | 💭 | Rachel | Idea Navigator | (0, 0, 0) | 0x4488ff (Blau) |
| projects | 🧬 | Coding | Project Manager | (16, 0, 11) | 0x44ff88 (Grün) |
| desktop | 🌟 | Hassan | Desktop Worker | (22, 0, -14) | 0xff8844 (Orange) |
| roarboot | 🚣 | Rowboat | Knowledge Navigator | (-17, 0, -8) | 0x22ccaa (Teal) |
| swedesign | 🏭 | Factory | Spec Generator | (8, 0, 5.5) | 0xff6633 (Rot-Orange) |
| clawport | 📊 | Dashboard | System Dashboard | (-8, 0, 12) | 0x8866ff (Lila) |
| agentfarm | 🏠 | Farmer | Agent Orchestrator | (-14, 0, 18) | 0x88aa44 (Olive) |
| thebrain | 🧠 | Brain | Knowledge Center | (14, 0, -22) | 0xff66aa (Pink) |
| video | 🎬 | Director | Video Producer | (-20, 0, 24) | 0xee4466 (Rot) |

> **Hinweis:** Agent-Namen sind UI-Labels für die jeweiligen Backend-Agents. Jeder Space ist unabhängig und handelt eigenständig — der Voice-Agent (Rachel) routet lediglich die User-Intention an den richtigen Space-Agent weiter. Die Spaces übernehmen dann die komplette Execution selbstständig.

## Key Components

| Datei | Zweck |
|-------|-------|
| `renderer/multiverse.js` | MultiverseApp: Three.js Scene, Camera, Simplex-Noise, Space-Navigation |
| `renderer/glass_bubbles.js` | Bootstrap, Roarboot-Status-Patching |
| `renderer/universe_canvas.js` | Canvas-Rendering |
| `renderer/exploration_dialog.js` | Explorations-UI |
| `renderer/rich_content_renderer.js` | Rich-Content-Anzeige |
| `renderer/shuttle_manager.js` | Shuttle/Requirements-Pipeline UI |
| `renderer/lib/three.min.js` | Three.js Library |
| `renderer/lib/OrbitControls.js` | Kamera-Steuerung |

## 3D-Features

- **Simplex-Noise Vertex-Displacement**: Organische Oberflächen für Space-Objekte
- **Pulse-Animation**: Lebendige Space-Darstellung
- **Camera-Interpolation**: Smooth Navigation zwischen Spaces
- **DNA-Helix Bubble-Rendering**: Ideen als DNA-Helix-Struktur
- **Hand-Gesture Navigation**: Gesten-basierte Steuerung
- **Organic Brain Mesh**: 60 Neuron-Partikel mit synaptischen Linien (TheBrain)

## Technology Stack

- **3D Engine**: Three.js mit OrbitControls
- **Voice Engine**: OpenAI Realtime API (speech-to-speech) via VoiceBridgeV2
- **Routing Engine**: IntentClassifier → EventRouter → Backend-Agents
- **Event Bus**: `python/swarm/event_bus.py` (Pub/Sub für Cross-Space-Kommunikation)
- **State Synchronization**: SQLite + IPC-Messages (Python ↔ Electron)
- **ClawPort Dashboard**: React-basiertes Monitoring-Overlay (5 Tabs: Schedule, Agents, Chat, Memory, Plugins)

## Current Status

- 3D Multiverse mit 9 visuellen Spaces ist voll funktional
- Voice-Dialog über Rachel → IntentClassifier → Backend-Agents operativ
- Three.js Rendering mit Simplex-Noise und Animationen
- Camera-Navigation zwischen Spaces funktioniert
- Shuttle Manager für Requirements-Pipeline integriert
- ClawPort React Dashboard (Schedule, Agents, Chat, Memory, Plugins)
- Exploration Dialog UI für AI-Scientist Sessions
- Intent-Routing zu 10 Backend-Agents (alle lazy-loaded in __init__.py)

## Roadmap

- Complete Desktop.Space context integration for full awareness (Q1-Q2 2026)
- Implement advanced intent understanding with multi-intent detection
- Build comprehensive event interlock system for complex workflows
- Add real-time space performance monitoring and load balancing
- Create workflow recording and replay for repeatable multi-space tasks
- Implement learning system that improves routing over time
- Add collaborative features for team-based workflows

## Ecosystem-Fit

Multiverse ist das zentrale Nervensystem von Vibemind. Jede User-Interaktion läuft durch Multiverse, das sie intelligent an passende Spaces routet. Es koordiniert Ideas.Space, Coding.Space, Desktop.Space, N8n.Space, Rowboat.Space, The Brain.Space, Video.Space und Software Design.Space zu einer einheitlichen Plattform.
