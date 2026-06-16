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
        "name": "vibemind_rowboat_cleanup",
        "description": "Reverse-Sync: loescht aus Rowboats MongoDB alle 'VibeMind - *'-Sources, die KEINER Live-Bubble (Supabase) mehr entsprechen. Standard dry_run=true (zeigt nur was geloescht WUERDE). dry_run=false fuehrt Hard-Delete aus. Safety: bricht ab wenn 0 Live-Bubbles oder mehr Orphans als max_delete.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {"type": "boolean", "description": "Nur berichten statt loeschen. Default true.", "default": True},
                "max_delete": {"type": "integer", "description": "Abbruch wenn mehr Orphans als das. Default 200.", "default": 200}
            }
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
    # ─── Phase 7 Split: Bridge Tools from desktop-automation ─────────
    {
        "name": "vibemind_bubble_create",
        "description": "Erstellt eine neue Bubble/Idea in VibeMind direkt via IdeasRepository + Electron UI Broadcast.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string", "default": ""},
            },
            "required": ["title"]
        }
    },
    {
        "name": "vibemind_bubble_update",
        "description": "Aktualisiert eine bestehende Bubble/Idea nach ID. Aenderungen werden an Electron UI gebroadcastet.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "bubble_id": {"type": "string"},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "score": {"type": "number"},
            },
            "required": ["bubble_id"]
        }
    },
    {
        "name": "vibemind_ui_command",
        "description": "Sendet einen IPC-Command direkt an die VibeMind Electron UI. Bekannte Commands: node_added, node_removed, node_updated, space_changed, canvas_refresh, navigate_to_space, show_notification.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "IPC message type (z.B. 'canvas_refresh', 'navigate_to_space')"},
                "params": {"type": "object", "description": "Zusaetzliche Parameter fuer den Command"},
            },
            "required": ["command"]
        }
    },
    {
        "name": "vibemind_agent_dispatch",
        "description": "Dispatcht einen Task an einen VibeMind Agent via Minibook. Nutze @agent Mentions fuer spezifische Spaces (z.B. @coding, @research, @ideas).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string"},
                "agent": {"type": "string", "description": "Ziel-Agent/Space (z.B. 'coding', 'research', 'ideas')"},
                "context": {"type": "object"},
            },
            "required": ["task"]
        }
    },
    {
        "name": "vibemind_agents_list",
        "description": "Listet VibeMind's 14 Domain-Spaces mit Event-Prefixes, Streams und Live-Status von Minibook + Brain.",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "vibemind_intent",
        "description": "Routet Text durch die volle IntentOrchestrator Pipeline (classify → route → execute → respond). Wie vibemind_chat aber gibt strukturiertes JSON zurueck statt formatiertem Text.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Natural language Intent, z.B. 'erstelle eine Idee zum Thema KI'"},
            },
            "required": ["text"]
        }
    },
    # ─── Space Debugging Tools ───────────────────────────────────────
    {
        "name": "vibemind_space_inspect",
        "description": "Inspiziert einen Space: Agent-Name, Stream, TOOL_MAP, PARAM_MAPPING, geladene Tools. Zeigt alles was der Space kann.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space": {
                    "type": "string",
                    "description": "Space-Name: bubbles, ideas, coding, desktop, rowboat, research, minibook, schedule, n8n, agentfarm, video, mirofish, flowzen",
                    "enum": ["bubbles", "ideas", "coding", "desktop", "rowboat", "research", "minibook", "schedule", "n8n", "agentfarm", "video", "mirofish", "flowzen"]
                }
            },
            "required": ["space"]
        }
    },
    {
        "name": "vibemind_space_test",
        "description": "Fuehrt ein Tool direkt auf einem Space-Agent aus — ohne Intent-Routing. Perfekt zum Debuggen einzelner Space-Funktionen.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space": {
                    "type": "string",
                    "description": "Space-Name",
                    "enum": ["bubbles", "ideas", "coding", "desktop", "rowboat", "research", "minibook", "schedule", "n8n", "agentfarm", "video", "mirofish", "flowzen"]
                },
                "event_type": {"type": "string", "description": "Event type, z.B. 'bubble.list', 'idea.create', 'code.status'"},
                "payload": {"type": "object", "description": "Parameter-Payload fuer das Tool"}
            },
            "required": ["space", "event_type"]
        }
    },
    {
        "name": "vibemind_spaces_overview",
        "description": "Zeigt alle 13 Spaces auf einen Blick: Agent geladen? Wie viele Tools? Letzte Fehler? Stream aktiv?",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "vibemind_space_health",
        "description": "Reality-Check: testet JEDEN Space ob er tatsaechlich funktioniert (nicht nur Code vorhanden). Ruft pro Space ein einfaches Tool auf (list/status) und meldet Erfolg/Fehler. Zeigt was wirklich geht vs was nur Code ist.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "space": {
                    "type": "string",
                    "description": "Optional: nur einen Space testen. Ohne = alle testen.",
                    "enum": ["bubbles", "ideas", "coding", "desktop", "rowboat", "research", "minibook", "schedule", "n8n", "agentfarm", "video", "mirofish", "flowzen", "all"]
                }
            }
        }
    },
    # ── Launcher control (Docker Swarm stack + native services) ────────────
    # Drives the same PS1 scripts as the Tauri launcher UI (scripts/vibemind-*.ps1)
    # so any LLM agent can bring the stack up/down or live-toggle spaces.
    {
        "name": "vibemind_launcher_status",
        "description": "Status aller Core-Services + Spaces des Vibemind-Stacks. Liefert JSON mit Container-Health (brain, rowboat, qdrant, supabase…), Native-Health (openfang, ollama, bridge, la-fungus, automation-ui) und der Aktiv/Inaktiv-Lage jedes Space (coding, n8n, mirofish, …).",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "vibemind_launcher_start",
        "description": "Startet den Vibemind-Stack mit der gegebenen Space-Auswahl (Core kommt immer mit). Funktioniert nur wenn der Stack noch nicht laeuft — fuer Live-Aenderungen `vibemind_launcher_apply` nehmen. Streamt KEIN Output zurueck (laeuft im Hintergrund), gibt sofort die submitted-Bestaetigung; Status via `vibemind_launcher_status` pollen.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spaces": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["coding", "mirofish", "n8n", "media", "logging", "core-phase-d"]},
                    "description": "Welche Spaces zusaetzlich zum Core hochfahren. Leeres Array = nur Core."
                }
            }
        }
    },
    {
        "name": "vibemind_launcher_stop",
        "description": "Faehrt den kompletten Vibemind-Stack runter (docker stack rm + native services). Named Volumes bleiben (qdrant, brain_data, rowboat_mongo, neo4j, …). Setzt den persistenten Space-State NICHT zurueck.",
        "inputSchema": {"type": "object", "properties": {}}
    },
    {
        "name": "vibemind_launcher_apply",
        "description": "Live-Re-Deploy mit der gegebenen Space-Auswahl. Funktioniert auch wenn der Stack schon laeuft — `docker stack deploy --prune` startet neue Services und entfernt abgewaehlte. Volumes bleiben.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "spaces": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["coding", "mirofish", "n8n", "media", "logging", "core-phase-d"]},
                    "description": "Vollstaendige Liste der Spaces die NACH dem Apply aktiv sein sollen. Was hier NICHT drin ist, wird gestoppt."
                }
            },
            "required": ["spaces"]
        }
    },
    {
        "name": "vibemind_launcher_presets",
        "description": "Verwaltet gespeicherte Space-Presets (~/.vibemind/presets.json). Sub-Action via `op`: list (Default), save (braucht name + spaces), delete (braucht name).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "op": {"type": "string", "enum": ["list", "save", "delete"], "default": "list"},
                "name": {"type": "string", "description": "Preset-Name fuer save/delete"},
                "spaces": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Space-Liste fuer save"
                }
            }
        }
    },
    {
        "name": "vibemind_launcher_logs",
        "description": "Liefert den letzten vibemind-start.ps1 / vibemind-stop.ps1 Transcript-Log + optional `docker stack ps vibemind` Events. Faengt UI-Klicks (Tauri-Launcher) UND MCP-Triggers (`vibemind_launcher_start/stop`), weil das Logging im PS1-Skript selbst sitzt. Use-Case: debug warum START nichts tut, ohne den UI-Log abtippen zu muessen.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {
                    "type": "string",
                    "enum": ["start", "stop", "both"],
                    "default": "start",
                    "description": "Welcher Skript-Lauf: start (Default), stop, oder both."
                },
                "lines": {
                    "type": "integer",
                    "default": 200,
                    "minimum": 10,
                    "maximum": 5000,
                    "description": "Maximale Zeilen vom Ende des Logs (Default 200)."
                },
                "include_stack_events": {
                    "type": "boolean",
                    "default": False,
                    "description": "Wenn true, haengt `docker stack ps vibemind --no-trunc` Output an (zeigt fehlgeschlagene Tasks + Container-Errors)."
                }
            }
        }
    },
]


