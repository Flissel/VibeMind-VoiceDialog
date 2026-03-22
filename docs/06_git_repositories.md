# Git-Repositories

---

## Hauptrepository

| Eigenschaft | Wert |
|------------|------|
| Name | VibeMind-VoiceDialog |
| Aktueller Branch | `main` |
| Pfad | `c:\Users\User\Desktop\Voice_dialog_vibemind\VibeMind-VoiceDialog` |
| Lizenz | MIT |

---

## Branches

| Branch | Status | Beschreibung |
|--------|--------|-------------|
| `main` | Aktiv (aktuell) | Hauptentwicklungsbranch |
| `feature/modular-filesystem-migration` | Abgeschlossen | Modulare Space-Architektur |
| `claude/gallant-lamport` | Worktree | Claude Code Arbeits-Worktree |

---

## Git Submodule (4)

| Submodul | Pfad | Beschreibung |
|----------|------|-------------|
| **Coding_engine** | `python/spaces/coding/Coding_engine` | 40+ AutoGen Agents, Society of Mind Code-Generierung |
| **Automation_ui** | `python/spaces/desktop/Automation_ui` | Custom Desktop Automation Framework |
| **Rowboat** | `python/spaces/roarboot/rowboat` | Knowledge Graph (MongoDB, Qdrant, Redis) |
| **SWE Design** | `python/spaces/shuttles/swe_desgine` | Software Engineering Design Factory |

### Submodul-Management

```bash
# Status aller Submodule pruefen
git submodule status

# Submodule aktualisieren
git submodule update --init --recursive

# Einzelnes Submodul aktualisieren
cd python/spaces/coding/Coding_engine && git pull origin main
```

---

## Letzte Commits

| Hash | Beschreibung | Scope |
|------|-------------|-------|
| `10ad831` | Remove .env from tracking, add voice test scripts, update .gitignore | Config, Git |
| `53a8ff9` | Harden Electron infrastructure: async port allocation, Docker robustness, voice config fixes | Electron, Docker |
| `18a8cf5` | Add Minibook Space for inter-space collaboration (11 new files, 9 modified) | Minibook Space |
| `c48f113` | Add OpenAI Realtime API voice layer (dual-provider: openai_realtime / elevenlabs) | Voice Layer |
| `310bc81` | Add ZeroClaw Research Space as 5th domain (web research, scraping, summarization) | Research Space |
| `40be12b` | Complete modular filesystem migration: add Rowboat space, remove dead spaces, refactor Electron UI | Migration |
| `4dd4f05` | Remove dead code from swarm/ (3 dirs, 3 files) | Cleanup |
| `e15b771` | Delete dead swarm/ dirs: mcp_plugins/ (87 files), simulation/ (10 files) | Cleanup |
| `e81eb69` | Delete 8 dead tool files + 1 dead test | Cleanup |
| `545884e` | Clean up python/ root: delete 15 dead files, move 18 scripts to scripts/ | Cleanup |

---

## Pending Changes (Uncommitted)

### Geaenderte Dateien

| Datei | Art | Beschreibung |
|-------|-----|-------------|
| `.env.example` | Modified | Neue ENV-Variablen hinzugefuegt |
| `python/electron_backend.py` | Modified | IPC-Handling erweitert |
| `python/swarm/orchestrator/intent_classifier.py` | Modified | Neue Event Types |
| `python/swarm/orchestrator/intent_orchestrator.py` | Modified | Orchestrator-Erweiterungen |

### Geloeschte Dateien (25+ Legacy)

| Datei | Grund |
|-------|-------|
| `python/agent_config.py` | Durch Space-Config ersetzt |
| `python/voice_dialog_main.py` | Durch electron_backend.py ersetzt |
| `python/elevenlabs_voice_dialog.py` | ElevenLabs entfernt, durch OpenAI Realtime ersetzt |
| `python/tools/client_tools_manager.py` | In Spaces migriert |
| `python/scripts/*.py` (15 Dateien) | Deploy/Setup Scripts nicht mehr benoetigt |

### Ungetrackte Dateien (Neue Features)

| Verzeichnis | Status | Beschreibung |
|------------|--------|-------------|
| `python/spaces/desktop/messaging/` | NEU | WhatsApp/Telegram Messaging Pipeline |
| `python/spaces/roarboot/` | NEU | Rowboat Knowledge Graph Space |

### Submodul-Aenderungen

| Submodul | Status |
|----------|--------|
| `python/spaces/coding/Coding_engine` | Modified (lokale Aenderungen) |
| `python/spaces/desktop/Automation_ui` | Modified (lokale Aenderungen) |
| `python/spaces/roarboot/rowboat` | Modified (lokale Aenderungen) |
| `python/spaces/shuttles/swe_desgine` | Modified (lokale Aenderungen) |

---

## Commit-Chronologie (Feature-Phasen)

```
Phase 17+: Feature Expansion
  10ad831  Config + Git Hygiene
  53a8ff9  Electron Hardening

Phase 17: Minibook + Research
  18a8cf5  Minibook Space (Collaboration)
  c48f113  OpenAI Realtime API
  310bc81  ZeroClaw Research Space

Phase 16: Modular Migration
  40be12b  Filesystem Migration abgeschlossen
  4dd4f05  Dead Code: swarm/ Cleanup
  e15b771  Dead Code: mcp_plugins, simulation
  e81eb69  Dead Code: Tools + Tests
  545884e  Dead Code: python/ Root Cleanup
```

---

## Empfohlene naechste Schritte

1. **Pending Changes committen** — intent_classifier.py, intent_orchestrator.py, .env.example
2. **Neue Features stagen** — desktop/messaging/, roarboot/
3. **Geloeschte Dateien committen** — Cleanup-Commit fuer Legacy-Dateien
4. **Submodule synchronisieren** — Aenderungen in Submodulen committen/pullen
