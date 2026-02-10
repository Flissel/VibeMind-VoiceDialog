"""
Desktop Swarm - AutoGen 0.4 Swarm for the Desktop Space (OpenClaw)

Society of Mind architecture with 3 agents:
    DesktopCoordinator (0 tools, routes to specialists)
    ├── ClaudeCLIAgent (planning + verification via Claude CLI Vision)
    └── DesktopOperator (execution: MoireTracker + MCP + ClawedVoice)

Flow:
1. Coordinator receives task, delegates to ClaudeCLI for planning
2. ClaudeCLIAgent plans complex tasks with claude_plan_task
3. DesktopOperator executes actions step by step (direct tools + optional MCP)
4. Operator signals READY_FOR_VERIFICATION
5. Coordinator sends back to ClaudeCLI for Vision verification
6. ClaudeCLI takes screenshot + analyzes → APPROVE or lists issues
7. If issues → back to Operator for correction

MCP Integration (optional, via USE_MCP_DESKTOP=true):
    When enabled, DesktopOperator gets additional MCP server tools
    from servers.json (desktop entry). Use run_desktop_swarm() for
    proper MCP lifecycle management.

Usage:
    # Without MCP (standard mode)
    swarm = create_desktop_swarm()
    result = await swarm.run(task="Oeffne Chrome und gehe zu github.com")

    # With MCP (full mode)
    result = await run_desktop_swarm("Oeffne Chrome und gehe zu github.com")
"""

import json
import os
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

# Feature flags
USE_MCP_DESKTOP = os.getenv("USE_MCP_DESKTOP", "false").lower() in ("true", "1", "yes")
MCP_DESKTOP_SERVER = os.getenv("MCP_DESKTOP_SERVER", "moire-handoff")


def _get_model_client():
    """Get OpenRouter model client for AG2 agents."""
    from swarm.cloud_client import get_model_client
    return get_model_client()


def _load_mcp_server_params():
    """Load MCP server params for desktop from servers.json.

    Returns:
        StdioServerParams or None if not configured.
    """
    servers_json = os.path.join(
        os.path.dirname(__file__), "..", "..", "..",
        "swarm", "mcp_plugins", "servers", "servers.json"
    )

    if not os.path.isfile(servers_json):
        logger.warning("[desktop_swarm] servers.json not found")
        return None

    try:
        with open(servers_json, "r", encoding="utf-8") as f:
            data = json.load(f)

        for srv in data.get("servers", []):
            if srv.get("name") == MCP_DESKTOP_SERVER and srv.get("active"):
                from autogen_ext.tools.mcp import StdioServerParams

                # Build environment with secrets
                env = os.environ.copy()
                for key, val in srv.get("env_vars", {}).items():
                    if isinstance(val, str) and val.startswith("env:"):
                        env_val = os.getenv(val[4:])
                        if env_val:
                            env[key] = env_val

                # Build params with optional cwd and timeout
                params_kwargs = dict(
                    command=srv["command"],
                    args=srv["args"],
                    env=env,
                )
                if srv.get("cwd"):
                    params_kwargs["cwd"] = srv["cwd"]
                if srv.get("read_timeout_seconds"):
                    params_kwargs["read_timeout_seconds"] = srv["read_timeout_seconds"]

                return StdioServerParams(**params_kwargs)

        logger.info("[desktop_swarm] No active 'desktop' MCP server in servers.json")
        return None

    except Exception as e:
        logger.warning(f"[desktop_swarm] Failed to load MCP config: {e}")
        return None