def _get_space_agent(space: str):
    """Load a space's backend agent by name. Returns the agent or None."""
    AGENT_GETTERS = {
        "bubbles": "get_bubbles_agent",
        "ideas": "get_ideas_agent",
        "coding": "get_coding_agent",
        "desktop": "get_desktop_agent",
        "rowboat": "get_roarboot_agent",
        "research": "get_zeroclaw_research_agent",
        "minibook": "get_minibook_agent",
        "schedule": "get_schedule_agent",
        "n8n": "get_n8n_agent",
        "agentfarm": "get_agentfarm_agent",
        "video": "get_video_agent",
        "mirofish": "get_mirofish_agent",
        "flowzen": "get_flowzen_agent",
    }
    getter_name = AGENT_GETTERS.get(space)
    if not getter_name:
        return None
    try:
        import swarm.backend_agents as ba
        getter = getattr(ba, getter_name, None)
        if getter:
            return getter()
    except Exception:
        pass
    return None


# ── Launcher control helpers ──────────────────────────────────────────────
# Mirror what scripts/vibemind-spaces.ps1 and scripts/vibemind-start.ps1 do.
# Repo root resolved relative to THIS file: voice/python/.. = vibemind-os/..
import subprocess
_REPO_ROOT = Path(__file__).resolve().parents[3]  # vibemind_mcp.py -> python -> voice -> vibemind-os -> Vibemind_V1


