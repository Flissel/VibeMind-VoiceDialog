# Roadmap

## Vision

VibeMind aims to be the definitive voice-first workspace for idea management — where speaking is faster than typing, and 3D visualization reveals connections you'd miss in flat lists.

## Stability Matrix

| Component | Status | Notes |
|-----------|--------|-------|
| OpenAI Realtime Voice | Stable | Primary voice interface |
| Intent Classification | Stable | 100+ event types, high accuracy |
| Ideas Space | Stable | Full CRUD, linking, formatting, exploration |
| Electron UI / Three.js | Stable | 3D scene, navigation, IPC |
| SQLite Database | Stable | Schema v14, migrations |
| Coding Space | Stable | Requires Coding_engine submodule |
| Desktop Space | Stable | pyautogui + OCR |
| Sync Mode | Stable | Zero-dependency local execution |
| Async Mode (Redis) | Beta | Works but less tested |
| Memory System | Beta | Supermemory integration |
| Rowboat Space | Beta | Knowledge graph + RAG |
| Research Space | Beta | ZeroClaw web research |
| Minibook Space | Beta | Inter-space collaboration |
| Shuttles Space | Beta | Requirements pipeline |
| Schedule Space | Beta | APScheduler integration |
| DroPE Resolver | Experimental | Reference resolution |
| C++ Visual Module | Experimental | Audio-reactive particles |

## Planned Features

### Short Term
- [ ] Documentation site (MkDocs on GitHub Pages)
- [ ] pyproject.toml with optional dependency groups
- [ ] Expanded test coverage
- [ ] macOS and Linux validation
- [ ] English-first voice prompts option

### Medium Term
- [ ] Plugin system for custom spaces
- [ ] Export to Markdown/PDF/Notion
- [ ] Multi-user support
- [ ] WebSocket API for non-Electron clients
- [ ] Voice command customization

### Long Term
- [ ] Mobile companion app
- [ ] Cloud sync with E2E encryption
- [ ] Real-time collaboration
- [ ] Custom LLM provider support (local models)
- [ ] Visual scripting for workflows

## How to Propose Features

1. Check existing [issues](https://github.com/Flissel/VibeMind-VoiceDialog/issues) and this roadmap
2. Open a [Feature Request](https://github.com/Flissel/VibeMind-VoiceDialog/issues/new?template=feature_request.md)
3. Discuss in the issue before starting work
4. For large features, propose architecture in a PR to `docs/plans/`
