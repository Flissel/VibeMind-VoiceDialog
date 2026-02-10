"""
Claude CLI Tools - Invoke Claude CLI for complex reasoning

These tools wrap the `claude` CLI (Claude Code) as subprocess calls,
enabling the Desktop Space agents to leverage Claude's reasoning capabilities.

Usage:
- claude_reason: General reasoning with prompt
- claude_analyze_screenshot: Visual analysis of screenshots
- claude_plan_task: Generate execution plans for desktop automation
"""

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

# Windows needs shell=True for .cmd files (npm global installs)
_IS_WINDOWS = sys.platform == "win32"


def _find_claude_cli() -> str:
    """Find the claude CLI executable path."""
    # On Windows, prefer .cmd extension for npm-installed CLIs
    if _IS_WINDOWS:
        # Try .cmd first (npm global install)
        cmd_path = shutil.which("claude.cmd")
        if cmd_path:
            return cmd_path

    found = shutil.which("claude")
    if found:
        return found

    # Common install locations (npm global)
    candidates = [
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude.cmd"),
        os.path.join(os.environ.get("APPDATA", ""), "npm", "claude"),
        os.path.expanduser("~/.local/bin/claude"),
        "/usr/local/bin/claude",
    ]
    for path in candidates:
        if path and os.path.isfile(path):
            return path

    return "claude"  # fallback


# Resolve once at import time
CLAUDE_CLI = _find_claude_cli()
logger.info(f"[claude_cli_tools] Using Claude CLI: {CLAUDE_CLI}")


