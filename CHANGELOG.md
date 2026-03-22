# Changelog

All notable changes to VibeMind Voice Dialog will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-03-06

### Added

- **OpenAI Realtime Voice** — Speech-to-speech with Rachel voice agent and native function calling
- **Intent Classification** — LLM-based classification of natural language to structured event types (bubble.*, idea.*, code.*, desktop.*)
- **Swarm Backend** — Domain-specific backend agents (IdeasAgent, CodingAgent, DesktopAgent) with tool execution
- **Electron UI** — 3D multiverse with glass bubbles rendered via Three.js
- **8 Spaces** — Ideas, Coding, Desktop, Rowboat, Research, Minibook, Shuttles, Schedule
- **Database Layer** — SQLite with repository pattern, migrations, and fuzzy search
- **Memory System** — Optional Supermemory integration for task memory, conversation memory, and user profiles
- **DroPE Reference Resolution** — Resolves ambiguous German references ("das", "nochmal") using conversation context
- **Input Enhancement Pipeline** — CollectorAgent, IntentEnhancer, ExecutionValidator for voice preprocessing
- **Tool Orchestrator** — Multi-step request handling via Claude Sonnet
- **Electron + Python IPC** — stdin/stdout JSON protocol with broadcast messages
- **Cross-platform builds** — Electron Builder for Windows (NSIS), macOS (DMG), Linux (AppImage)
- **Optional C++ visual module** — Audio-reactive OpenGL particle effects

### Architecture

- Modular space-based architecture with agents, tools, and event routing per domain
- Sync mode (FORCE_SYNC_MODE) for zero-dependency local development
- Async mode with Redis streams for production event processing
- 6 git submodules: Coding_engine, Automation_ui, Rowboat, SWE Design, ZeroClaw, Minibook

## [Unreleased]

### Planned

- Documentation site (MkDocs)
- CI/CD pipelines (GitHub Actions)
- Docker support
- English translations of German architecture docs