def _run_spaces_ps1(args: list[str], timeout: int = 60) -> tuple[int, str, str]:
    """Call scripts/vibemind-spaces.ps1 with the given args. Returns (rc, stdout, stderr).
    Uses CREATE_NO_WINDOW on Windows so the MCP-side flash matches the launcher.
    """
    script = _REPO_ROOT / "scripts" / "vibemind-spaces.ps1"
    if not script.exists():
        return 127, "", f"script not found: {script}"
    cmd = [
        "pwsh.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script),
    ] + args
    flags = 0
    if sys.platform == "win32":
        flags = 0x08000000  # CREATE_NO_WINDOW
    try:
        proc = subprocess.run(
            cmd, cwd=str(_REPO_ROOT),
            capture_output=True, text=True, timeout=timeout,
            creationflags=flags,
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"timeout after {timeout}s"
    except Exception as e:
        return 1, "", str(e)


def _run_start_ps1_bg(spaces_csv: str) -> tuple[bool, str]:
    """Fire-and-forget the long-running vibemind-start.ps1. Returns (ok, message).
    Stack-boot is ~2-3min; the MCP tool must not block on it.
    """
    script = _REPO_ROOT / "scripts" / "vibemind-start.ps1"
    if not script.exists():
        return False, f"script not found: {script}"
    cmd = [
        "pwsh.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script),
        "-SkipVenv", "-SkipNode", "-SkipElectron",  # avoid double-spawn (Electron etc. drive themselves)
    ]
    if spaces_csv:
        cmd += ["-Spaces", spaces_csv]
    flags = 0
    detach = {}
    if sys.platform == "win32":
        flags = 0x08000000 | 0x00000008  # CREATE_NO_WINDOW | DETACHED_PROCESS
        detach = {"creationflags": flags}
    try:
        subprocess.Popen(
            cmd, cwd=str(_REPO_ROOT),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **detach,
        )
        return True, f"start submitted with spaces=[{spaces_csv}] — poll vibemind_launcher_status for progress"
    except Exception as e:
        return False, str(e)


def _run_stop_ps1_bg() -> tuple[bool, str]:
    """Fire-and-forget vibemind-stop.ps1."""
    script = _REPO_ROOT / "scripts" / "vibemind-stop.ps1"
    if not script.exists():
        return False, f"script not found: {script}"
    cmd = [
        "pwsh.exe", "-NoProfile", "-NonInteractive",
        "-ExecutionPolicy", "Bypass",
        "-File", str(script),
    ]
    flags = 0
    detach = {}
    if sys.platform == "win32":
        flags = 0x08000000 | 0x00000008
        detach = {"creationflags": flags}
    try:
        subprocess.Popen(
            cmd, cwd=str(_REPO_ROOT),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            **detach,
        )
        return True, "stop submitted — poll vibemind_launcher_status for progress"
    except Exception as e:
        return False, str(e)


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
                _of_url = os.environ.get("OPENFANG_URL", "http://localhost:4200").rstrip("/")
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

    elif name == "vibemind_rowboat_cleanup":
        dry_run = bool(args.get("dry_run", True))
        max_delete = int(args.get("max_delete", 200))
        try:
            from data import IdeasRepository
            from publishing.rowboat_mongo_publisher import RowboatMongoPublisher
            # Canonical live bubbles = top-level ideas (parent_id IS NULL).
            repo = IdeasRepository()
            bubbles = repo.list_top_level(limit=10000)
            live_titles = {b.title for b in bubbles if getattr(b, "title", None)}
            head = "🧹 Rowboat-Cleanup " + ("(DRY-RUN)" if dry_run else "(ECHT-LAUF)")
            lines = [head, f"  live bubbles: {len(live_titles)}"]

            # Ebene 1: RAG-MongoDB-Sources
            mrep = RowboatMongoPublisher().cleanup_orphaned_sources(
                live_titles, dry_run=dry_run, max_delete=max_delete
            )
            lines.append(
                f"  [MongoDB] geprueft: {mrep.get('checked')} | orphaned: {len(mrep.get('orphaned') or [])} | geloescht: {mrep.get('deleted')}"
                + (f"  ⚠️ {mrep['aborted']}" if mrep.get("aborted") else "")
            )

            # Ebene 2: Filesystem-Vault knowledge/Projects/'VibeMind - *'
            from publishing.ideas_publisher import IdeasPublisher
            frep = IdeasPublisher().cleanup_orphaned_project_dirs(
                live_titles, dry_run=dry_run, max_delete=max_delete
            )
            lines.append(
                f"  [Vault]   geprueft: {frep.get('checked')} | orphaned: {len(frep.get('orphaned') or [])} | geloescht: {frep.get('deleted')}"
                + (f"  ⚠️ {frep['aborted']}" if frep.get("aborted") else "")
            )

            orph = sorted(set((mrep.get("orphaned") or []) + (frep.get("orphaned") or [])))
            if orph:
                lines.append(f"  orphaned ({len(orph)} distinct):")
                for n in orph[:60]:
                    lines.append(f"    - {n}")
                if len(orph) > 60:
                    lines.append(f"    … (+{len(orph)-60} weitere)")
            return "\n".join(lines)
        except Exception as e:
            return f"Fehler beim Rowboat-Cleanup: {e}"

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

    # ─── Phase 7 Split: Bridge Tool handlers ───────────────────────────

    elif name == "vibemind_bubble_create":
        title = args.get("title", "").strip()
        description = args.get("description", "")
        if not title:
            return json.dumps({"success": False, "error": "title ist erforderlich"})
        try:
            from data import IdeasRepository
            repo = IdeasRepository()
            idea = repo.create(title=title, description=description)
            idea_id = idea.id if hasattr(idea, "id") else None
            # Broadcast to Electron
            try:
                from tools.workspace_tools import _broadcast_to_electron
                _broadcast_to_electron({
                    "type": "node_added",
                    "node": {"id": str(idea_id), "title": title, "description": description},
                })
            except Exception:
                pass
            return json.dumps({"success": True, "idea_id": str(idea_id), "title": title})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    elif name == "vibemind_bubble_update":
        bubble_id = args.get("bubble_id", "").strip()
        if not bubble_id:
            return json.dumps({"success": False, "error": "bubble_id ist erforderlich"})
        try:
            from data import IdeasRepository
            repo = IdeasRepository()
            updates = {}
            for k in ["title", "description", "score"]:
                if k in args and args[k] is not None:
                    updates[k] = args[k]
            if not updates:
                return json.dumps({"success": False, "error": "keine Felder zum Update"})
            if hasattr(repo, "update"):
                repo.update(bubble_id, **updates)
            try:
                from tools.workspace_tools import _broadcast_to_electron
                _broadcast_to_electron({"type": "node_updated", "node": {"id": bubble_id, **updates}})
            except Exception:
                pass
            return json.dumps({"success": True, "bubble_id": bubble_id, "updated": list(updates.keys())})
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    elif name == "vibemind_ui_command":
        command = args.get("command", "").strip()
        params = args.get("params", {})
        if not command:
            return json.dumps({"success": False, "error": "command ist erforderlich"})
        message = {"type": command, **(params or {})}
        delivered = False
        # Try Python IPC
        try:
            from tools.workspace_tools import _electron_send_message
            if _electron_send_message:
                _electron_send_message(message)
                delivered = True
        except Exception:
            pass
        # Try CDP
        if not delivered:
            CDP_PORT = int(os.environ.get("ELECTRON_CDP_PORT", "9223"))
            try:
                import websockets
                import urllib.request
                resp = urllib.request.urlopen(f"http://localhost:{CDP_PORT}/json", timeout=2)
                pages = json.loads(resp.read())
                for p in pages:
                    if "Multiverse" in p.get("title", "") or "renderer" in p.get("url", ""):
                        ws_url = p.get("webSocketDebuggerUrl")
                        if ws_url:
                            async with websockets.connect(ws_url) as ws:
                                js = f"window.postMessage({json.dumps(message)}, '*');"
                                await ws.send(json.dumps({"id": 99, "method": "Runtime.evaluate", "params": {"expression": js}}))
                                await asyncio.wait_for(ws.recv(), timeout=3)
                                delivered = True
                            break
            except Exception:
                pass
        return json.dumps({"success": True, "delivered": delivered, "command": command})

    elif name == "vibemind_agent_dispatch":
        task = args.get("task", "").strip()
        agent = args.get("agent")
        if not task:
            return json.dumps({"success": False, "error": "task ist erforderlich"})
        minibook_url = os.environ.get("MINIBOOK_URL", "http://localhost:3480")
        payload = {"content": f"@{agent} {task}" if agent else task, "metadata": args.get("context", {})}
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.post(f"{minibook_url}/api/tasks", json=payload, timeout=aiohttp.ClientTimeout(total=15)) as r:
                    data = await r.json()
                    return json.dumps({"success": True, "source": "minibook", "agent": agent, "result": data})
        except Exception:
            # Fallback: route via process_intent
            result = await _call_intent(task)
            return json.dumps({"success": True, "source": "intent_fallback", "result": result})

    elif name == "vibemind_agents_list":
        spaces = [
            {"name": "Bubbles", "stream": "events:tasks:bubbles", "prefix": "bubble.*"},
            {"name": "Ideas", "stream": "events:tasks:ideas", "prefix": "idea.*"},
            {"name": "Coding", "stream": "events:tasks:coding", "prefix": "code.*"},
            {"name": "Desktop", "stream": "events:tasks:desktop", "prefix": "desktop.*"},
            {"name": "Rowboat", "stream": "events:tasks:roarboot", "prefix": "roarboot.*"},
            {"name": "Research", "stream": "events:tasks:zeroclaw", "prefix": "research.*"},
            {"name": "Minibook", "stream": "events:tasks:minibook", "prefix": "minibook.*"},
            {"name": "Schedule", "stream": "events:tasks:schedule", "prefix": "schedule.*"},
            {"name": "N8n", "stream": "events:tasks:n8n", "prefix": "n8n.*"},
            {"name": "AgentFarm", "stream": "events:tasks:agentfarm", "prefix": "agentfarm.*"},
            {"name": "Video", "stream": "events:tasks:video", "prefix": "video.*"},
            {"name": "MiroFish", "stream": "events:tasks:mirofish_pred", "prefix": "mirofish.*"},
            {"name": "Flowzen", "stream": "via submodule", "prefix": "flowzen.*"},
            {"name": "Brain", "stream": "standalone (port 5000)", "prefix": "brain.*"},
        ]
        brain_status = None
        try:
            import aiohttp
            async with aiohttp.ClientSession() as s:
                async with s.get("http://localhost:5000/api/cortex/classify/stats", timeout=aiohttp.ClientTimeout(total=2)) as r:
                    if r.status == 200:
                        brain_status = await r.json()
        except Exception:
            pass
        return json.dumps({
            "success": True,
            "spaces": spaces,
            "space_count": len(spaces),
            "brain": {"reachable": brain_status is not None, "stats": brain_status},
        })

    elif name == "vibemind_intent":
        text = args.get("text", "").strip()
        if not text:
            return json.dumps({"success": False, "error": "text ist erforderlich"})
        result = await _call_intent(text)
        return json.dumps(result)

    # ─── Space Debugging Handlers ────────────────────────────────────

    elif name == "vibemind_space_inspect":
        space = args.get("space", "").strip().lower()
        agent = _get_space_agent(space)
        if agent is None:
            return json.dumps({"success": False, "error": f"Space '{space}' nicht ladbar"})
        try:
            info = {
                "success": True,
                "space": space,
                "agent_name": agent.name if hasattr(agent, "name") else type(agent).__name__,
                "agent_class": type(agent).__name__,
                "stream": agent.stream if hasattr(agent, "stream") else None,
                "param_mapping": agent.PARAM_MAPPING if hasattr(agent, "PARAM_MAPPING") else {},
            }
            # Load tools
            tools = agent.tools if hasattr(agent, "tools") else {}
            info["tool_count"] = len(tools)
            info["tools"] = sorted(tools.keys()) if isinstance(tools, dict) else []
            # TOOL_MAP if available
            if hasattr(agent, "TOOL_MAP"):
                info["tool_map"] = agent.TOOL_MAP
            # Try _get_tool_name for common events
            if hasattr(agent, "_get_tool_name"):
                test_events = [f"{space.replace('rowboat','roarboot')}.list", f"{space.replace('rowboat','roarboot')}.create", f"{space.replace('rowboat','roarboot')}.status"]
                mappings = {}
                for evt in test_events:
                    try:
                        tool_name = agent._get_tool_name(evt)
                        if tool_name:
                            mappings[evt] = tool_name
                    except Exception:
                        pass
                if mappings:
                    info["event_to_tool_samples"] = mappings
            return json.dumps(info, default=str)
        except Exception as e:
            return json.dumps({"success": False, "error": str(e)})

    elif name == "vibemind_space_test":
        space = args.get("space", "").strip().lower()
        event_type = args.get("event_type", "").strip()
        payload = args.get("payload", {})
        if not event_type:
            return json.dumps({"success": False, "error": "event_type ist erforderlich"})
        agent = _get_space_agent(space)
        if agent is None:
            return json.dumps({"success": False, "error": f"Space '{space}' nicht ladbar"})
        try:
            # Find the tool function
            tool_name = None
            if hasattr(agent, "_get_tool_name"):
                tool_name = agent._get_tool_name(event_type)
            if not tool_name and hasattr(agent, "TOOL_MAP"):
                tool_name = agent.TOOL_MAP.get(event_type)
            if not tool_name:
                available = sorted(agent.tools.keys()) if hasattr(agent, "tools") else []
                return json.dumps({
                    "success": False,
                    "error": f"Kein Tool fuer event_type '{event_type}' in Space '{space}'",
                    "available_tools": available,
                })
            tools = agent.tools if hasattr(agent, "tools") else {}
            tool_fn = tools.get(tool_name)
            if not tool_fn:
                return json.dumps({"success": False, "error": f"Tool '{tool_name}' nicht geladen"})
            # Normalize params
            if hasattr(agent, "PARAM_MAPPING") and event_type in agent.PARAM_MAPPING:
                for src, dst in agent.PARAM_MAPPING[event_type].items():
                    if src in payload:
                        payload[dst] = payload.pop(src)
            # Execute
            if asyncio.iscoroutinefunction(tool_fn):
                result = await tool_fn(payload) if payload else await tool_fn()
            else:
                result = tool_fn(payload) if payload else tool_fn()
            return json.dumps({
                "success": True,
                "space": space,
                "event_type": event_type,
                "tool_name": tool_name,
                "result": result,
            }, default=str)
        except Exception as e:
            return json.dumps({"success": False, "space": space, "event_type": event_type, "error": str(e)})

    elif name == "vibemind_spaces_overview":
        overview = []
        for space_name in ["bubbles", "ideas", "coding", "desktop", "rowboat",
                           "research", "minibook", "schedule", "n8n", "agentfarm",
                           "video", "mirofish", "flowzen"]:
            entry = {"space": space_name, "loaded": False}
            try:
                agent = _get_space_agent(space_name)
                if agent:
                    entry["loaded"] = True
                    entry["agent_class"] = type(agent).__name__
                    entry["stream"] = agent.stream if hasattr(agent, "stream") else None
                    tools = agent.tools if hasattr(agent, "tools") else {}
                    entry["tool_count"] = len(tools)
                    if hasattr(agent, "TOOL_MAP"):
                        entry["event_types"] = len(agent.TOOL_MAP)
            except Exception as e:
                entry["error"] = str(e)[:100]
            overview.append(entry)
        return json.dumps({"success": True, "spaces": overview, "total": len(overview)}, default=str)

    elif name == "vibemind_space_health":
        space = args.get("space", "all").strip().lower()
        # Read-only event patterns — safe to call with empty/default params
        READ_ONLY_PATTERNS = {"list", "status", "get", "find", "search", "describe", "count"}
        # Dangerous — never execute, only check existence
        DANGEROUS_PATTERNS = {"delete", "cancel", "stop", "reset", "remove", "delete_all"}
        # Write ops — check loadability but don't execute (avoids creating real data)
        WRITE_PATTERNS = {"create", "update", "promote", "score", "enter", "connect",
                          "generate", "run", "activate", "send", "type", "click",
                          "open", "draft", "clone", "build", "move", "convert",
                          "train", "modify", "publish", "evaluate", "accept", "reject"}

        # Default test params per event pattern — so write ops actually get called
        DEFAULT_TEST_PARAMS = {
            "create": {"title": "[HEALTH_CHECK_TEST]", "description": "auto-test"},
            "enter": {"bubble_name": "VibeMind"},
            "exit": {},
            "find": {"query": "test"},
            "search": {"query": "test"},
            "list": {},
            "status": {},
            "get": {},
            "count": {},
            "update": {"idea_name": "[HEALTH_CHECK_TEST]", "new_content": "test"},
            "score": {"bubble_name": "VibeMind"},
            "evaluate": {"bubble_name": "VibeMind"},
            "promote": {"bubble_name": "VibeMind"},
            "connect": {"idea1": "test1", "idea2": "test2"},
            "format": {"idea_name": "test"},
            "generate": {"description": "health check test"},
            "open_app": {"app_name": "notepad"},
            "click": {"element_description": "test"},
            "type": {"text": "health_check"},
            "query": {"subject": "test"},
            "recommend": {},
            "run": {"task": "health check"},
            "activate": {"name": "test"},
            "describe": {"name": "test"},
            "execute": {"name": "test"},
        }

        spaces_to_test = [space] if space != "all" else [
            "bubbles", "ideas", "desktop", "rowboat", "minibook", "n8n",
            "coding", "research", "schedule", "agentfarm", "video", "mirofish", "flowzen",
        ]

        all_results = []
        for sp in spaces_to_test:
            space_result = {"space": sp, "agent_loaded": False, "events": [], "summary": {}}
            agent = _get_space_agent(sp)
            if not agent:
                space_result["error"] = "Agent konnte nicht geladen werden"
                all_results.append(space_result)
                continue

            space_result["agent_loaded"] = True
            space_result["agent_class"] = type(agent).__name__
            space_result["stream"] = agent.stream if hasattr(agent, "stream") else None

            # Get TOOL_MAP
            tool_map = {}
            if hasattr(agent, "TOOL_MAP"):
                tool_map = agent.TOOL_MAP
            elif hasattr(agent, "_get_tool_name"):
                # Build from tools dict
                tools = agent.tools if hasattr(agent, "tools") else {}
                for t_name in tools:
                    tool_map[t_name] = t_name

            tools_dict = agent.tools if hasattr(agent, "tools") else {}
            ok_count = 0
            error_count = 0
            loadable_count = 0
            skipped_count = 0

            for event_type, tool_name in sorted(tool_map.items()):
                entry = {
                    "event": event_type,
                    "tool": tool_name,
                    "status": "unknown",
                }

                # Check if tool function exists
                tool_fn = tools_dict.get(tool_name)
                if not tool_fn:
                    entry["status"] = "missing"
                    entry["error"] = f"Tool '{tool_name}' nicht in tools dict geladen"
                    error_count += 1
                    space_result["events"].append(entry)
                    continue

                # Classify the event
                event_parts = event_type.lower().split(".")
                last_part = event_parts[-1] if event_parts else ""

                is_dangerous = any(p in last_part for p in DANGEROUS_PATTERNS)

                is_write = any(p in last_part for p in WRITE_PATTERNS)

                if is_dangerous:
                    entry["status"] = "exists"
                    entry["note"] = "dangerous — nicht ausgefuehrt"
                    skipped_count += 1
                elif is_write:
                    entry["status"] = "loadable"
                    entry["note"] = "write op — Tool geladen, nicht ausgefuehrt (keine Seiteneffekte)"
                    loadable_count += 1
                else:
                    # TRY calling it — find matching test params
                    test_params = {}
                    for pattern, params in DEFAULT_TEST_PARAMS.items():
                        if pattern in last_part or pattern in event_type.lower():
                            test_params = dict(params)
                            break

                    try:
                        # Tools have different calling conventions:
                        #   A) tool_fn(params_dict) — BaseBackendAgent style
                        #   B) tool_fn(**kwargs) — direct keyword args
                        #   C) tool_fn() — no args
                        # Try A first, then B, then C.
                        call_result = None
                        call_ok = False
                        # Try multiple calling conventions:
                        # 1. fn(params_dict)     — BaseBackendAgent style
                        # 2. fn(**kwargs)         — keyword args
                        # 3. fn(first_string_val) — adapted tools expect a string
                        # 4. fn()                 — no args
                        attempts = []
                        if test_params:
                            attempts.append(("dict", lambda: tool_fn(test_params)))
                            attempts.append(("kwargs", lambda: tool_fn(**test_params)))
                            # Some tools expect a single string arg (title, query, etc.)
                            first_val = next(iter(test_params.values()), None)
                            if isinstance(first_val, str):
                                attempts.append(("string", lambda fv=first_val: tool_fn(fv)))
                        attempts.append(("none", lambda: tool_fn()))

                        for style, caller in attempts:
                            try:
                                if asyncio.iscoroutinefunction(tool_fn):
                                    call_result = await asyncio.wait_for(
                                        caller() if not asyncio.iscoroutinefunction(caller) else caller(),
                                        timeout=5.0
                                    )
                                else:
                                    call_result = caller()
                                call_ok = True
                                entry["call_style"] = style
                                break
                            except (TypeError, AttributeError):
                                continue  # wrong calling convention
                        if not call_ok:
                            raise TypeError(f"no calling convention worked for {tool_name}")
                        result = call_result
                        entry["status"] = "ok"
                        if isinstance(result, str):
                            entry["result_preview"] = result[:200]
                        elif isinstance(result, dict):
                            entry["result_preview"] = str(result)[:200]
                        elif isinstance(result, list):
                            entry["result_preview"] = f"{len(result)} items"
                        else:
                            entry["result_preview"] = str(result)[:150]
                        if test_params:
                            entry["test_params"] = test_params
                        ok_count += 1
                    except asyncio.TimeoutError:
                        entry["status"] = "timeout"
                        entry["error"] = "5s timeout"
                        error_count += 1
                    except Exception as e:
                        entry["status"] = "error"
                        entry["error"] = str(e)[:150]
                        if test_params:
                            entry["test_params"] = test_params
                        error_count += 1

                space_result["events"].append(entry)

            space_result["summary"] = {
                "total": len(tool_map),
                "ok": ok_count,
                "loadable": loadable_count,
                "error": error_count,
                "skipped": skipped_count,
            }
            all_results.append(space_result)

        if len(all_results) == 1:
            return json.dumps(all_results[0], default=str, ensure_ascii=False)
        return json.dumps({"success": True, "spaces": all_results}, default=str, ensure_ascii=False)

    # ── Launcher control ──────────────────────────────────────────────────
    elif name == "vibemind_launcher_status":
        rc_c, core_out, core_err = _run_spaces_ps1(["core-status"], timeout=30)
        rc_s, spaces_out, spaces_err = _run_spaces_ps1(["list"], timeout=15)
        result = {"success": rc_c == 0 and rc_s == 0}
        if rc_c == 0:
            try: result["core"] = json.loads(core_out.strip())
            except Exception as e: result["core_parse_error"] = str(e); result["core_raw"] = core_out[:500]
        else:
            result["core_error"] = core_err or "core-status failed"
        if rc_s == 0:
            try: result["spaces"] = json.loads(spaces_out.strip())
            except Exception as e: result["spaces_parse_error"] = str(e); result["spaces_raw"] = spaces_out[:500]
        else:
            result["spaces_error"] = spaces_err or "list failed"
        return json.dumps(result, ensure_ascii=False)

    elif name == "vibemind_launcher_start":
        spaces = args.get("spaces") or []
        csv = ",".join(s.strip() for s in spaces if s.strip())
        ok, msg = _run_start_ps1_bg(csv)
        return json.dumps({"success": ok, "message": msg, "spaces": spaces}, ensure_ascii=False)

    elif name == "vibemind_launcher_stop":
        ok, msg = _run_stop_ps1_bg()
        return json.dumps({"success": ok, "message": msg}, ensure_ascii=False)

    elif name == "vibemind_launcher_apply":
        spaces = args.get("spaces")
        if spaces is None:
            return json.dumps({"success": False, "error": "apply requires `spaces` array (use [] for core-only)"})
        csv = ",".join(s.strip() for s in spaces if s.strip())
        rc, out, err = _run_spaces_ps1(["apply", csv], timeout=300)
        return json.dumps({
            "success": rc == 0,
            "spaces": spaces,
            "stdout_tail": out[-400:] if out else "",
            "stderr_tail": err[-200:] if err else "",
            "exit_code": rc,
        }, ensure_ascii=False)

    elif name == "vibemind_launcher_logs":
        kind = args.get("kind", "start")
        line_count = int(args.get("lines", 200))
        include_events = bool(args.get("include_stack_events", False))
        log_dir = _REPO_ROOT / "logs" / "launcher"

        def _read_latest(prefix: str) -> dict:
            if not log_dir.is_dir():
                return {"found": False, "reason": f"{log_dir} does not exist yet — no run captured"}
            candidates = sorted(
                log_dir.glob(f"{prefix}-*.log"),
                key=lambda p: p.stat().st_mtime,
                reverse=True,
            )
            if not candidates:
                return {"found": False, "reason": f"no {prefix}-*.log in {log_dir}"}
            latest = candidates[0]
            try:
                text = latest.read_text(encoding="utf-8", errors="replace")
            except OSError as e:
                return {"found": False, "reason": f"read failed: {e}", "path": str(latest)}
            lines = text.splitlines()
            tail = lines[-line_count:] if len(lines) > line_count else lines
            return {
                "found": True,
                "path": str(latest),
                "total_lines": len(lines),
                "returned_lines": len(tail),
                "log": "\n".join(tail),
            }

        result: dict = {"success": True}
        if kind in ("start", "both"):
            result["start"] = _read_latest("start")
        if kind in ("stop", "both"):
            result["stop"] = _read_latest("stop")

        if include_events:
            try:
                # First: does the stack even exist? Avoids the misleading
                # `exit 1 / nothing found in stack` confusion.
                ls_proc = subprocess.run(
                    ["docker", "stack", "ls", "--format", "{{.Name}}"],
                    capture_output=True, text=True, timeout=10,
                )
                stacks = [s.strip() for s in ls_proc.stdout.splitlines() if s.strip()]
                deployed = "vibemind" in stacks

                if not deployed:
                    result["stack_events"] = {
                        "stack_status": "not_deployed",
                        "deployed_stacks": stacks,
                        "hint": "vibemind stack is not running — start it via vibemind_launcher_start or the Tauri UI.",
                    }
                else:
                    proc = subprocess.run(
                        ["docker", "stack", "ps", "vibemind", "--no-trunc",
                         "--format", "{{.Name}}\t{{.CurrentState}}\t{{.Error}}"],
                        capture_output=True, text=True, timeout=15,
                    )
                    events = proc.stdout.strip()
                    rows = events.splitlines() if events else []
                    # Filter to rows with an error message (Error column non-empty).
                    errors = [
                        line for line in rows
                        if line.count("\t") >= 2 and line.split("\t")[2].strip()
                    ]
                    result["stack_events"] = {
                        "stack_status": "deployed",
                        "exit_code": proc.returncode,
                        "stderr_tail": (proc.stderr or "").strip().splitlines()[-5:],
                        "task_count": len(rows),
                        "error_rows": errors[:50],
                        "raw_tail": rows[-30:],
                    }
            except Exception as e:
                result["stack_events"] = {"error": str(e)}

        return json.dumps(result, ensure_ascii=False, default=str)

    elif name == "vibemind_launcher_presets":
        op = args.get("op", "list")
        if op == "list":
            rc, out, err = _run_spaces_ps1(["presets-list"], timeout=10)
            if rc != 0:
                return json.dumps({"success": False, "error": err or "presets-list failed"})
            try:
                return json.dumps({"success": True, "presets": json.loads(out.strip())}, ensure_ascii=False)
            except Exception as e:
                return json.dumps({"success": False, "error": f"parse: {e}", "raw": out[:500]})
        elif op == "save":
            n = (args.get("name") or "").strip()
            sps = args.get("spaces") or []
            if not n:
                return json.dumps({"success": False, "error": "save requires `name`"})
            csv = ",".join(s.strip() for s in sps if s.strip())
            rc, out, err = _run_spaces_ps1(["presets-save", n, csv], timeout=10)
            return json.dumps({"success": rc == 0, "name": n, "spaces": sps, "stderr": err[:200] if err else ""}, ensure_ascii=False)
        elif op == "delete":
            n = (args.get("name") or "").strip()
            if not n:
                return json.dumps({"success": False, "error": "delete requires `name`"})
            rc, out, err = _run_spaces_ps1(["presets-delete", n], timeout=10)
            return json.dumps({"success": rc == 0, "name": n, "stderr": err[:200] if err else ""}, ensure_ascii=False)
        else:
            return json.dumps({"success": False, "error": f"unknown op: {op}"})

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
