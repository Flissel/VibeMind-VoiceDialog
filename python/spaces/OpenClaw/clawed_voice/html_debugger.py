"""
HTML Debugger via OpenClaw + Claude

Simple HTML debugging using OpenClaw's Claude agent with browser automation.
No AutoGen - just OpenClaw.

Usage:
    from clawed_voice import debug_html

    # Debug a localhost page
    result = await debug_html("http://localhost:9999/page.html")

    # Or sync version
    result = debug_html_sync("http://localhost:9999/page.html")
"""

import asyncio
from typing import Optional
from .bridge import get_bridge, ClawedVoiceBridge


async def debug_html(
    url: str,
    checks: Optional[list[str]] = None,
    bridge: Optional[ClawedVoiceBridge] = None,
) -> dict:
    """
    Debug an HTML page using OpenClaw's Claude agent.

    Claude will:
    1. Open the page in browser
    2. Check for visual issues
    3. Check for JavaScript errors
    4. Report problems and suggestions

    Args:
        url: URL to debug (localhost URLs work via host.docker.internal)
        checks: Optional additional things to check
        bridge: Optional existing bridge instance

    Returns:
        {
            "success": bool,
            "visual_ok": bool,
            "functional_ok": bool,
            "errors": [...],
            "warnings": [...],
            "suggestions": [...],
        }
    """
    if bridge is None:
        bridge = get_bridge()

    # Convert localhost for Docker access
    test_url = url
    if "localhost:" in url:
        test_url = url.replace("localhost:", "host.docker.internal:")
    elif "127.0.0.1:" in url:
        test_url = url.replace("127.0.0.1:", "host.docker.internal:")

    # Build the debug task
    checks_str = ""
    if checks:
        checks_str = "\n\nZusätzlich prüfen:\n" + "\n".join(f"- {c}" for c in checks)

    task = f"""Debugge diese Webseite: {test_url}

PRÜFE VISUELL:
- Lädt die Seite ohne Fehler?
- Sind alle UI-Elemente sichtbar?
- Ist das Layout korrekt?
- Sind Texte lesbar?

PRÜFE FUNKTIONAL:
- Gibt es JavaScript Console-Errors?
- Laden alle Ressourcen (CSS, JS, Bilder)?
- Sind Buttons/Links vorhanden?
{checks_str}

WORKFLOW:
1. Nutze browser_navigate("{test_url}")
2. Nutze browser_snapshot() um alle Elemente zu sehen
3. Nutze browser_console_messages(level="error") für JS-Errors

Antworte NUR mit diesem JSON:
{{
  "success": true,
  "visual_ok": true,
  "functional_ok": true,
  "errors": [],
  "warnings": [],
  "suggestions": []
}}

Bei Problemen: success=false, und fülle errors/warnings/suggestions."""

    try:
        result = await bridge.execute_task(
            'agent.run',
            {
                'task': task,
                'allowedTools': ['mcp__MCP_DOCKER__browser_*'],
            },
            store_result=True
        )

        if result.get('success'):
            # Parse the agent's response
            response = result.get('response', result.get('result', ''))

            # Try to extract JSON from response
            import json
            import re

            # Find JSON in response
            json_match = re.search(r'\{[^{}]*"success"[^{}]*\}', response, re.DOTALL)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # If no JSON found, return raw response
            return {
                "success": True,
                "visual_ok": True,
                "functional_ok": True,
                "errors": [],
                "warnings": [],
                "suggestions": [],
                "raw_response": response,
            }
        else:
            return {
                "success": False,
                "visual_ok": False,
                "functional_ok": False,
                "errors": [result.get('error', 'Unknown error')],
                "warnings": [],
                "suggestions": [],
            }

    except Exception as e:
        return {
            "success": False,
            "visual_ok": False,
            "functional_ok": False,
            "errors": [str(e)],
            "warnings": [],
            "suggestions": [],
        }


def debug_html_sync(
    url: str,
    checks: Optional[list[str]] = None,
) -> dict:
    """
    Synchronous version of debug_html.

    Args:
        url: URL to debug
        checks: Optional additional checks

    Returns:
        Debug result dict
    """
    return asyncio.run(debug_html(url, checks))


async def quick_debug(url: str) -> None:
    """
    Quick debug with printed output.

    Args:
        url: URL to debug
    """
    print(f"Debugging: {url}")
    print("-" * 40)

    result = await debug_html(url)

    if result["success"]:
        print("[OK] Seite funktioniert!")
        if result.get("warnings"):
            print("\nWarnungen:")
            for w in result["warnings"]:
                print(f"  - {w}")
        if result.get("suggestions"):
            print("\nVorschläge:")
            for s in result["suggestions"]:
                print(f"  - {s}")
    else:
        print("[FEHLER] Probleme gefunden!")
        for e in result.get("errors", []):
            print(f"  [!] {e}")

    print("-" * 40)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python html_debugger.py <url>")
        print("Example: python html_debugger.py http://localhost:9999/page.html")
        sys.exit(1)

    url = sys.argv[1]
    asyncio.run(quick_debug(url))