def create_desktop_swarm(model_client=None, mcp_workbench=None):
    """
    Create the Desktop Space AutoGen 0.4 Swarm.

    3 agents in Society of Mind pattern:
    - DesktopCoordinator: Routes tasks, no tools
    - ClaudeCLIAgent: Planning + Vision verification via Claude CLI
    - DesktopOperator: Executes desktop actions (direct + optional MCP)

    Args:
        model_client: Optional pre-configured model client.
                      Uses OpenRouter via cloud_client if not provided.
        mcp_workbench: Optional McpWorkbench instance for MCP tool access.
                       Pass from an active `async with McpWorkbench(...) as mcp` context.

    Returns:
        Swarm team instance
    """
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.conditions import (
        HandoffTermination,
        TextMentionTermination,
        MaxMessageTermination,
    )
    from autogen_agentchat.teams import Swarm

    if model_client is None:
        model_client = _get_model_client()

    # --- Import tools ---

    # Claude CLI tools (reasoning + planning + vision)
    from spaces.OpenClaw.tools.claude_cli_tools import (
        claude_reason,
        claude_analyze_screenshot,
        claude_plan_task,
    )

    # Desktop operator tools (execution)
    from spaces.OpenClaw.tools.desktop_cli_tools import (
        execute_desktop_task,
        click_element,
        type_text,
        press_key,
        take_screenshot,
        scroll_screen,
        open_app,
        moire_scan,
        moire_find_element,
    )

    # Messaging tools (ClawedVoice integration)
    from spaces.OpenClaw.tools.messaging_tools import (
        send_whatsapp,
        send_telegram,
        web_search,
        web_fetch,
        get_pending_notifications,
        get_openclaw_status,
    )

    # --- Agent Definitions ---

    # 1. Desktop Coordinator (Society of Mind Hub)
    #    No tools - routes to specialists
    coordinator = AssistantAgent(
        name="desktop_coordinator",
        model_client=model_client,
        handoffs=[
            "claude_cli_agent",
            "desktop_operator",
            "user",
        ],
        system_message="""Du bist der Desktop-Koordinator im Society of Mind System.

Deine Aufgabe ist es, Desktop-Automatisierungsaufgaben zu koordinieren.

ROUTING-REGELN:
1. Bei NEUER AUFGABE: Immer erst an claude_cli_agent delegieren fuer Planung
2. Nach PLANUNG: An desktop_operator delegieren fuer Ausfuehrung
3. Nach AUSFUEHRUNG (READY_FOR_VERIFICATION): An claude_cli_agent fuer Vision-Verifikation
4. Bei FEHLERN (vom Claude CLI): Zurueck an desktop_operator mit Korrekturanweisungen
5. Bei APPROVE (vom Claude CLI): An user zurueckgeben mit Zusammenfassung

FLOW:
claude_cli_agent (Plan) → desktop_operator (Ausfuehren) → claude_cli_agent (Verifizieren)
                                    ↑                              │
                                    └──── bei Fehlern ─────────────┘

BEISPIELE:
- "Oeffne Chrome" → claude_cli_agent (Plan) → desktop_operator → claude_cli_agent (Verify) → user
- "Screenshot machen" → desktop_operator (direkt) → claude_cli_agent (Verify) → user
- "Sende WhatsApp" → desktop_operator (direkt) → user

WICHTIG:
- Fuer komplexe Aufgaben IMMER erst planen lassen
- Einfache Ein-Schritt-Aufgaben direkt an desktop_operator
- Nach Ausfuehrung: claude_cli_agent fuer Vision-Verifikation
- Bei Unsicherheit: claude_cli_agent fragen

Du hast KEINE Tools - du koordinierst nur die Spezialisten.""",
    )

    # 2. Claude CLI Agent (Planning + Vision Verification)
    #    Uses Claude CLI for planning, reasoning, AND screenshot-based verification.
    #    Dual role: Planner (before execution) and Verifier (after execution).
    claude_cli_agent = AssistantAgent(
        name="claude_cli_agent",
        model_client=model_client,
        handoffs=["desktop_coordinator"],
        tools=[
            claude_reason,
            claude_analyze_screenshot,
            claude_plan_task,
            take_screenshot,
        ],
        system_message="""Du bist der Claude CLI Agent - Planer UND Verifier fuer Desktop-Automatisierung.

DEINE TOOLS:
- claude_reason: Komplexes Denken und Analyse
- claude_plan_task: Ausfuehrungsplaene erstellen
- take_screenshot: Screenshot des aktuellen Bildschirms
- claude_analyze_screenshot: Screenshots mit Claude Vision analysieren

DU HAST ZWEI ROLLEN:

=== ROLLE 1: PLANER (bei neuer Aufgabe) ===
1. Verstehe was der Nutzer will
2. Falls noetig: take_screenshot + claude_analyze_screenshot fuer aktuellen Zustand
3. Plan erstellen mit claude_plan_task
4. Plan an desktop_coordinator zurueckgeben

Plan-Schritte:
- open_app, click, type, press_key, scroll, wait, screenshot

Beispiel:
"Plan erstellt:
1. Chrome oeffnen
2. 2 Sekunden warten
3. URL-Leiste anklicken
4. 'github.com' eingeben
5. Enter druecken
Bitte an desktop_operator zur Ausfuehrung delegieren."

=== ROLLE 2: VERIFIER (nach Ausfuehrung, bei READY_FOR_VERIFICATION) ===
1. take_screenshot() ausfuehren
2. claude_analyze_screenshot() mit Frage: "Wurde die Aufgabe korrekt ausgefuehrt?"
3. Ergebnis bewerten

Verifikations-Antwort:
- Wenn KORREKT: "APPROVE" + 1-2 Bullet Points
- Wenn FALSCH: Konkrete Probleme auflisten (1-2 Punkte)

Beispiel APPROVE:
"APPROVE
- Chrome wurde erfolgreich geoeffnet
- GitHub.com ist im Browser geladen"

Beispiel FEHLER:
"Die URL-Leiste zeigt google.com statt github.com.
Bitte desktop_operator korrigieren lassen."

WICHTIG:
- Bei READY_FOR_VERIFICATION: IMMER Screenshot machen + analysieren
- Gib nach Planung/Verifikation IMMER an desktop_coordinator zurueck""",
    )

    # 3. Desktop Operator Agent (Execution + Messaging)
    #    OpenClaw: Executes desktop actions via MoireTracker and messaging via ClawedVoice.
    #    When MCP workbench is provided, also has access to MCP server tools.
    operator_tools = [
        # Desktop tools (MoireTracker)
        execute_desktop_task,
        click_element,
        type_text,
        press_key,
        take_screenshot,
        scroll_screen,
        open_app,
        moire_scan,
        moire_find_element,
        # Messaging tools (ClawedVoice)
        send_whatsapp,
        send_telegram,
        web_search,
        web_fetch,
        get_pending_notifications,
        get_openclaw_status,
    ]

    # Build operator kwargs (workbench is optional for MCP)
    operator_kwargs = dict(
        name="desktop_operator",
        model_client=model_client,
        handoffs=["desktop_coordinator"],
        tools=operator_tools,
        system_message="""Du bist der Desktop-Operator (OpenClaw). Du fuehrst Aktionen aus.

DESKTOP TOOLS (MoireTracker):
- execute_desktop_task: Komplexe Aufgabe via AI
- click_element: UI-Element anklicken (Beschreibung)
- type_text: Text eingeben
- press_key: Taste druecken (enter, tab, ctrl+s, alt+tab, etc.)
- take_screenshot: Screenshot machen
- scroll_screen: Scrollen (up/down, Anzahl)
- open_app: App oeffnen (Chrome, Word, VSCode, etc.)
- moire_scan: Bildschirm scannen (OCR)
- moire_find_element: Element finden und Koordinaten holen

MESSAGING TOOLS (ClawedVoice):
- send_whatsapp: WhatsApp Nachricht senden
- send_telegram: Telegram Nachricht senden
- web_search: Web-Suche durchfuehren
- web_fetch: Webseite abrufen
- get_pending_notifications: Benachrichtigungen abrufen
- get_openclaw_status: Gateway-Status pruefen

WORKFLOW:
1. Erhalte Aufgabe/Plan vom Coordinator
2. Fuehre Schritte nacheinander aus
3. Vor Klick: moire_find_element nutzen um Element zu finden
4. Nach Aktionen: take_screenshot zur Dokumentation
5. Wenn fertig: Sage "READY_FOR_VERIFICATION" und melde Ergebnis
6. Bei Fehler: An desktop_coordinator melden

WICHTIG:
- Vor JEDEM Klick: moire_find_element nutzen!
- Nach App-Oeffnung: Kurz warten
- Bei Fehler NICHT wiederholen - melden!
- Wenn alles ausgefuehrt: IMMER "READY_FOR_VERIFICATION" sagen
- Fuer Messaging: get_openclaw_status pruefen wenn Fehler""",
    )

    # Add MCP workbench if available
    if mcp_workbench is not None:
        operator_kwargs["workbench"] = mcp_workbench
        logger.info("[desktop_swarm] MCP workbench attached to DesktopOperator")

    desktop_operator = AssistantAgent(**operator_kwargs)

    # --- Termination Conditions ---
    termination = (
        HandoffTermination(target="user")
        | TextMentionTermination("APPROVE")
        | TextMentionTermination("DONE")
        | TextMentionTermination("FERTIG")
        | MaxMessageTermination(max_messages=30)
    )

    # --- Create Swarm ---
    swarm = Swarm(
        participants=[
            coordinator,
            claude_cli_agent,
            desktop_operator,
        ],
        termination_condition=termination,
    )

    mcp_status = "with MCP" if mcp_workbench else "without MCP"
    logger.info(
        f"[desktop_swarm] Created Desktop Swarm: 3 agents "
        f"(coordinator + claude_cli + operator) [{mcp_status}]"
    )

    return swarm


