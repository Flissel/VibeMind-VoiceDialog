# Contributing to VibeMind Voice Dialog

Thank you for your interest in contributing to VibeMind! This guide will help you get started.

## Getting Started

### 1. Fork & Clone

```bash
# Fork the repo on GitHub, then:
git clone --recursive https://github.com/YOUR_USERNAME/VibeMind-VoiceDialog.git
cd VibeMind-VoiceDialog
```

The `--recursive` flag is important — it pulls in the 6 git submodules (Coding_engine, Automation_ui, Rowboat, etc.).

### 2. Set Up Your Environment

```bash
# Python backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Electron frontend
cd electron-app
npm install
cd ..

# Configuration
cp .env.example .env
# Edit .env with your API keys (at minimum: OPENAI_API_KEY)
```

### 3. Verify Setup

```bash
# Quick check - should start without errors
cd electron-app && npm start
```

See [docs/installation/](docs/installation/) for platform-specific setup guides.

## Development Workflow

### Branch Naming

```
feature/short-description    # New features
fix/issue-number-description # Bug fixes
docs/what-changed            # Documentation
refactor/what-changed        # Code restructuring
```

### Making Changes

1. Create a branch from `main`:
   ```bash
   git checkout -b feature/my-feature main
   ```

2. Make your changes with clear, focused commits

3. Test your changes:
   ```bash
   cd python
   python -m tests.test_intent_to_tool    # Intent routing
   python -m tests.test_data_layer        # Database layer
   ```

4. Push and open a Pull Request:
   ```bash
   git push origin feature/my-feature
   ```

### Commit Messages

Use clear, descriptive messages:

```
Add bubble.merge event type for combining ideas

- Add merge_bubbles() tool in bubble_tools.py
- Register in IdeasBackendAgent TOOL_MAP
- Add classifier examples for German/English
- Update intent test cases
```

## What to Contribute

### Good First Issues

Look for issues labeled [`good first issue`](https://github.com/Flissel/VibeMind-VoiceDialog/labels/good%20first%20issue) — these are scoped and approachable.

### Areas We Need Help

- **Documentation** — Translations (German <-> English), tutorials, examples
- **Test Coverage** — Unit tests for tools, intent classification edge cases
- **New Event Types** — Voice commands for existing spaces
- **UI Improvements** — Three.js rendering, Electron UI
- **Platform Support** — macOS/Linux testing and fixes
- **Accessibility** — Screen reader support, keyboard navigation

### Adding a New Feature

For significant changes, please open an issue first to discuss the approach. This saves time and ensures alignment with the project direction.

## Code Guidelines

### Python

- **Python 3.11+** required
- **Docstrings**: Google format for all public functions
- **Type hints**: Use `typing` for function signatures
- **Imports**: Group as stdlib, third-party, local — separated by blank lines
- **Tool functions**: Return `{"success": bool, "message": str, ...}`

### JavaScript

- **ES6+** syntax in renderer code
- **JSDoc** for exported functions
- **No TypeScript** currently (plain JS)

### General

- Keep changes focused — one feature or fix per PR
- Don't refactor unrelated code in the same PR
- Add tests for new tools and event types
- Update documentation if you change behavior

## Architecture Quick Reference

Adding something new? Here's where things go:

| What | Where | Example |
|------|-------|---------|
| New tool function | `python/tools/` or `python/spaces/<space>/tools/` | `my_tool.py` |
| New event type | `python/swarm/orchestrator/intent_classifier.py` | Add to CLASSIFIER_PROMPT_TEMPLATE |
| Event → tool mapping | `python/swarm/backend_agents/<agent>.py` | Add to TOOL_MAP |
| Param normalization | Same backend agent | Add to PARAM_MAPPING |
| UI message type | `python/tools/*.py` + `electron-app/renderer/` | `_broadcast_to_electron()` |
| New space | `python/spaces/<name>/` | agents/, tools/, README.md |
| Tests | `python/tests/` | `test_<feature>.py` |

See [CLAUDE.md](CLAUDE.md) for the full architecture reference.

## Pull Request Process

1. Fill out the PR template completely
2. Ensure all tests pass
3. Update documentation for any changed behavior
4. Request review from a maintainer
5. Address feedback promptly
6. Squash-merge when approved

## Reporting Bugs

Use the [bug report template](https://github.com/Flissel/VibeMind-VoiceDialog/issues/new?template=bug_report.md). Include:

- Your OS and Python/Node versions
- Steps to reproduce
- Expected vs actual behavior
- Relevant log output (`python/logs/`)

## Security Issues

**Do NOT open a public issue for security vulnerabilities.** See [SECURITY.md](SECURITY.md) for responsible disclosure instructions.

## License

By contributing, you agree that your contributions will be licensed under the [MIT License](LICENSE).
