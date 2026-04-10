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
        "name": "vibemind_ui",
        "description": "Liest den aktuellen VibeMind Electron UI-Zustand via CDP (Chrome DevTools Protocol). Zeigt: aktive Spaces, Chat-Messages, 3D-Szene Status, WebGL, Fehler. Nützlich um zu prüfen ob die UI richtig rendert.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Was tun: 'read' (UI-State lesen), 'reload' (Seite neu laden), 'screenshot' (Screenshot als Pfad)",
                    "enum": ["read", "reload", "screenshot"],
                    "default": "read"
                }
            }
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

    elif name == "vibemind_ui":
        action = args.get("action", "read")
        CDP_PORT = int(os.environ.get("ELECTRON_CDP_PORT", "9223"))
        try:
            result = await _vibemind_ui_action(action, CDP_PORT)
            return result
        except Exception as e:
            return f"VibeMind UI nicht erreichbar (CDP :{CDP_PORT}): {e}"

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


async def _vibemind_ui_action(action: str, cdp_port: int) -> str:
    """Read/reload VibeMind Electron UI via Chrome DevTools Protocol."""
    import urllib.request

    # 1. Find the Multiverse page WebSocket URL
    try:
        resp = urllib.request.urlopen(f"http://localhost:{cdp_port}/json", timeout=3)
        pages = json.loads(resp.read())
    except Exception as e:
        return f"CDP nicht erreichbar auf :{cdp_port} — Electron läuft nicht? ({e})"

    ws_url = None
    all_pages = []
    for p in pages:
        all_pages.append(f"  [{p.get('type','?')}] {p.get('title','?')}")
        if "Multiverse" in p.get("title", "") or "renderer/index.html" in p.get("url", ""):
            ws_url = p.get("webSocketDebuggerUrl")

    if not ws_url:
        return f"Kein VibeMind Renderer gefunden. Pages:\n" + "\n".join(all_pages)

    # 2. Connect via WebSocket and run JS expressions
    try:
        import websockets
    except ImportError:
        return "websockets package nicht installiert (pip install websockets)"

    async with websockets.connect(ws_url, max_size=2**20) as ws:
        async def evaluate(expr: str, eid: int) -> str:
            await ws.send(json.dumps({
                "id": eid, "method": "Runtime.evaluate",
                "params": {"expression": expr, "returnByValue": True}
            }))
            for _ in range(5):
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=5))
                if msg.get("id") == eid:
                    res = msg.get("result", {}).get("result", {})
                    if msg.get("result", {}).get("exceptionDetails"):
                        exc = msg["result"]["exceptionDetails"]
                        return f"JS ERROR: {exc.get('text', str(exc)[:200])}"
                    return str(res.get("value", res.get("description", "")))
            return "TIMEOUT"

        if action == "reload":
            await ws.send(json.dumps({"id": 99, "method": "Page.reload", "params": {"ignoreCache": True}}))
            await asyncio.sleep(2)
            return "✅ VibeMind Seite neu geladen (WebGL sollte sich reinitialisieren)"

        if action == "screenshot":
            await ws.send(json.dumps({"id": 98, "method": "Page.captureScreenshot", "params": {"format": "png"}}))
            for _ in range(5):
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))
                if msg.get("id") == 98:
                    import base64
                    data = msg.get("result", {}).get("data", "")
                    if data:
                        spath = os.path.join(os.environ.get("TEMP", "/tmp"), "vibemind_screenshot.png")
                        with open(spath, "wb") as f:
                            f.write(base64.b64decode(data))
                        return f"📸 Screenshot gespeichert: {spath}"
                    return "Screenshot fehlgeschlagen"
            return "Screenshot TIMEOUT"

        # action == "read" — collect UI state
        lines = ["🖥️ VibeMind UI State"]

        # Title + URL
        title = await evaluate("document.title", 1)
        lines.append(f"  Title: {title}")

        # WebGL status
        webgl = await evaluate("""
            (function() {
                var c = document.querySelector('canvas');
                if (!c) return 'NO CANVAS';
                var gl = c.getContext('webgl2') || c.getContext('webgl');
                if (!gl) return 'NO WEBGL CONTEXT';
                if (gl.isContextLost()) return 'CONTEXT LOST (weißer Screen!)';
                return 'OK (' + c.width + 'x' + c.height + ')';
            })()
        """, 2)
        lines.append(f"  WebGL: {webgl}")

        # Active space / navigation
        spaces = await evaluate("""
            JSON.stringify(Array.from(document.querySelectorAll('.space-tab, .nav-item, [class*=space]'))
                .slice(0, 15)
                .map(e => ({text: e.textContent.trim().substring(0, 30), active: e.classList.contains('active')})))
        """, 3)
        lines.append(f"  Spaces: {spaces[:300]}")

        # Chat messages
        chat = await evaluate("""
            JSON.stringify((function() {
                var msgs = document.querySelectorAll('.chat-message, .message, [class*=message]');
                var result = [];
                msgs.forEach(function(m) {
                    var text = m.textContent.trim().substring(0, 100);
                    if (text) result.push(text);
                });
                return result.slice(-5);
            })())
        """, 4)
        lines.append(f"  Chat (letzte 5): {chat[:400]}")

        # Current bubble/space indicator
        current = await evaluate("""
            (function() {
                var el = document.querySelector('#current-space, #current-bubble, .current-space, [class*=current]');
                return el ? el.textContent.trim().substring(0, 50) : 'kein aktives Element';
            })()
        """, 5)
        lines.append(f"  Aktueller Space: {current}")

        # Voice status
        voice = await evaluate("""
            (function() {
                var el = document.querySelector('#voice-status, [class*=voice], .voice-indicator');
                return el ? el.textContent.trim().substring(0, 50) : 'kein Voice-Element';
            })()
        """, 6)
        lines.append(f"  Voice: {voice}")

        # 3D scene objects (Three.js)
        scene3d = await evaluate("""
            (function() {
                if (typeof window.scene === 'undefined' && typeof window.app === 'undefined') return 'kein scene/app Objekt';
                var s = window.scene || (window.app && window.app.scene);
                if (!s) return 'scene nicht gefunden';
                var names = [];
                s.traverse(function(obj) { if (obj.name) names.push(obj.name); });
                return names.length + ' Objekte: ' + names.slice(0, 20).join(', ');
            })()
        """, 7)
        lines.append(f"  3D Szene: {scene3d[:300]}")

        # Console errors (last 5)
        errors = await evaluate("""
            JSON.stringify(window.__vibemind_errors || [])
        """, 8)
        if errors and errors != "[]":
            lines.append(f"  Errors: {errors[:300]}")

        # Connection status (WebSocket to MoireServer)
        ws_status = await evaluate("""
            (function() {
                var sockets = [];
                if (window._ws) sockets.push('_ws: ' + window._ws.readyState);
                if (window._moireWs) sockets.push('moire: ' + window._moireWs.readyState);
                return sockets.length ? sockets.join(', ') : 'keine WebSockets gefunden';
            })()
        """, 9)
        lines.append(f"  WebSockets: {ws_status}")

        return "\n".join(lines)


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
