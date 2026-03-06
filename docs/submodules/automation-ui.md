# Automation UI Submodule

## Overview

Automation_ui is a UI automation framework that powers the Desktop space in VibeMind. It provides capabilities for application control, UI element detection, screen capture, and keyboard/mouse automation.

## Location

- **Path in VibeMind:** `python/spaces/desktop/Automation_ui/`
- **Upstream repository:** https://github.com/Flissel/Automation_ui.git
- **Configured in:** `.gitmodules`

## How VibeMind Uses It

### Agent

The **DesktopAgent** (`python/spaces/desktop/agents/desktop_agent.py`) is the backend agent that handles `desktop.*`, `messaging.*`, and `web.*` events. When a user requests desktop automation (e.g., "Oeffne Chrome" or "Klick auf OK"), the agent uses tools that interface with Automation_ui.

### Client Interface

The **`automation_ui_client.py`** (`python/spaces/desktop/automation_ui_client.py`) provides a Python client interface to the Automation_ui submodule. It:

1. Initializes the automation framework
2. Exposes methods for application launching, UI interaction, and screen capture
3. Translates VibeMind tool calls into Automation_ui API calls

### Tools

- `desktop_tools.py` -- Core desktop automation tools (`open_app`, `click`, `type_text`, `screenshot`)
- `adapted_desktop_tools.py` -- Adapted tool wrappers for the backend agent pattern
- `moire_tools.py` -- Visual analysis tools
- `quickaction_tools.py` -- Pre-defined quick action shortcuts
- `task_tools.py` -- System task management

### Adapted Tools

- `adapted/desktop_tools.py` -- Desktop tool adaptations
- `adapted/messaging_tools.py` -- Messaging tool adaptations for chat/messaging applications

## Initialize / Update

```bash
# Initialize
git submodule update --init python/spaces/desktop/Automation_ui

# Update to latest
cd python/spaces/desktop/Automation_ui
git pull origin main
cd ../../../..
git add python/spaces/desktop/Automation_ui
git commit -m "Update Automation_ui submodule"
```
