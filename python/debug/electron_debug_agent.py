#!/usr/bin/env python3
"""
Electron Debug Agent - AutoGen 0.7.x
Verbindet sich mit Electron via CDP und erstellt kontinuierliche Debug-Logs.

Usage:
    1. Starte Electron mit: electron --remote-debugging-port=9222 electron-app
    2. Starte diesen Agent: python electron_debug_agent.py
"""

import os
import sys
import json
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

# Ensure python/ is on sys.path so llm_config and other modules are importable
_PYTHON_DIR = str(Path(__file__).resolve().parent.parent)
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)

# Load .env from project root (two levels up from python/debug/)
try:
    from dotenv import load_dotenv
    _project_root = Path(__file__).resolve().parent.parent.parent
    load_dotenv(_project_root / ".env")
except ImportError:
    pass

logger = logging.getLogger(__name__)

# AutoGen 0.7.x imports
try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.messages import TextMessage
    from autogen_agentchat.conditions import TextMentionTermination
    from autogen_agentchat.ui import Console
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_core import CancellationToken
    from autogen_core.tools import FunctionTool
    from autogen_ext.models.openai import OpenAIChatCompletionClient
    HAS_AUTOGEN = True
except ImportError:
    HAS_AUTOGEN = False
    print("WARNING: AutoGen 0.7.x not installed. Install with: pip install autogen-agentchat~=0.7")

# CDP via websockets
try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False
    print("WARNING: websockets not installed. Install with: pip install websockets")

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    print("WARNING: aiohttp not installed. Install with: pip install aiohttp")

