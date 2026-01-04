"""
VibeMind Desktop Automation Tools

Zentrale Sammlung aller Client Tools für ElevenLabs Agenten.

Tool-Kategorien:
- Task Tools (5): To-Do Widget Management
- Quick Actions (2): App öffnen/verwenden
- Memory Tools (2): Command History
- Claude Skills (2): Komplexe Automationen
- Desktop Tools (6): Basis-Desktop-Interaktion (existierend)
- Handoff MCP Tools (7): Direct desktop automation via pyautogui
- Moire Server Tools (3): Advanced OCR via MoireServer WebSocket
- Claude Orchestrator Tools (7): Claude Code instance management via Redis

Total: 34 Tools
"""

from typing import Dict, Any, List, Optional, Callable
import logging

logger = logging.getLogger(__name__)

# Import all tool modules
try:
    from .task_tools import (
        create_task_node,
        update_task_status,
        get_task_list,
        mark_task_complete,
        watch_task_progress,
        TASK_TOOLS,
        register_task_tools,
        set_electron_sender
    )
    HAS_TASK_TOOLS = True
except ImportError as e:
    logger.warning(f"Task tools not available: {e}")
    HAS_TASK_TOOLS = False
    TASK_TOOLS = []

try:
    from .quickaction_tools import (
        open_app,
        use_app,
        QUICKACTION_TOOLS,
        register_quickaction_tools
    )
    HAS_QUICKACTION_TOOLS = True
except ImportError as e:
    logger.warning(f"Quick action tools not available: {e}")
    HAS_QUICKACTION_TOOLS = False
    QUICKACTION_TOOLS = []

try:
    from .memory_tools import (
        store_command_history,
        get_frequent_commands,
        MEMORY_TOOLS,
        register_memory_tools
    )
    HAS_MEMORY_TOOLS = True
except ImportError as e:
    logger.warning(f"Memory tools not available: {e}")
    HAS_MEMORY_TOOLS = False
    MEMORY_TOOLS = []

try:
    from .claude_skills import (
        execute_complex_automation,
        generate_automation_script,
        CLAUDE_SKILLS_TOOLS,
        register_claude_skills
    )
    HAS_CLAUDE_SKILLS = True
except ImportError as e:
    logger.warning(f"Claude skills not available: {e}")
    HAS_CLAUDE_SKILLS = False
    CLAUDE_SKILLS_TOOLS = []

try:
    from .desktop_tools import (
        DESKTOP_TOOLS,
        register_desktop_tools
    )
    HAS_DESKTOP_TOOLS = True
except ImportError as e:
    logger.warning(f"Desktop tools not available: {e}")
    HAS_DESKTOP_TOOLS = False
    DESKTOP_TOOLS = []

try:
    from .handoff_tools import (
        HANDOFF_TOOLS,
        register_handoff_tools
    )
    HAS_HANDOFF_TOOLS = True
except ImportError as e:
    logger.warning(f"Handoff MCP tools not available: {e}")
    HAS_HANDOFF_TOOLS = False
    HANDOFF_TOOLS = []

try:
    from .moire_tools import (
        MOIRE_TOOLS,
        register_moire_tools
    )
    HAS_MOIRE_TOOLS = True
except ImportError as e:
    logger.warning(f"Moire Server tools not available: {e}")
    HAS_MOIRE_TOOLS = False
    MOIRE_TOOLS = []

try:
    from .claude_tools import (
        CLAUDE_TOOLS,
        register_claude_tools
    )
    HAS_CLAUDE_TOOLS = True
except ImportError as e:
    logger.warning(f"Claude Orchestrator tools not available: {e}")
    HAS_CLAUDE_TOOLS = False
    CLAUDE_TOOLS = []


# =============================================================================
# COMBINED TOOL DEFINITIONS
# =============================================================================

def get_all_tool_definitions() -> List[Dict[str, Any]]:
    """
    Gibt alle Tool-Definitionen für ElevenLabs zurück.

    Returns:
        Liste aller Tool-Definitionen
    """
    all_tools = []

    if HAS_TASK_TOOLS:
        all_tools.extend(TASK_TOOLS)

    if HAS_QUICKACTION_TOOLS:
        all_tools.extend(QUICKACTION_TOOLS)

    if HAS_MEMORY_TOOLS:
        all_tools.extend(MEMORY_TOOLS)

    if HAS_CLAUDE_SKILLS:
        all_tools.extend(CLAUDE_SKILLS_TOOLS)

    if HAS_DESKTOP_TOOLS:
        all_tools.extend(DESKTOP_TOOLS)

    if HAS_HANDOFF_TOOLS:
        all_tools.extend(HANDOFF_TOOLS)

    if HAS_MOIRE_TOOLS:
        all_tools.extend(MOIRE_TOOLS)

    if HAS_CLAUDE_TOOLS:
        all_tools.extend(CLAUDE_TOOLS)

    return all_tools


def get_adam_tool_definitions() -> List[Dict[str, Any]]:
    """
    Gibt Tool-Definitionen speziell für Adam (Desktop Agent) zurück.
    
    Alle neuen 11 Tools + existierende Desktop Tools.
    """
    return get_all_tool_definitions()


# =============================================================================
# REGISTRATION
# =============================================================================

