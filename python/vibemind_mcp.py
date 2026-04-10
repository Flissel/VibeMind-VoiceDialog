"""
VibeMind MCP Server — direkter Zugriff auf process_intent für Claude Code.

Tools:
  vibemind_chat    — Text senden, Antwort empfangen
  vibemind_status  — System-Status abfragen
  vibemind_bubbles — Bubbles/Spaces auflisten
"""
import asyncio
import json
import sys
import os
from pathlib import Path

# Add python/ root to path
ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT.parent / ".env")
except Exception:
    pass


def _get_orchestrator():
    """Get or create the IntentOrchestrator singleton."""
    try:
        from swarm.orchestrator import get_orchestrator
        return get_orchestrator()
    except Exception as e:
        return None


async def _call_intent(text: str) -> dict:
    """Call process_intent and return result."""
    orch = _get_orchestrator()
    if not orch:
        # Try lazy init
        try:
            from swarm.orchestrator.intent_orchestrator import IntentOrchestrator
            orch = IntentOrchestrator()
        except Exception as e:
            return {"success": False, "message": f"Orchestrator nicht verfügbar: {e}"}

    try:
        result = await orch.process_intent(text)
        return {
            "success": True,
            "message": result.response_hint if result else "Keine Antwort",
            "event_type": result.event_type if result else None,
            "error": result.error if result and result.error else None,
        }
    except Exception as e:
        return {"success": False, "message": str(e)}


# ── MCP Protocol (stdio JSON-RPC) ──────────────────────────────────────────

TOOLS = [
    {
        "name": "vibemind_chat",
        "description": "Sendet Text an VibeMind process_intent und gibt die Antwort zurück. Nutze dies um das komplette Intent-Routing zu testen.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Der Text der verarbeitet werden soll (z.B. 'list bubbles', 'erstelle eine Idee', 'hi')"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "vibemind_status",
        "description": "Zeigt den Status des VibeMind Systems (Orchestrator, Tools, Modell).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "vibemind_bubbles",
        "description": "Listet alle Bubbles/Spaces in VibeMind direkt aus der Datenbank.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "vibemind_brain_classify",
        "description": "Fragt direkt den Brain (EventRoutingHead) wie er einen Text klassifizieren würde, ohne Tool-Ausführung. Nützlich um zu sehen ob der Brain schon gut genug trainiert ist.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text der klassifiziert werden soll"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "vibemind_brain_train",
        "description": "Trainiert den Brain (EventRoutingHead) explizit mit einem (text, event_type) Paar — supervised learning. Nutze dies um Korrekturen einzuspielen wenn der Brain etwas falsch klassifiziert.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "User-Text"},
                "event_type": {"type": "string", "description": "Korrektes event_type, z.B. 'bubble.list'"}
            },
            "required": ["text", "event_type"]
        }
    },
    {
        "name": "vibemind_brain_stats",
        "description": "Zeigt EventRoutingHead Statistiken: Anzahl Trainings, Top-Centroids, Aktivierungsstatus.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
]