# Enable ANSI escape codes on Windows CMD (Virtual Terminal Processing)
if sys.platform == "win32":
    try:
        import ctypes
        _kernel32 = ctypes.windll.kernel32
        _kernel32.SetConsoleMode(_kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass  # Fallback: colors won't render but nothing breaks


# ========================================================================
# CONFIGURATION
# ========================================================================

@dataclass
class DebugConfig:
    """Debug Agent Configuration."""
    cdp_ports: List[int] = field(default_factory=lambda: [9222, 9223, 9224])  # Try multiple ports
    cdp_host: str = "127.0.0.1"
    log_dir: Path = field(default_factory=lambda: Path("logs/electron_debug"))
    log_console: bool = True
    log_network: bool = True
    log_errors: bool = True
    log_dom: bool = False
    max_log_size_mb: int = 50
    rotation_count: int = 5

    @property
    def cdp_port(self) -> int:
        """Return first port for compatibility."""
        return self.cdp_ports[0] if self.cdp_ports else 9222


# ========================================================================
# CDP CLIENT
# ========================================================================

class CDPClient:
    """Chrome DevTools Protocol Client for Electron debugging."""

    
    def __init__(self, config: DebugConfig):
        self.config = config
        self.ws: Optional[Any] = None
        self.ws_url: Optional[str] = None
        self.connected_port: Optional[int] = None
        self.message_id = 0
        self.pending_responses: Dict[int, asyncio.Future] = {}
        self.event_handlers: Dict[str, List[Callable]] = {}
        self._receive_task: Optional[asyncio.Task] = None
        
    async def connect(self) -> bool:
        """Connect to Electron via CDP, trying multiple ports."""
        if not HAS_AIOHTTP or not HAS_WEBSOCKETS:
            return False
        
        # Try each port in sequence
        ports_to_try = self.config.cdp_ports
        
        for port in ports_to_try:
            try:
                print(f"CDP: Trying port {port}...")
                # Get WebSocket URL from /json endpoint
                url = f"http://{self.config.cdp_host}:{port}/json"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                        if resp.status != 200:
                            print(f"CDP: Port {port} - Failed: {resp.status}")
                            continue
                        targets = await resp.json()
            
            except asyncio.TimeoutError:
                print(f"CDP: Port {port} - Timeout")
                continue
            except Exception as e:
                print(f"CDP: Port {port} - Error: {e}")
                continue
            
            if not targets:
                print(f"CDP: Port {port} - No targets found")
                continue
            
            # Find page target
            page_target = None
            for target in targets:
                if target.get("type") == "page":
                    page_target = target
                    break
            
            if not page_target:
                page_target = targets[0]
            
            self.ws_url = page_target.get("webSocketDebuggerUrl")
            if not self.ws_url:
                print(f"CDP: Port {port} - No WebSocket URL found")
                continue
            
            print(f"CDP: Connecting to {self.ws_url}")
            self.ws = await websockets.connect(self.ws_url)
            self.connected_port = port
            
            # Start message receiver
            self._receive_task = asyncio.create_task(self._receive_messages())
            
            print(f"CDP: Connected on port {port}!")
            return True
        
        print(f"CDP: Failed to connect on any port: {ports_to_try}")
        return False
    
    async def disconnect(self):
        """Disconnect from CDP."""
        if self._receive_task:
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        
        if self.ws:
            await self.ws.close()
            self.ws = None
    
    async def send(self, method: str, params: Dict = None) -> Dict:
        """Send CDP command and wait for response."""
        logger.debug("CDPClient.send: method=%s", method)
        if not self.ws:
            raise RuntimeError("Not connected")

        self.message_id += 1
        msg_id = self.message_id
        
        message = {
            "id": msg_id,
            "method": method,
            "params": params or {}
        }
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self.pending_responses[msg_id] = future
        
        await self.ws.send(json.dumps(message))
        
        try:
            result = await asyncio.wait_for(future, timeout=10.0)
            return result
        except asyncio.TimeoutError:
            del self.pending_responses[msg_id]
            raise
    
    async def _receive_messages(self):
        """Background task to receive CDP messages."""
        try:
            async for message in self.ws:
                data = json.loads(message)
                
                # Response to a command
                if "id" in data:
                    msg_id = data["id"]
                    if msg_id in self.pending_responses:
                        future = self.pending_responses.pop(msg_id)
                        if "error" in data:
                            future.set_exception(Exception(data["error"]))
                        else:
                            future.set_result(data.get("result", {}))
                
                # Event
                elif "method" in data:
                    method = data["method"]
                    params = data.get("params", {})
                    
                    if method in self.event_handlers:
                        for handler in self.event_handlers[method]:
                            try:
                                await handler(params)
                            except Exception as e:
                                print(f"CDP: Event handler error: {e}")
                                
        except websockets.exceptions.ConnectionClosed:
            print("CDP: Connection closed")
        except asyncio.CancelledError:
            pass
    
    def on(self, event: str, handler: Callable):
        """Register event handler."""
        if event not in self.event_handlers:
            self.event_handlers[event] = []
        self.event_handlers[event].append(handler)
    
    async def enable_domains(self):
        """Enable CDP domains for debugging."""
        await self.send("Runtime.enable")
        
        # Console.enable might not be available in Node.js inspector
        try:
            await self.send("Console.enable")
        except Exception:
            print("CDP: Console.enable not available (Node.js inspector)")
        
        # Log.enable is Chrome-specific, not available in Node.js
        try:
            await self.send("Log.enable")
        except Exception:
            print("CDP: Log.enable not available (Node.js inspector)")
        
        if self.config.log_network:
            try:
                await self.send("Network.enable")
            except Exception:
                print("CDP: Network.enable not available")
        
        if self.config.log_dom:
            try:
                await self.send("DOM.enable")
            except Exception:
                print("CDP: DOM.enable not available")
        
        print("CDP: Domains enabled")


# ========================================================================
# SPACE LOG COLORING (mirrors python/swarm/logging/space_logger.py)
# ========================================================================

SPACE_ANSI = {
    "bubbles": "\033[96m", "ideas": "\033[92m", "coding": "\033[93m",
    "desktop": "\033[95m", "rowboat": "\033[94m", "research": "\033[91m",
    "minibook": "\033[97m", "schedule": "\033[36m", "voice": "\033[33m",
    "orchestrator": "\033[35m", "brain": "\033[32m", "system": "\033[2m",
}
SPACE_TAGS = {
    "bubbles": "[BUBBLES]", "ideas": "[IDEAS]", "coding": "[CODING]",
    "desktop": "[DESKTOP]", "rowboat": "[ROWBOAT]", "research": "[RESEARCH]",
    "minibook": "[MINIBOOK]", "schedule": "[SCHEDULE]", "voice": "[VOICE]",
    "orchestrator": "[ORCH]", "brain": "[BRAIN]", "system": "[SYSTEM]",
}
LEVEL_ANSI = {
    "DEBUG": "\033[2m", "INFO": "", "WARNING": "\033[93m",
    "ERROR": "\033[91m", "CRITICAL": "\033[91;1m",
}
RST = "\033[0m"
DIM = "\033[2m"

# Node.js service prefix → space mapping (for non-Python logs)
NODE_SERVICE_SPACE = {
    "[GraphBuilder]": "rowboat", "[Rowboat]": "rowboat",
    "[Main]": "system", "[DockerManager]": "system",
    "[PortAllocator]": "system", "[Brain-Server]": "brain",
    "[BrainManager]": "brain", "[Fireflies]": "system",
    "[Granola]": "system", "[PreBuilt]": "system",
    "[AgentRunner]": "system", "[DEBUG]": "system",
    "[Python stderr]": "system", "[Python stdout]": "system",
    "[Python ERROR]": "system", "[Python]": "system",
    "[eyeTerm]": "desktop", "[Coding Engine]": "coding",
    "[Sensory]": "brain", "[AgentLoop]": "brain",
    "[Production": "brain",
    "Google OAuth": "system", "Sleeping for": "system",
}

# Suppress high-frequency noise lines
SUPPRESS_PATTERNS = (
    "Forwarded to renderer:",
    '"objectId"',
    '"className": "Object"',
    "Electron Security Warning (Insecure Content-Security-Policy)",
    "This warning will not show up",
)


def _print_space_log(log: Dict):
    """Print a SpaceLogger JSON log with ANSI colors (whole line in space color)."""
    s = log.get("s", "system")
    tag = SPACE_TAGS.get(s, "[SYSTEM]").ljust(10)
    color = SPACE_ANSI.get(s, SPACE_ANSI["system"])
    level_pad = (log.get("l", "") or "").ljust(5)
    ts = log.get("t", "")
    msg = log.get("m", "")
    print(f"{color}{tag} {level_pad} [{ts}] {msg}{RST}")


def _print_ipc_log(obj: Dict):
    """Print an IPC trace log in dim style."""
    d = obj.get("dir", "\u2192")
    label = f"Python{d}Electron" if d == "\u2192" else f"Electron{d}Python"
    t = obj.get("type", "?")
    preview = obj.get("preview", "")
    # Truncate long previews
    if len(preview) > 120:
        preview = preview[:120] + "..."
    print(f"{DIM}[IPC]      {label} {t}: {preview}{RST}")


def _should_suppress(message: str) -> bool:
    """Check if a message should be suppressed (noise reduction)."""
    for pattern in SUPPRESS_PATTERNS:
        if pattern in message:
            return True
    return False


def _detect_node_service_space(message: str) -> Optional[str]:
    """Detect space from Node.js service prefix in message."""
    for prefix, space in NODE_SERVICE_SPACE.items():
        if prefix in message:
            return space
    return None


# ========================================================================
# DEBUG LOGGER
# ========================================================================

class DebugLogger:
    """Writes structured debug logs."""
    
    def __init__(self, config: DebugConfig):
        self.config = config
        self.log_file: Optional[Path] = None
        self.log_handle = None
        self.entry_count = 0
        
        # Create log directory
        config.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup file logging
        self._setup_log_file()
    
    def _setup_log_file(self):
        """Setup log file with timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.config.log_dir / f"electron_debug_{timestamp}.jsonl"
        self.log_handle = open(self.log_file, "w", encoding="utf-8")
        print(f"Debug logs: {self.log_file}")
    
    def log(self, category: str, level: str, message: str, data: Dict = None, silent: bool = False):
        """Write a log entry.

        Args:
            silent: If True, only write to file without printing to console.
                    Used when caller already printed a colored line.
        """
        entry = {
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "level": level,
            "message": message,
            "data": data or {}
        }

        # Write to file
        if self.log_handle:
            self.log_handle.write(json.dumps(entry) + "\n")
            self.log_handle.flush()

        # Print to console (unless caller already did)
        if not silent:
            level_colors = {
                "error": "\033[91m",
                "warning": "\033[93m",
                "info": "\033[94m",
                "debug": "\033[90m"
            }
            reset = "\033[0m"
            color = level_colors.get(level, "")
            print(f"{color}[{category}] {level.upper()}: {message}{reset}", flush=True)

        self.entry_count += 1
        
        # Check rotation
        if self.log_file and self.log_file.stat().st_size > self.config.max_log_size_mb * 1024 * 1024:
            self._rotate_log()
    
    def _rotate_log(self):
        """Rotate log file."""
        if self.log_handle:
            self.log_handle.close()
        self._setup_log_file()
    
    def close(self):
        """Close log file."""
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None


# ========================================================================
# DEBUG AGENT (AutoGen 0.7.x)
# ========================================================================

class ElectronDebugAgent:
    """
    AutoGen 0.7.x Agent that monitors Electron app via CDP.
    Creates continuous debug logs, auto-analyzes issues,
    and pushes toast notifications into the Electron renderer.
    """

    def __init__(self, config: DebugConfig = None):
        self.config = config or DebugConfig()
        self.cdp = CDPClient(self.config)
        self.logger = DebugLogger(self.config)
        self.running = False

        # Stats
        self.stats = {
            "console_logs": 0,
            "errors": 0,
            "warnings": 0,
            "network_requests": 0,
            "start_time": None
        }

        # Auto-analysis: buffer issues, debounce, then analyze
        self._issue_buffer: List[Dict] = []
        self._debounce_task: Optional[asyncio.Task] = None
        self._debounce_seconds: float = 3.0
        self._analyzing: bool = False
        self._toast_id: int = 0

        # AutoGen agent (optional, for analysis)
        self.autogen_agent = None
        if HAS_AUTOGEN:
            self._setup_autogen_agent()
    
    def _setup_autogen_agent(self):
        """Setup AutoGen agent for log analysis."""
        # Define tools for the agent
        async def analyze_logs(query: str) -> str:
            """Analyze recent logs for patterns or issues."""
            # Read last 100 entries
            if not self.logger.log_file or not self.logger.log_file.exists():
                return "No logs available yet."
            
            entries = []
            with open(self.logger.log_file, "r") as f:
                for line in f:
                    try:
                        entries.append(json.loads(line))
                    except:
                        pass
            
            # Filter errors
            errors = [e for e in entries if e.get("level") == "error"]
            warnings = [e for e in entries if e.get("level") == "warning"]
            
            return f"""Log Analysis:
- Total entries: {len(entries)}
- Errors: {len(errors)}
- Warnings: {len(warnings)}

Recent errors:
{json.dumps(errors[-5:], indent=2) if errors else 'None'}"""
        
        async def get_stats() -> str:
            """Get current debug statistics."""
            duration = "N/A"
            if self.stats["start_time"]:
                delta = datetime.now() - self.stats["start_time"]
                duration = str(delta).split(".")[0]
            
            return f"""Debug Statistics:
- Running for: {duration}
- Console logs: {self.stats['console_logs']}
- Errors: {self.stats['errors']}
- Warnings: {self.stats['warnings']}
- Network requests: {self.stats['network_requests']}
- Log file: {self.logger.log_file}
"""
        
        # Create tools
        analyze_tool = FunctionTool(analyze_logs, description="Analyze debug logs for patterns or issues")
        stats_tool = FunctionTool(get_stats, description="Get current debugging statistics")

        # Create model client via centralized LLM config
        from llm_config import get_model, get_model_config
        cfg = get_model_config("desktop_orchestrator")
        model_name = cfg["model"]
        api_key = cfg["api_key"]
        base_url = cfg["base_url"]

        if not api_key:
            # Fallback: try OpenRouter
            api_key = os.getenv("OPENROUTER_API_KEY", "") or os.getenv("OPENAI_API_KEY", "")
            if not api_key:
                print("WARNING: No API key found for debug analysis (set OPENROUTER_API_KEY or OPENAI_API_KEY)")
                return

        client_kwargs = {"model": model_name, "api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
            client_kwargs["model_info"] = {
                "vision": False,
                "function_calling": True,
                "json_output": True,
                "structured_output": False,
                "family": model_name.split("/")[-1] if "/" in model_name else model_name,
            }

        model_client = OpenAIChatCompletionClient(**client_kwargs)
        
        self.autogen_agent = AssistantAgent(
            name="ElectronDebugger",
            model_client=model_client,
            tools=[analyze_tool, stats_tool],
            system_message="""You are an Electron debugging assistant.
You monitor application logs and help identify issues.
When errors occur, analyze them and suggest fixes."""
        )

    
    # ------------------------------------------------------------------
    # Auto-analysis: buffer → debounce → analyze → toast
    # ------------------------------------------------------------------

    def _buffer_issue(self, level: str, message: str, source: str = ""):
        """Buffer an error/warning for batched analysis."""
        self._issue_buffer.append({
            "level": level,
            "message": message[:300],
            "source": source,
            "time": datetime.now().strftime("%H:%M:%S"),
        })
        # (Re-)start debounce timer
        if self._debounce_task and not self._debounce_task.done():
            self._debounce_task.cancel()
        self._debounce_task = asyncio.create_task(self._debounce_analysis())

    async def _debounce_analysis(self):
        """Wait for quiet period, then trigger analysis."""
        try:
            await asyncio.sleep(self._debounce_seconds)
        except asyncio.CancelledError:
            return
        if self._issue_buffer and not self._analyzing:
            await self._auto_analyze()

    async def _auto_analyze(self):
        """Analyze buffered issues and push a toast into Electron."""
        self._analyzing = True
        batch = self._issue_buffer.copy()
        self._issue_buffer.clear()

        errors = [i for i in batch if i["level"] == "error"]
        warnings = [i for i in batch if i["level"] == "warning"]

        # Build summary lines for the toast
        summary_lines = []
        if errors:
            summary_lines.append(f"{len(errors)} Error{'s' if len(errors)>1 else ''}")
            for e in errors[:5]:
                summary_lines.append(f"  [{e['time']}] {e['message'][:120]}")
        if warnings:
            summary_lines.append(f"{len(warnings)} Warning{'s' if len(warnings)>1 else ''}")
            for w in warnings[:3]:
                summary_lines.append(f"  [{w['time']}] {w['message'][:120]}")

        # Optional: let AutoGen produce a smarter diagnosis
        ai_summary = ""
        if self.autogen_agent:
            try:
                prompt = (
                    "Analyze these Electron errors/warnings. "
                    "Give a short diagnosis (max 3 sentences) and a concrete fix suggestion.\n\n"
                    + json.dumps(batch, indent=2)
                )
                result = await self.autogen_agent.on_messages(
                    [TextMessage(content=prompt, source="user")],
                    cancellation_token=CancellationToken(),
                )
                ai_summary = result.chat_message.content
            except Exception as e:
                ai_summary = f"AutoGen analysis failed: {e}"

        severity = "error" if errors else "warning"
        await self._show_toast_via_cdp(severity, summary_lines, ai_summary)
        self._analyzing = False

    async def _show_toast_via_cdp(
        self, severity: str, summary_lines: List[str], ai_analysis: str = ""
    ):
        """Inject a toast notification into Electron renderer via CDP (safe DOM API)."""
        if not self.cdp.ws:
            return

        self._toast_id += 1
        tid = self._toast_id

        border_color = "#ff4444" if severity == "error" else "#ffbb33"
        icon = "\u26d4" if severity == "error" else "\u26a0"
        title = "Error Detected" if severity == "error" else "Warning Detected"

        # JSON-encode strings so they're safe to embed in JS
        lines_json = json.dumps(summary_lines)
        ai_json = json.dumps(ai_analysis)

        js = f"""
        (function() {{
            // Container (reused across toasts)
            var container = document.getElementById('debug-toast-container');
            if (!container) {{
                container = document.createElement('div');
                container.id = 'debug-toast-container';
                container.style.cssText = 'position:fixed;top:12px;right:12px;z-index:99999;'
                    + 'display:flex;flex-direction:column;gap:8px;pointer-events:none;'
                    + 'max-height:80vh;overflow-y:auto;max-width:420px;';
                document.body.appendChild(container);
            }}

            // Toast card
            var toast = document.createElement('div');
            toast.id = 'debug-toast-{tid}';
            toast.style.cssText = 'pointer-events:auto;background:#1e1e2e;color:#e0e0e0;'
                + 'border:1px solid {border_color};border-left:4px solid {border_color};'
                + 'border-radius:8px;padding:12px 16px;font-family:monospace;font-size:13px;'
                + 'box-shadow:0 4px 24px rgba(0,0,0,0.6);opacity:0;'
                + 'transform:translateX(40px);transition:all 0.3s ease;max-width:420px;';

            // Header row
            var header = document.createElement('div');
            header.style.cssText = 'display:flex;justify-content:space-between;align-items:center;';
            var titleEl = document.createElement('span');
            titleEl.style.cssText = 'font-size:15px;font-weight:bold;';
            titleEl.textContent = {json.dumps(icon + ' ' + title)};
            var closeBtn = document.createElement('span');
            closeBtn.style.cssText = 'cursor:pointer;font-size:18px;opacity:0.6;padding:0 4px;';
            closeBtn.textContent = '\\u00d7';
            closeBtn.title = 'Dismiss';
            closeBtn.onclick = function() {{
                toast.style.opacity = '0';
                toast.style.transform = 'translateX(40px)';
                setTimeout(function() {{ toast.remove(); }}, 300);
            }};
            header.appendChild(titleEl);
            header.appendChild(closeBtn);
            toast.appendChild(header);

            // Summary lines
            var body = document.createElement('div');
            body.style.cssText = 'margin-top:8px;line-height:1.6;font-size:12px;';
            var lines = {lines_json};
            lines.forEach(function(line) {{
                var p = document.createElement('div');
                if (line.indexOf('Error') !== -1 || line.indexOf('Warning') !== -1) {{
                    p.style.fontWeight = 'bold';
                    p.style.marginTop = '4px';
                }}
                p.textContent = line;
                body.appendChild(p);
            }});
            toast.appendChild(body);

            // AI diagnosis block (optional)
            var aiText = {ai_json};
            if (aiText) {{
                var aiBox = document.createElement('div');
                aiBox.style.cssText = 'margin-top:8px;padding:8px;background:rgba(255,255,255,0.05);'
                    + 'border-radius:4px;font-size:12px;color:#ccc;'
                    + 'border-left:3px solid {border_color};white-space:pre-wrap;';
                var aiLabel = document.createElement('b');
                aiLabel.textContent = 'AI Diagnosis:';
                aiBox.appendChild(aiLabel);
                aiBox.appendChild(document.createElement('br'));
                var aiContent = document.createElement('span');
                aiContent.textContent = aiText;
                aiBox.appendChild(aiContent);
                toast.appendChild(aiBox);
            }}

            container.appendChild(toast);
            requestAnimationFrame(function() {{
                toast.style.opacity = '1';
                toast.style.transform = 'translateX(0)';
            }});

            // Auto-dismiss after 20s
            setTimeout(function() {{
                var el = document.getElementById('debug-toast-{tid}');
                if (el) {{
                    el.style.opacity = '0';
                    el.style.transform = 'translateX(40px)';
                    setTimeout(function() {{ el.remove(); }}, 300);
                }}
            }}, 20000);
        }})();
        """

        try:
            await self.cdp.send("Runtime.evaluate", {
                "expression": js,
                "silent": True,
                "returnByValue": False,
            })
        except Exception as e:
            print(f"{LEVEL_ANSI['ERROR']}[TOAST] Failed to inject: {e}{RST}")

    async def _on_console_api(self, params: Dict):
        """Handle console API calls."""
        msg_type = params.get("type", "log")
        args = params.get("args", [])

        # Extract message text
        messages = []
        for arg in args:
            if arg.get("type") == "string":
                messages.append(arg.get("value", ""))
            else:
                messages.append(str(arg.get("value", arg)))

        message = " ".join(messages)

        # ── Suppress noise ──
        if _should_suppress(message):
            return

        # ── Structured JSON logs (forwarded by main.js via console.log) ──
        if len(messages) >= 1:
            try:
                obj = json.loads(messages[0])

                # SpaceLogger JSON (__space_log)
                if obj.get("__space_log"):
                    _print_space_log(obj)
                    self.stats["console_logs"] += 1
                    self.logger.log(
                        f"space:{obj.get('s', 'system')}",
                        (obj.get("l", "INFO") or "INFO").lower(),
                        obj.get("m", ""),
                        obj,
                        silent=True,
                    )
                    if obj.get("l") in ("ERROR", "CRITICAL"):
                        self.stats["errors"] += 1
                        self._buffer_issue("error", obj.get("m", ""), f"space:{obj.get('s','')}")
                    elif obj.get("l") == "WARNING":
                        self.stats["warnings"] += 1
                        self._buffer_issue("warning", obj.get("m", ""), f"space:{obj.get('s','')}")
                    return

                # IPC trace (__ipc_log)
                if obj.get("__ipc_log"):
                    _print_ipc_log(obj)
                    self.stats["console_logs"] += 1
                    self.logger.log("ipc", "debug", f"{obj.get('type','?')}", obj, silent=True)
                    return

            except (json.JSONDecodeError, TypeError, ValueError):
                pass

        # ── Node.js service logs (GraphBuilder, Main, BrainManager etc.) ──
        node_space = _detect_node_service_space(message)
        if node_space:
            color = SPACE_ANSI.get(node_space, SPACE_ANSI["system"])
            tag = SPACE_TAGS.get(node_space, "[SYSTEM]").ljust(10)
            level_str = "ERROR" if msg_type == "error" else \
                        "WARNING" if msg_type in ("warning", "warn") else "INFO"
            level_color = LEVEL_ANSI.get(level_str, "")
            print(f"{color}{tag} {level_color}{level_str.ljust(5)}{RST} {color}{message}{RST}")
            self.stats["console_logs"] += 1
            self.logger.log(f"node:{node_space}", level_str.lower(), message, silent=True)
            if level_str == "ERROR":
                self.stats["errors"] += 1
                self._buffer_issue("error", message, f"node:{node_space}")
            elif level_str == "WARNING":
                self.stats["warnings"] += 1
                self._buffer_issue("warning", message, f"node:{node_space}")
            return

        # ── Fallback: everything else gets [SYSTEM] space coloring ──
        level_str = "ERROR" if msg_type in ("error",) else \
                    "WARNING" if msg_type in ("warning", "warn") else "INFO"
        color = SPACE_ANSI["system"]
        tag = SPACE_TAGS["system"].ljust(10)
        level_color = LEVEL_ANSI.get(level_str, "")
        print(f"{color}{tag} {level_color}{level_str.ljust(5)}{RST} {color}{message}{RST}")
        self.stats["console_logs"] += 1
        self.logger.log("console", level_str.lower(), message, silent=True)

        if level_str == "ERROR":
            self.stats["errors"] += 1
            self._buffer_issue("error", message, "console")
        elif level_str == "WARNING":
            self.stats["warnings"] += 1
            self._buffer_issue("warning", message, "console")

    async def _on_exception_thrown(self, params: Dict):
        """Handle runtime exceptions."""
        exception = params.get("exceptionDetails", {})
        text = exception.get("text", "Unknown exception")
        
        stack = exception.get("exception", {}).get("description", "")
        
        self.logger.log("exception", "error", text, {
            "stack": stack,
            "lineNumber": exception.get("lineNumber"),
            "columnNumber": exception.get("columnNumber"),
            "url": exception.get("url")
        })
        self.stats["errors"] += 1
        self._buffer_issue("error", f"{text}\n{stack[:200]}" if stack else text, "exception")
    
    async def _on_log_entry(self, params: Dict):
        """Handle log entries."""
        entry = params.get("entry", {})
        level = entry.get("level", "info")
        text = entry.get("text", "")
        source = entry.get("source", "")

        self.logger.log(f"log:{source}", level, text, entry)
        if level == "error":
            self.stats["errors"] += 1
            self._buffer_issue("error", text, f"log:{source}")
        elif level == "warning":
            self.stats["warnings"] += 1
            self._buffer_issue("warning", text, f"log:{source}")
    
    async def _on_network_request(self, params: Dict):
        """Handle network requests."""
        request = params.get("request", {})
        url = request.get("url", "")
        method = request.get("method", "GET")
        
        self.logger.log("network", "debug", f"{method} {url}", {
            "requestId": params.get("requestId"),
            "type": params.get("type")
        })
        self.stats["network_requests"] += 1
    
    async def _on_network_response(self, params: Dict):
        """Handle network responses."""
        response = params.get("response", {})
        url = response.get("url", "")
        status = response.get("status", 0)
        
        level = "info" if status < 400 else "error"
        self.logger.log("network", level, f"Response {status}: {url}", {
            "requestId": params.get("requestId"),
            "status": status,
            "statusText": response.get("statusText")
        })
    
    async def start(self):
        """Start the debug agent."""
        logger.debug("ElectronDebugAgent.start called")
        print("\n" + "="*60)
        print("Electron Debug Agent")
        print("="*60)
        
        # Connect to CDP
        connected = await self.cdp.connect()
        if not connected:
            print("\nFailed to connect to Electron.")
            print("Make sure Electron is running with:")
            print("  electron --remote-debugging-port=9222 electron-app")
            return False
        
        # Register event handlers
        self.cdp.on("Runtime.consoleAPICalled", self._on_console_api)
        self.cdp.on("Runtime.exceptionThrown", self._on_exception_thrown)
        self.cdp.on("Log.entryAdded", self._on_log_entry)
        
        if self.config.log_network:
            self.cdp.on("Network.requestWillBeSent", self._on_network_request)
            self.cdp.on("Network.responseReceived", self._on_network_response)
        
        # Enable CDP domains
        await self.cdp.enable_domains()
        
        self.running = True
        self.stats["start_time"] = datetime.now()
        
        print(f"\nDebug agent running. Logs: {self.logger.log_file}")
        print("Press Ctrl+C to stop.\n")
        
        return True
    
    async def stop(self):
        """Stop the debug agent."""
        logger.debug("ElectronDebugAgent.stop called")
        self.running = False
        await self.cdp.disconnect()
        self.logger.close()
        
        print("\n" + "="*60)
        print("Debug Agent Stopped")
        print("="*60)
        print(f"Total console logs: {self.stats['console_logs']}")
        print(f"Total errors: {self.stats['errors']}")
        print(f"Total warnings: {self.stats['warnings']}")
        print(f"Total network requests: {self.stats['network_requests']}")
        print(f"Log file: {self.logger.log_file}")
    
    async def run_forever(self):
        """Run until interrupted."""
        if not await self.start():
            return
        
        try:
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            await self.stop()
    
    async def analyze(self, query: str = "What issues are in the logs?") -> str:
        """Use AutoGen agent to analyze logs."""
        if not self.autogen_agent:
            return "AutoGen not available"
        
        # Create a simple chat
        result = await self.autogen_agent.on_messages(
            [TextMessage(content=query, source="user")],
            cancellation_token=CancellationToken(),
        )
        return result.chat_message.content


# ========================================================================
# MAIN
# ========================================================================

async def main():
    """Main entry point."""
    config = DebugConfig(
        log_console=True,
        log_network=True,
        log_errors=True
    )
    
    agent = ElectronDebugAgent(config)
    await agent.run_forever()


if __name__ == "__main__":
    asyncio.run(main())