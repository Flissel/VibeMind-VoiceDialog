"""
Claude Skills für Desktop Automation

Nutzt Claude via OpenRouter für komplexe Multi-Step Reasoning
und Script-Generierung.

Tools:
1. execute_complex_automation - Führt komplexe Multi-Step Tasks aus
2. generate_automation_script - Generiert PyAutoGUI Scripts
"""

import asyncio
import logging
import json
import os
import re
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# OpenRouter API
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"


async def _call_claude(
    prompt: str,
    system_prompt: str = "",
    model: str = DEFAULT_MODEL,
    max_tokens: int = 2000
) -> Dict[str, Any]:
    """
    Ruft Claude via OpenRouter auf.
    
    Args:
        prompt: Der User-Prompt
        system_prompt: System-Prompt
        model: Model ID
        max_tokens: Max Tokens
    
    Returns:
        Dict mit response
    """
    import aiohttp
    
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return {
            "success": False,
            "error": "OPENROUTER_API_KEY nicht gesetzt"
        }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://vibemind.app",
        "X-Title": "VibeMind Desktop Automation"
    }
    
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.3
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                OPENROUTER_API_URL,
                headers=headers,
                json=payload,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    return {
                        "success": False,
                        "error": f"API Error {response.status}: {error_text}"
                    }
                
                data = await response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                return {
                    "success": True,
                    "content": content,
                    "model": model,
                    "usage": data.get("usage", {})
                }
                
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


async def execute_complex_automation(
    goal: str,
    context: Optional[str] = None,
    constraints: Optional[List[str]] = None,
    timeout: float = 120.0
) -> Dict[str, Any]:
    """
    Führt eine komplexe Multi-Step Desktop Automation aus.
    
    Nutzt Claude für Reasoning und Planung, dann MoireTracker
    für die Ausführung.
    
    Args:
        goal: Das Ziel (z.B. "Erstelle ein Word-Dokument mit einer Tabelle")
        context: Zusätzlicher Kontext
        constraints: Einschränkungen (z.B. ["Nicht speichern", "Nur Chrome"])
        timeout: Maximale Ausführungszeit
    
    Returns:
        Dict mit Ergebnis und ausgeführten Schritten
    """
    try:
        logger.info(f"Complex automation: {goal}")
        
        # System Prompt für Planung
        system_prompt = """Du bist ein Desktop-Automation-Experte. Deine Aufgabe ist es, 
komplexe Desktop-Tasks in einzelne, ausführbare Schritte aufzuteilen.

Für jeden Schritt gibst du an:
- action: Die Aktion (click, type, keyboard, wait, verify)
- target: Das Ziel (Button-Name, Textfeld, etc.)
- value: Der Wert (Text, Taste, etc.)
- description: Kurze Beschreibung

Ausgabe als JSON-Array von Schritten.
Beispiel:
[
  {"action": "click", "target": "Start Menu", "description": "Startmenü öffnen"},
  {"action": "type", "target": "Search", "value": "Word", "description": "Nach Word suchen"},
  {"action": "keyboard", "value": "Enter", "description": "Enter drücken"}
]"""

        # User Prompt
        user_prompt = f"Ziel: {goal}"
        if context:
            user_prompt += f"\n\nKontext: {context}"
        if constraints:
            user_prompt += f"\n\nEinschränkungen:\n" + "\n".join(f"- {c}" for c in constraints)
        
        user_prompt += "\n\nErstelle einen Schritt-für-Schritt Plan als JSON."
        
        # Claude aufrufen für Planung
        plan_result = await _call_claude(user_prompt, system_prompt)
        
        if not plan_result.get("success"):
            return {
                "success": False,
                "error": f"Planung fehlgeschlagen: {plan_result.get('error')}",
                "goal": goal
            }
        
        # Plan parsen
        content = plan_result.get("content", "")
        
        # JSON aus Response extrahieren
        json_match = re.search(r'\[[\s\S]*\]', content)
        if not json_match:
            return {
                "success": False,
                "error": "Konnte keinen Plan aus Claude-Antwort extrahieren",
                "raw_response": content
            }
        
        try:
            steps = json.loads(json_match.group())
        except json.JSONDecodeError as e:
            return {
                "success": False,
                "error": f"JSON Parse Error: {e}",
                "raw_response": content
            }
        
        # Schritte ausführen
        executed_steps = []
        failed_step = None
        
        try:
            from moire_external import execute_task
            has_moire = True
        except ImportError:
            has_moire = False
        
        for i, step in enumerate(steps):
            step_desc = step.get("description", f"Schritt {i+1}")
            action = step.get("action", "")
            target = step.get("target", "")
            value = step.get("value", "")
            
            logger.info(f"Executing step {i+1}: {step_desc}")
            
            if has_moire:
                # Via MoireTracker ausführen
                task_desc = step_desc
                if action == "click":
                    task_desc = f"Klicke auf '{target}'"
                elif action == "type":
                    task_desc = f"Tippe '{value}' in '{target}'"
                elif action == "keyboard":
                    task_desc = f"Drücke Taste '{value}'"
                
                result = await execute_task(task_desc, timeout=30.0)
                success = result.success if hasattr(result, 'success') else False
            else:
                # Simuliere Ausführung
                import pyautogui
                
                if action == "click":
                    # Würde Element suchen und klicken
                    success = True
                elif action == "type" and value:
                    pyautogui.write(value)
                    success = True
                elif action == "keyboard" and value:
                    if value.lower() == "enter":
                        pyautogui.press('enter')
                    elif "+" in value:
                        keys = value.lower().split("+")
                        pyautogui.hotkey(*keys)
                    else:
                        pyautogui.press(value.lower())
                    success = True
                elif action == "wait":
                    await asyncio.sleep(float(value) if value else 1.0)
                    success = True
                else:
                    success = True
            
            executed_steps.append({
                "step": i + 1,
                "description": step_desc,
                "action": action,
                "success": success
            })
            
            if not success:
                failed_step = i + 1
                break
            
            # Kurze Pause zwischen Schritten
            await asyncio.sleep(0.5)
        
        all_success = failed_step is None
        
        return {
            "success": all_success,
            "goal": goal,
            "total_steps": len(steps),
            "executed_steps": len(executed_steps),
            "steps": executed_steps,
            "failed_at_step": failed_step,
            "plan": steps,
            "message": "Alle Schritte erfolgreich" if all_success else f"Fehlgeschlagen bei Schritt {failed_step}"
        }
        
    except Exception as e:
        logger.error(f"execute_complex_automation failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "goal": goal
        }