async def run_desktop_swarm(
    task: str,
    model_client=None,
    use_mcp: Optional[bool] = None,
) -> Any:
    """
    Run the Desktop Swarm on a task with proper MCP lifecycle management.

    When MCP is enabled (via use_mcp param or USE_MCP_DESKTOP env var),
    this function manages the McpWorkbench async context and passes it
    to the swarm's DesktopOperator agent.

    Args:
        task: Natural language task description
        model_client: Optional pre-configured model client
        use_mcp: Override USE_MCP_DESKTOP env var (True/False/None=auto)

    Returns:
        TaskResult from the swarm run
    """
    should_use_mcp = use_mcp if use_mcp is not None else USE_MCP_DESKTOP

    if should_use_mcp:
        server_params = _load_mcp_server_params()
        if server_params is not None:
            logger.info(f"[desktop_swarm] Running with MCP workbench")
            from autogen_ext.tools.mcp import McpWorkbench

            async with McpWorkbench(server_params) as mcp:
                swarm = create_desktop_swarm(model_client, mcp_workbench=mcp)
                result = await swarm.run(task=task)
                return result
        else:
            logger.warning("[desktop_swarm] MCP requested but no config found, falling back")

    # Standard mode (no MCP)
    swarm = get_desktop_swarm(model_client)
    result = await swarm.run(task=task)
    return result


# --- Singleton Pattern (for non-MCP usage) ---

_desktop_swarm = None


def get_desktop_swarm(model_client=None):
    """
    Get or create the Desktop Swarm singleton (without MCP).

    For MCP-enabled runs, use run_desktop_swarm() instead.

    Args:
        model_client: Optional model client (only used on first call)

    Returns:
        Swarm instance
    """
    global _desktop_swarm
    if _desktop_swarm is None:
        _desktop_swarm = create_desktop_swarm(model_client)
    return _desktop_swarm


def reset_desktop_swarm():
    """Reset the Desktop Swarm singleton (for testing)."""
    global _desktop_swarm
    _desktop_swarm = None


__all__ = [
    "create_desktop_swarm",
    "get_desktop_swarm",
    "reset_desktop_swarm",
    "run_desktop_swarm",
    "USE_MCP_DESKTOP",
]
