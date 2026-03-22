# The Brain.Space

**Neuroscience-inspiriertes kognitives System mit 43 Modulen, 14 AutoGen-Agents und 5 Microservices.**

## Overview

The Brain.Space ist Vibeminds Wissens-Discovery-Engine, aufgebaut als Neuroscience-inspiriertes System. Es ist KEIN traditioneller Backend-Agent, sondern läuft als Set von 5 standalone Microservices mit eigenem Docker-Stack.

> **Hinweis:** Brain hat keinen Backend-Agent in `python/swarm/backend_agents/__init__.py`. Es ist ein eigenständiges System im Git-Submodul `python/spaces/brain/the_brain/` (github.com/Flissel/the_brain).

## 5 Microservices

| Service | Port | Zweck |
|---------|------|-------|
| Brain Server | 5000 | Zentrales unified Brain + Dashboards |
| Production API | 5001 | Legacy REST API |
| Swarm Server | 5002 | 14 kognitive AutoGen-Agents |
| Memory API | 8001 | Supermemory Integration |
| Dashboard | 5000 | Brain-Visualisierung |

## 43 Neuroscience-Module

Inspiriert von echten Hirnregionen:
- **PFC** (Prefrontal Cortex) — Executive Function
- **ACC** (Anterior Cingulate Cortex) — Conflict Monitoring
- **Amygdala** — Emotional Processing
- **VTA** (Ventral Tegmental Area) — Reward/Motivation
- **Raphe** — Serotonin/Mood Regulation
- **Hippocampus** — Memory Consolidation
- **Cerebellum** — Motor Learning/Prediction
- ... und 36 weitere Module

## 9-Phase Cognitive Loop

```
Perceive → Appraise → Remember → Attend → Modulate → Reason → Reflect → Learn → Consolidate
```

## 14 Kognitive AutoGen-Agents (Swarm Server)

Der Swarm Server (Port 5002) orchestriert 14 spezialisierte Agents via AutoGen für kognitive Verarbeitung.

## 3D-Visualisierung im Multiverse

In `electron-app/renderer/multiverse.js`:
- Organic Brain Mesh (3D-Gehirnform)
- 60 Neuron-Partikel mit synaptischen Linien
- Position: (14, 0, -22), Farbe: 0xff66aa (Pink)
- Agent-Name: "Brain", Rolle: "Knowledge Center"

## Key Features

- **Evolutionary ML Pipeline**: Genetische Algorithmen für Contextual Transformation Models (CTMs)
- **Semantic Clustering**: Dynamische Wissens-Cluster basierend auf Semantic Noise
- **Continuous Learning**: Analyse von Datenströmen für neue Verbindungen
- **Pattern Discovery**: Automatische Erkennung bedeutungsvoller Muster
- **Intelligent Silence**: Lernt, wann NICHT zu antworten (Anti-Prompt-Injection)
- **Rowboat Integration**: Seeded Integration mit Rowboat-Datenschicht

## Current Status

- 5 Microservices architektonisch definiert und teilweise implementiert
- 43 Neuroscience-Module vorhanden
- 9-Phase Cognitive Loop implementiert
- 14 kognitive AutoGen-Agents im Swarm Server
- Evolutionary Algorithm Framework funktional
- CTM Training auf Semantic Noise in Research/Validation Phase
- Rowboat-Datenintegration gestartet
- 3D-Visualisierung im Multiverse aktiv

## Roadmap

- Complete CTM training methodology and parameter optimization (Q2-Q3 2026)
- Implement full continuous learning loop with Rowboat data
- Develop domain-specific clustering for common business scenarios
- Create visualization system for knowledge cluster exploration
- Add explainability layer showing why patterns were discovered
- Build prediction capability based on semantic cluster analysis
- Integrate with Ideas.Space for intelligent requirement mining
- Deploy production ML pipeline with multi-tenant isolation

## Ecosystem-Fit

The Brain.Space ist die Intelligenzschicht unter Vibemind. Rowboat.Space speist Business-Daten zur Analyse. Ideas.Space nutzt Insights für Anforderungsverständnis. Desktop.Space lernt User-Verhaltensmuster. Coding.Space greift auf erkannte Patterns zu. Die gesamte Plattform wird progressiv intelligenter durch die Verbindungen, die The Brain entdeckt.