async def _run_claude_subprocess(cmd: list, stdin_data: bytes = b"", timeout: float = 60.0):
    """Run a Claude CLI subprocess, handling Windows .cmd files.

    On Windows, .cmd files must be run via shell. On other platforms,
    uses direct exec for efficiency.

    Returns (stdout_bytes, stderr_bytes, returncode)
    """
    if _IS_WINDOWS:
        # Windows: use create_subprocess_shell for .cmd files
        shell_cmd = subprocess.list2cmdline(cmd)
        process = await asyncio.create_subprocess_shell(
            shell_cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    else:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    try:
        stdout, stderr = await asyncio.wait_for(
            process.communicate(input=stdin_data),
            timeout=timeout
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()
        raise

    return stdout, stderr, process.returncode


async def claude_reason(prompt: str, context: str = "", timeout: float = 60.0) -> str:
    """
    Invoke Claude CLI for complex reasoning.

    Uses `claude --print` to get Claude's response for complex analysis,
    planning, or decision-making tasks.

    Args:
        prompt: The reasoning prompt/question
        context: Optional background context
        timeout: Subprocess timeout in seconds (default: 60s)

    Returns:
        Claude's reasoning response as string

    Example:
        >>> result = await claude_reason(
        ...     "Wie sollte ich Chrome oeffnen und zu GitHub navigieren?",
        ...     context="Aktuell ist der Desktop sichtbar mit Taskleiste"
        ... )
    """
    full_prompt = f"{context}\n\n{prompt}" if context else prompt

    try:
        cmd = [CLAUDE_CLI, "--print"]
        logger.debug(f"[claude_reason] Prompt: {len(full_prompt)} chars")

        stdout, stderr, rc = await _run_claude_subprocess(
            cmd, stdin_data=full_prompt.encode("utf-8"), timeout=timeout
        )

        if rc != 0:
            error_msg = stderr.decode("utf-8", errors="replace").strip()
            logger.error(f"[claude_reason] Error (code {rc}): {error_msg}")
            return f"Fehler: {error_msg}"

        response = stdout.decode("utf-8", errors="replace").strip()
        logger.info(f"[claude_reason] Response: {len(response)} chars")
        return response

    except asyncio.TimeoutError:
        logger.error(f"[claude_reason] Timeout after {timeout}s")
        return f"Fehler: Claude CLI Timeout nach {timeout} Sekunden"

    except FileNotFoundError:
        logger.error("[claude_reason] Claude CLI not found in PATH")
        return "Fehler: Claude CLI nicht gefunden. Stelle sicher, dass 'claude' im PATH ist."

    except Exception as e:
        logger.error(f"[claude_reason] Exception: {e}", exc_info=True)
        return f"Fehler: {str(e)}"


async def claude_analyze_screenshot(
    screenshot_base64: str,
    question: str,
    timeout: float = 90.0
) -> str:
    """
    Send screenshot to Claude for visual analysis.

    Saves the screenshot to a temp file and uses Claude's vision
    capabilities to analyze it.

    Args:
        screenshot_base64: Base64-encoded PNG screenshot
        question: What to analyze/find in the screenshot
        timeout: Subprocess timeout in seconds (default: 90s)

    Returns:
        Analysis result as string

    Example:
        >>> result = await claude_analyze_screenshot(
        ...     screenshot_b64,
        ...     "Wo ist der Chrome Browser Icon auf dem Desktop?"
        ... )
    """
    import base64

    try:
        # Decode and save screenshot to temp file
        screenshot_bytes = base64.b64decode(screenshot_base64)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(screenshot_bytes)
            temp_path = f.name

        logger.debug(f"[claude_analyze_screenshot] Saved screenshot to {temp_path}")

        try:
            # Build prompt with image reference
            prompt = f"""Analysiere diesen Screenshot und beantworte die Frage.

Frage: {question}

Bitte analysiere:
1. Welche UI-Elemente sind sichtbar?
2. Aktueller Zustand der Anwendung(en)
3. Antwort auf die spezifische Frage

Sei praezise und gib konkrete Koordinaten oder Element-Namen an wenn moeglich."""

            # Use claude with image file
            cmd = [CLAUDE_CLI, "--print", temp_path]

            try:
                stdout, stderr, rc = await _run_claude_subprocess(
                    cmd, stdin_data=prompt.encode("utf-8"), timeout=timeout
                )
            except asyncio.TimeoutError:
                return f"Fehler: Screenshot-Analyse Timeout nach {timeout} Sekunden"

            if rc != 0:
                error_msg = stderr.decode("utf-8", errors="replace").strip()
                return f"Fehler: {error_msg}"

            response = stdout.decode("utf-8", errors="replace").strip()
            logger.info(f"[claude_analyze_screenshot] Analysis complete: {len(response)} chars")
            return response

        finally:
            # Clean up temp file
            try:
                os.unlink(temp_path)
            except Exception:
                pass

    except Exception as e:
        logger.error(f"[claude_analyze_screenshot] Exception: {e}", exc_info=True)
        return f"Fehler bei Screenshot-Analyse: {str(e)}"


async def claude_plan_task(
    task_description: str,
    current_state: str = "",
    timeout: float = 60.0
) -> Dict[str, Any]:
    """
    Generate an execution plan for a desktop automation task.

    Uses Claude to decompose a complex task into atomic actions
    that the Desktop Worker Agent can execute.

    Args:
        task_description: What the user wants to accomplish
        current_state: Description of current screen/application state
        timeout: Subprocess timeout in seconds (default: 60s)

    Returns:
        Dict with execution plan:
        {
            "plan": [
                {"step": 1, "action": "open_app", "target": "Chrome", "verify": "..."},
                {"step": 2, "action": "click", "target": "URL bar", "verify": "..."},
                ...
            ],
            "expected_outcome": "...",
            "risks": ["..."]
        }

    Example:
        >>> plan = await claude_plan_task(
        ...     "Oeffne Chrome und gehe zu github.com",
        ...     current_state="Desktop mit Taskleiste sichtbar"
        ... )
    """
    state_info = f"\nAktueller Zustand: {current_state}" if current_state else ""

    prompt = f"""Erstelle einen Ausfuehrungsplan fuer diese Desktop-Automatisierungsaufgabe.

AUFGABE: {task_description}
{state_info}

Generiere einen schrittweisen Plan. Fuer jeden Schritt spezifiziere:
- action: Aktionstyp (open_app, click, type, press_key, scroll, wait, screenshot)
- target: Womit interagiert werden soll
- value: Text/Taste falls noetig (optional)
- verify: Wie der Erfolg verifiziert werden kann

WICHTIG: Nutze nur diese Aktionen:
- open_app: App oeffnen (target = App-Name)
- click: Element anklicken (target = Element-Beschreibung)
- type: Text eingeben (value = Text)
- press_key: Taste druecken (value = Taste wie "enter", "tab", "ctrl+s")
- scroll: Scrollen (target = "up" oder "down", value = Anzahl)
- wait: Warten (value = Sekunden)
- screenshot: Screenshot machen zur Verifikation

Antworte NUR mit JSON:
{{
    "plan": [
        {{"step": 1, "action": "open_app", "target": "Chrome", "verify": "Chrome Fenster oeffnet sich"}},
        {{"step": 2, "action": "wait", "value": "2", "verify": "Chrome vollstaendig geladen"}},
        {{"step": 3, "action": "click", "target": "URL-Leiste", "verify": "Cursor in URL-Leiste"}},
        {{"step": 4, "action": "type", "value": "github.com", "verify": "URL eingegeben"}},
        {{"step": 5, "action": "press_key", "value": "enter", "verify": "Seite laedt"}}
    ],
    "expected_outcome": "GitHub Website ist geoeffnet in Chrome",
    "risks": ["Chrome koennte nicht installiert sein", "Netzwerk nicht verfuegbar"]
}}"""

    try:
        response = await claude_reason(prompt, timeout=timeout)

        # Try to parse JSON from response
        try:
            # Handle markdown code blocks
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0].strip()
            else:
                json_str = response.strip()

            plan = json.loads(json_str)
            logger.info(f"[claude_plan_task] Generated plan with {len(plan.get('plan', []))} steps")
            return plan

        except json.JSONDecodeError as e:
            logger.warning(f"[claude_plan_task] Failed to parse JSON: {e}")
            return {
                "error": "JSON Parse fehlgeschlagen",
                "raw_response": response,
                "plan": [],
                "expected_outcome": "Unbekannt",
                "risks": ["Plan konnte nicht geparst werden"]
            }

    except Exception as e:
        logger.error(f"[claude_plan_task] Exception: {e}", exc_info=True)
        return {
            "error": str(e),
            "plan": [],
            "expected_outcome": "Fehler",
            "risks": [str(e)]
        }


# Tool registry for AutoGen
CLAUDE_CLI_TOOLS = [
    claude_reason,
    claude_analyze_screenshot,
    claude_plan_task,
]


__all__ = [
    "claude_reason",
    "claude_analyze_screenshot",
    "claude_plan_task",
    "CLAUDE_CLI_TOOLS",
]