def register_all_tools(tools_manager, electron_sender: Optional[Callable] = None) -> Dict[str, int]:
    """
    Registriert alle Tools im ClientToolsManager.

    Args:
        tools_manager: Der ClientToolsManager
        electron_sender: Callback für Electron-Nachrichten

    Returns:
        Dict mit Anzahl registrierter Tools pro Kategorie
    """
    stats = {
        "task_tools": 0,
        "quickaction_tools": 0,
        "memory_tools": 0,
        "claude_skills": 0,
        "desktop_tools": 0,
        "handoff_tools": 0,
        "moire_tools": 0,
        "claude_tools": 0,
        "total": 0
    }

    print("\n" + "="*50)
    print("Registering all Desktop Automation Tools")
    print("="*50)

    # Electron Sender für Task Tools setzen
    if electron_sender and HAS_TASK_TOOLS:
        set_electron_sender(electron_sender)

    # Task Tools (5)
    if HAS_TASK_TOOLS:
        try:
            register_task_tools(tools_manager)
            stats["task_tools"] = 5
        except Exception as e:
            logger.error(f"Failed to register task tools: {e}")

    # Quick Action Tools (2)
    if HAS_QUICKACTION_TOOLS:
        try:
            register_quickaction_tools(tools_manager)
            stats["quickaction_tools"] = 2
        except Exception as e:
            logger.error(f"Failed to register quickaction tools: {e}")

    # Memory Tools (2)
    if HAS_MEMORY_TOOLS:
        try:
            register_memory_tools(tools_manager)
            stats["memory_tools"] = 3  # Includes bonus get_command_suggestions
        except Exception as e:
            logger.error(f"Failed to register memory tools: {e}")

    # Claude Skills (2)
    if HAS_CLAUDE_SKILLS:
        try:
            register_claude_skills(tools_manager)
            stats["claude_skills"] = 2
        except Exception as e:
            logger.error(f"Failed to register claude skills: {e}")

    # Desktop Tools (6) - existierende
    if HAS_DESKTOP_TOOLS:
        try:
            register_desktop_tools(tools_manager)
            stats["desktop_tools"] = 6
        except Exception as e:
            logger.error(f"Failed to register desktop tools: {e}")

    # Handoff MCP Tools (7) - NEW
    if HAS_HANDOFF_TOOLS:
        try:
            register_handoff_tools(tools_manager)
            stats["handoff_tools"] = 7
        except Exception as e:
            logger.error(f"Failed to register handoff tools: {e}")

    # Moire Server Tools (3) - NEW
    if HAS_MOIRE_TOOLS:
        try:
            register_moire_tools(tools_manager)
            stats["moire_tools"] = 3
        except Exception as e:
            logger.error(f"Failed to register moire tools: {e}")

    # Claude Orchestrator Tools (7) - NEW
    if HAS_CLAUDE_TOOLS:
        try:
            register_claude_tools(tools_manager)
            stats["claude_tools"] = 7
        except Exception as e:
            logger.error(f"Failed to register claude tools: {e}")

    stats["total"] = sum(v for k, v in stats.items() if k != "total")

    print("-"*50)
    print(f"Total tools registered: {stats['total']}")
    print(f"  - Task Tools: {stats['task_tools']}")
    print(f"  - Quick Actions: {stats['quickaction_tools']}")
    print(f"  - Memory Tools: {stats['memory_tools']}")
    print(f"  - Claude Skills: {stats['claude_skills']}")
    print(f"  - Desktop Tools: {stats['desktop_tools']}")
    print(f"  - Handoff MCP Tools: {stats['handoff_tools']}")
    print(f"  - Moire Server Tools: {stats['moire_tools']}")
    print(f"  - Claude Orchestrator Tools: {stats['claude_tools']}")
    print("="*50 + "\n")

    return stats


def get_tool_categories() -> Dict[str, List[str]]:
    """
    Gibt Tool-Namen gruppiert nach Kategorie zurück.
    """
    return {
        "task": [
            "create_task_node",
            "update_task_status",
            "get_task_list",
            "mark_task_complete",
            "watch_task_progress"
        ],
        "quickaction": [
            "open_app",
            "use_app"
        ],
        "memory": [
            "store_command_history",
            "get_frequent_commands",
            "get_command_suggestions"
        ],
        "claude_skills": [
            "execute_complex_automation",
            "generate_automation_script"
        ],
        "desktop": [
            "execute_desktop_task",
            "click_element",
            "type_text",
            "press_key",
            "take_screenshot",
            "scroll_screen"
        ],
        "handoff_mcp": [
            "mcp_click",
            "mcp_type",
            "mcp_scroll",
            "mcp_press_key",
            "mcp_read_screen",
            "mcp_validate",
            "mcp_get_focus"
        ],
        "moire_server": [
            "moire_scan",
            "moire_find_element",
            "moire_get_ui_context"
        ],
        "claude_orchestrator": [
            "spawn_claude",
            "send_to_claude",
            "list_claude_instances",
            "close_claude",
            "get_claude_status",
            "get_claude_notifications",
            "get_claude_output"
        ]
    }


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Functions
    "get_all_tool_definitions",
    "get_adam_tool_definitions",
    "register_all_tools",
    "get_tool_categories",
    "set_electron_sender",

    # Tool lists - existing
    "TASK_TOOLS",
    "QUICKACTION_TOOLS",
    "MEMORY_TOOLS",
    "CLAUDE_SKILLS_TOOLS",
    "DESKTOP_TOOLS",

    # Tool lists - new
    "HANDOFF_TOOLS",
    "MOIRE_TOOLS",
    "CLAUDE_TOOLS",

    # Registration functions - new
    "register_handoff_tools",
    "register_moire_tools",
    "register_claude_tools",

    # Individual tools (if available)
    "create_task_node",
    "update_task_status",
    "get_task_list",
    "mark_task_complete",
    "watch_task_progress",
    "open_app",
    "use_app",
    "store_command_history",
    "get_frequent_commands",
    "execute_complex_automation",
    "generate_automation_script"
]