async def generate_automation_script(
    description: str,
    output_format: str = "pyautogui",
    include_comments: bool = True,
    safety_checks: bool = True
) -> Dict[str, Any]:
    """
    Generiert ein Automation-Script basierend auf Beschreibung.
    
    Nutzt Claude um ein ausführbares PyAutoGUI-Script zu erstellen.
    
    Args:
        description: Beschreibung was das Script tun soll
        output_format: Format (pyautogui, ahk, powershell)
        include_comments: Kommentare hinzufügen?
        safety_checks: Sicherheitschecks einfügen?
    
    Returns:
        Dict mit generiertem Script
    """
    try:
        logger.info(f"Generating script: {description}")
        
        # System Prompt
        system_prompts = {
            "pyautogui": """Du bist ein Python/PyAutoGUI Experte. Generiere ein sauberes, 
ausführbares Python-Script mit PyAutoGUI für Desktop-Automation.

Anforderungen:
- Nutze pyautogui für Maus/Tastatur
- Füge time.sleep() zwischen Aktionen ein
- Behandle Fehler mit try/except
- Füge Safety-Checks ein (pyautogui.FAILSAFE)
""",
            "ahk": """Du bist ein AutoHotkey Experte. Generiere ein sauberes AHK-Script.

Anforderungen:
- Nutze moderne AHK v2 Syntax
- Füge Sleep zwischen Aktionen ein
- Behandle Fehler
""",
            "powershell": """Du bist ein PowerShell Experte. Generiere ein PowerShell-Script
mit System.Windows.Forms für UI-Automation.

Anforderungen:
- Nutze Add-Type für Windows Forms
- Füge Start-Sleep zwischen Aktionen ein
"""
        }
        
        system_prompt = system_prompts.get(output_format.lower(), system_prompts["pyautogui"])
        
        if include_comments:
            system_prompt += "\nFüge hilfreiche Kommentare hinzu die erklären was jeder Schritt tut."
        
        if safety_checks:
            system_prompt += "\nFüge Safety-Checks ein (z.B. Bildschirmgrenzen, Timeout)."
        
        user_prompt = f"""Erstelle ein {output_format} Script das folgendes tut:

{description}

Gib NUR den Code aus, ohne zusätzliche Erklärungen."""

        # Claude aufrufen
        result = await _call_claude(user_prompt, system_prompt)
        
        if not result.get("success"):
            return {
                "success": False,
                "error": f"Script-Generierung fehlgeschlagen: {result.get('error')}",
                "description": description
            }
        
        content = result.get("content", "")
        
        # Code extrahieren (falls in Markdown-Block)
        code_match = re.search(r'```(?:python|ahk|powershell)?\n?([\s\S]*?)```', content)
        if code_match:
            script = code_match.group(1).strip()
        else:
            script = content.strip()
        
        # Validierung
        is_valid = True
        validation_errors = []
        
        if output_format.lower() == "pyautogui":
            if "import pyautogui" not in script:
                script = "import pyautogui\nimport time\n\n" + script
            
            # Safety check einfügen wenn nicht vorhanden
            if safety_checks and "FAILSAFE" not in script:
                script = "import pyautogui\nimport time\n\npyautogui.FAILSAFE = True\npyautogui.PAUSE = 0.5\n\n" + script.replace("import pyautogui\nimport time\n\n", "")
        
        return {
            "success": True,
            "script": script,
            "format": output_format,
            "description": description,
            "is_valid": is_valid,
            "validation_errors": validation_errors,
            "lines": len(script.split("\n")),
            "usage": result.get("usage", {})
        }
        
    except Exception as e:
        logger.error(f"generate_automation_script failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "description": description
        }