async def handle_tool(name: str, args: dict) -> str:
    if name == "vibemind_chat":
        text = args.get("text", "").strip()
        if not text:
            return "Kein Text angegeben."
        result = await _call_intent(text)
        lines = [f"✅ Event: {result.get('event_type', '?')}" if result['success'] else "❌ Fehler"]
        lines.append(f"Antwort: {result['message']}")
        if result.get('error'):
            lines.append(f"Error: {result['error']}")
        return "\n".join(lines)

    elif name == "vibemind_status":
        lines = ["VibeMind MCP Status"]
        lines.append(f"Python: {sys.version.split()[0]}")
        lines.append(f"CWD: {os.getcwd()}")
        try:
            from llm_config import get_model
            lines.append(f"Classifier Model: {get_model('classifier')}")
            lines.append(f"Response Model: {get_model('response')}")
        except Exception as e:
            lines.append(f"LLM Config: {e}")
        try:
            from swarm.orchestrator import get_orchestrator
            orch = get_orchestrator()
            if orch:
                tool_count = len(orch._tool_executors) if hasattr(orch, '_tool_executors') else '?'
                lines.append(f"Orchestrator: ✅ ({tool_count} tools)")
            else:
                lines.append("Orchestrator: ⚠️ nicht initialisiert")
        except Exception as e:
            lines.append(f"Orchestrator: ❌ {e}")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                r = await asyncio.wait_for(s.get("http://localhost:5000/api/health"), timeout=2)
                lines.append(f"Brain Server: ✅ ({r.status})")
        except Exception:
            lines.append("Brain Server: ❌ nicht erreichbar")
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                _of_url = os.environ.get("OPENFANG_URL", "http://localhost:50051").rstrip("/")
                r = await asyncio.wait_for(s.get(f"{_of_url}/api/health"), timeout=2)
                lines.append(f"OpenFang: ✅ ({r.status})")
        except Exception:
            lines.append("OpenFang: ❌ nicht erreichbar")
        return "\n".join(lines)

    elif name == "vibemind_bubbles":
        try:
            from data import IdeasRepository
            repo = IdeasRepository()
            bubbles = repo.list(limit=50, order_by="score DESC")
            if not bubbles:
                return "Keine Bubbles gefunden."
            lines = [f"📦 {len(bubbles)} Bubbles:"]
            for b in bubbles:
                bid = (b.id or "")[:8]
                lines.append(f"  • {b.title or '(untitled)'} (id={bid or 'none'}...)")
            return "\n".join(lines)
        except Exception as e:
            return f"Fehler beim Laden der Bubbles: {e}"

    elif name == "vibemind_brain_classify":
        text = args.get("text", "").strip()
        if not text:
            return "Kein Text angegeben."
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "http://localhost:5000/api/cortex/classify",
                    json={"user_text": text},
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as r:
                    if r.status != 200:
                        return f"Brain returned HTTP {r.status}"
                    data = await r.json()
                    lines = [
                        f"🧠 Brain-Klassifikation für: '{text}'",
                        f"  event_type:   {data.get('event_type', '?')}",
                        f"  confidence:   {data.get('confidence', 0):.1%}",
                        f"  alternatives: {', '.join(data.get('alternatives', []))}",
                        f"  latency:      {data.get('latency_ms', '?')}ms",
                    ]
                    return "\n".join(lines)
        except Exception as e:
            return f"Brain nicht erreichbar: {e}"

    elif name == "vibemind_brain_train":
        text = args.get("text", "").strip()
        event_type = args.get("event_type", "").strip()
        if not text or not event_type:
            return "text und event_type sind erforderlich."
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "http://localhost:5000/api/cortex/classify/train",
                    json={"user_text": text, "correct_event_type": event_type},
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as r:
                    if r.status != 200:
                        return f"Brain training failed: HTTP {r.status}"
                    data = await r.json()
                    return f"✅ Brain trainiert: '{text}' → {event_type} (ok={data.get('ok')})"
        except Exception as e:
            return f"Brain nicht erreichbar: {e}"

    elif name == "vibemind_brain_stats":
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get(
                    "http://localhost:5000/api/cortex/classify/stats",
                    timeout=aiohttp.ClientTimeout(total=2),
                ) as r:
                    if r.status != 200:
                        return f"Brain returned HTTP {r.status}"
                    data = await r.json()
                    lines = [
                        f"🧠 EventRoutingHead Stats:",
                        f"  total_events:    {data.get('total_events', '?')}",
                        f"  total_routes:    {data.get('total_routes', 0)}",
                        f"  total_rewards:   {data.get('total_rewards', 0)}",
                        f"  pending_routes:  {data.get('pending_routes', 0)}",
                        f"  train_since_save: {data.get('train_since_save', 0)}",
                    ]
                    top = data.get('top_centroids', {})
                    if top:
                        lines.append("  Top centroids by norm:")
                        for name_, norm in list(top.items())[:10]:
                            lines.append(f"    {norm:.3f}  {name_}")
                    return "\n".join(lines)
        except Exception as e:
            return f"Brain nicht erreichbar: {e}"

    return f"Unbekanntes Tool: {name}"


def main():
    """MCP stdio server loop — synchronous stdin, persistent async loop for tool handlers.

    Uses sync stdin.readline() because asyncio.connect_read_pipe does not work with
    stdin on Windows (ProactorEventLoop). Async tool handlers are run via a single
    persistent event loop with run_until_complete.
    """
    # Persistent loop for async tool handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def send(obj):
        line = json.dumps(obj) + "\n"
        sys.stdout.buffer.write(line.encode())
        sys.stdout.buffer.flush()

    while True:
        try:
            raw = sys.stdin.buffer.readline()
            if not raw:
                break
            req = json.loads(raw.decode("utf-8").strip())
        except Exception:
            break

        method = req.get("method", "")
        req_id = req.get("id")
        params = req.get("params", {})

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": req_id, "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "vibemind-mcp", "version": "1.0.0"}
            }})

        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": req_id, "result": {"tools": TOOLS}})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            try:
                result_text = loop.run_until_complete(handle_tool(tool_name, tool_args))
            except Exception as e:
                result_text = f"Fehler: {e}"
            send({"jsonrpc": "2.0", "id": req_id, "result": {
                "content": [{"type": "text", "text": result_text}]
            }})

        elif method == "notifications/initialized":
            pass  # No response needed

        else:
            if req_id is not None:
                send({"jsonrpc": "2.0", "id": req_id, "error": {
                    "code": -32601, "message": f"Method not found: {method}"
                }})

    try:
        loop.close()
    except Exception:
        pass


if __name__ == "__main__":
    main()
