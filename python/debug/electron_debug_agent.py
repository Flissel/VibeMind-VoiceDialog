#!/usr/bin/env python3
"""
Electron Debug Agent - AutoGen 0.4
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

# AutoGen 0.4 imports
try:
    from autogen_agentchat.agents import AssistantAgent
    from autogen_agentchat.messages import TextMessage
    from autogen_agentchat.task import Console, TextMentionTermination
    from autogen_agentchat.teams import RoundRobinGroupChat
    from autogen_core.components.tools import FunctionTool
    from autogen_ext.models import OpenAIChatCompletionClient
    HAS_AUTOGEN = True
except ImportError:
    HAS_AUTOGEN = False
    print("WARNING: AutoGen 0.4 not installed. Install with: pip install autogen-agentchat")

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
    
    def log(self, category: str, level: str, message: str, data: Dict = None):
        """Write a log entry."""
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
        
        # Also print to console
        level_colors = {
            "error": "\033[91m",
            "warning": "\033[93m",
            "info": "\033[94m",
            "debug": "\033[90m"
        }
        reset = "\033[0m"
        color = level_colors.get(level, "")
        print(f"{color}[{category}] {level.upper()}: {message}{reset}")
        
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
# DEBUG AGENT (AutoGen 0.4)
# ========================================================================

class ElectronDebugAgent:
    """
    AutoGen 0.4 Agent that monitors Electron app via CDP.
    Creates continuous debug logs and can analyze issues.
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
        
        # Create agent
        model_client = OpenAIChatCompletionClient(
            model="gpt-4o-mini",
            api_key=os.getenv("OPENAI_API_KEY", "")
        )
        
        self.autogen_agent = AssistantAgent(
            name="ElectronDebugger",
            model_client=model_client,
            tools=[analyze_tool, stats_tool],
            system_message="""You are an Electron debugging assistant.
You monitor application logs and help identify issues.
When errors occur, analyze them and suggest fixes."""
        )

    
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
        
        # Determine level from console type
        level_map = {
            "log": "info",
            "info": "info",
            "warning": "warning",
            "warn": "warning",
            "error": "error",
            "debug": "debug"
        }
        level = level_map.get(msg_type, "info")
        
        # Parse IPC messages for better categorization
        category = "console"
        parsed_data = {"type": msg_type}
        
        # Check if message is from Python IPC (JSON format)
        if "[Python IPC]:" in message:
            try:
                json_str = message.split("[Python IPC]:", 1)[1].strip()
                ipc_data = json.loads(json_str)
                
                # Determine category and level from IPC message type
                ipc_type = ipc_data.get("type", "unknown")
                category = f"ipc:{ipc_type}"
                parsed_data = ipc_data
                
                # Set error level for error types
                if "error" in ipc_type.lower() or ipc_data.get("error"):
                    level = "error"
                    message = ipc_data.get("error", message)
                elif "warning" in ipc_type.lower():
                    level = "warning"
                else:
                    message = f"{ipc_type}: {json.dumps(ipc_data)}"
                    
            except (json.JSONDecodeError, IndexError):
                pass
        
        # Check for Python ERROR prefix
        elif "[Python ERROR]:" in message:
            level = "error"
            category = "ipc:error"
            message = message.split("[Python ERROR]:", 1)[1].strip()
        
        # Check for Python stderr
        elif "[Python stderr]:" in message:
            category = "stderr"
            # Check if it's a warning or error
            if "warning" in message.lower():
                level = "warning"
            elif "error" in message.lower() or "traceback" in message.lower():
                level = "error"
        
        self.logger.log(category, level, message, parsed_data)
        self.stats["console_logs"] += 1
        
        if level == "error":
            self.stats["errors"] += 1
        elif level == "warning":
            self.stats["warnings"] += 1
    
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
    
    async def _on_log_entry(self, params: Dict):
        """Handle log entries."""
        entry = params.get("entry", {})
        level = entry.get("level", "info")
        text = entry.get("text", "")
        source = entry.get("source", "")
        
        self.logger.log(f"log:{source}", level, text, entry)
    
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
            cancellation_token=None
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