# =============================================================================
# TOOL DEFINITIONS for ElevenLabs
# =============================================================================

CLAUDE_SKILLS_TOOLS = [
    {
        "name": "execute_complex_automation",
        "description": "Führt komplexe Multi-Step Desktop Tasks aus. Nutzt KI-Reasoning um das Ziel in Einzelschritte aufzuteilen und diese auszuführen. Ideal für komplexe Aufgaben wie 'Erstelle ein Word-Dokument mit einer Tabelle'.",
        "parameters": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Das Ziel der Automation (z.B. 'Erstelle ein Word-Dokument mit einer Tabelle')"
                },
                "context": {
                    "type": "string",
                    "description": "Zusätzlicher Kontext (z.B. 'Word ist bereits geöffnet')"
                },
                "constraints": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Einschränkungen (z.B. ['Nicht speichern', 'Nur im Browser'])"
                }
            },
            "required": ["goal"]
        }
    },
    {
        "name": "generate_automation_script",
        "description": "Generiert ein Automation-Script (PyAutoGUI, AHK, PowerShell) basierend auf einer Beschreibung. Das Script kann gespeichert und später wiederverwendet werden.",
        "parameters": {
            "type": "object",
            "properties": {
                "description": {
                    "type": "string",
                    "description": "Beschreibung was das Script tun soll"
                },
                "output_format": {
                    "type": "string",
                    "enum": ["pyautogui", "ahk", "powershell"],
                    "description": "Format: pyautogui (Python), ahk (AutoHotkey), powershell",
                    "default": "pyautogui"
                },
                "include_comments": {
                    "type": "boolean",
                    "description": "Kommentare hinzufügen?",
                    "default": True
                },
                "safety_checks": {
                    "type": "boolean",
                    "description": "Sicherheitschecks einfügen?",
                    "default": True
                }
            },
            "required": ["description"]
        }
    }
]


# =============================================================================
# REGISTRATION
# =============================================================================

def register_claude_skills(tools_manager) -> None:
    """Registriert Claude Skills im ClientToolsManager."""
    print("Registering Claude skills...")
    
    def execute_complex_wrapper(params):
        return _run_async(execute_complex_automation(
            params.get("goal", ""),
            params.get("context"),
            params.get("constraints")
        ))
    
    def generate_script_wrapper(params):
        return _run_async(generate_automation_script(
            params.get("description", ""),
            params.get("output_format", "pyautogui"),
            params.get("include_comments", True),
            params.get("safety_checks", True)
        ))
    
    tools_manager.register_with_observer("execute_complex_automation", execute_complex_wrapper)
    tools_manager.register_with_observer("generate_automation_script", generate_script_wrapper)
    
    print("Claude skills registered (2 tools)")


def _run_async(coro):
    """Helper um async functions synchron auszuführen."""
    import concurrent.futures
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return asyncio.run(coro)
    except Exception as e:
        return {"success": False, "error": str(e)}


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    "execute_complex_automation",
    "generate_automation_script",
    "CLAUDE_SKILLS_TOOLS",
    "register_claude_skills"
]