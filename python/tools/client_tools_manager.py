"""
Client Tools Manager
Manages registration and routing of ElevenLabs client tools to specialized agents
"""

import json
import time
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
from dataclasses import dataclass, field
from pathlib import Path
from elevenlabs.conversational_ai.conversation import ClientTools


@dataclass
class ToolCallRecord:
    """Record of a single tool call."""
    tool_name: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_ms: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "params": self.params,
            "result": self.result,
            "error": self.error,
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_ms": self.duration_ms
        }


class ToolCallObserver:
    """
    Observer that receives notifications about all tool calls.
    Subclass this to implement custom logging/monitoring.
    """
    
    def on_tool_call_start(self, tool_name: str, params: Dict[str, Any]) -> None:
        """Called when a tool call starts."""
        pass
    
    def on_tool_call_success(self, tool_name: str, params: Dict[str, Any], 
                             result: Dict[str, Any], duration_ms: float) -> None:
        """Called when a tool call completes successfully."""
        pass
    
    def on_tool_call_error(self, tool_name: str, params: Dict[str, Any], 
                           error: str, duration_ms: float) -> None:
        """Called when a tool call fails."""
        pass


class ConsoleToolObserver(ToolCallObserver):
    """Observer that logs all tool calls to console with colors (cross-platform safe)."""
    
    # Detect if Windows console can handle Unicode
    @staticmethod
    def _supports_unicode() -> bool:
        """Check if the console supports Unicode output."""
        import sys
        import os
        
        # Force ASCII on Windows unless explicitly running in UTF-8 mode
        if sys.platform == 'win32':
            # Check if running in Windows Terminal or VS Code terminal
            if os.environ.get('WT_SESSION') or os.environ.get('TERM_PROGRAM') == 'vscode':
                return True
            # Check console encoding
            try:
                return sys.stdout.encoding.lower() in ('utf-8', 'utf8')
            except:
                return False
        return True
    
    # ASCII-safe symbols for cross-platform compatibility
    SYMBOLS_ASCII = {
        "start": "->",
        "success": "OK",
        "error": "X",
    }
    
    SYMBOLS_UNICODE = {
        "start": "→",
        "success": "✓",
        "error": "✗",
    }
    
    COLORS = {
        "start": "\033[94m",    # Blue
        "success": "\033[92m",  # Green
        "error": "\033[91m",    # Red
        "reset": "\033[0m",
        "gray": "\033[90m",
    }
    
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.use_unicode = self._supports_unicode()
        self.symbols = self.SYMBOLS_UNICODE if self.use_unicode else self.SYMBOLS_ASCII
    
    def _safe_print(self, text: str) -> None:
        """Print text safely, handling encoding errors."""
        try:
            print(text)
        except UnicodeEncodeError:
            # Fallback: replace problematic characters
            safe_text = text.encode('ascii', errors='replace').decode('ascii')
            print(safe_text)
    
    def on_tool_call_start(self, tool_name: str, params: Dict[str, Any]) -> None:
        c = self.COLORS
        sym = self.symbols["start"]
        self._safe_print(f"{c['start']}[TOOL] {sym} {tool_name}{c['reset']}")
        if self.verbose and params:
            params_str = json.dumps(params, default=str)[:200]
            self._safe_print(f"{c['gray']}  params: {params_str}{c['reset']}")
    
    def on_tool_call_success(self, tool_name: str, params: Dict[str, Any], 
                             result: Dict[str, Any], duration_ms: float) -> None:
        c = self.COLORS
        sym = self.symbols["success"]
        self._safe_print(f"{c['success']}[TOOL] {sym} {tool_name} ({duration_ms:.1f}ms){c['reset']}")
        if self.verbose:
            result_str = json.dumps(result, default=str)[:300]
            self._safe_print(f"{c['gray']}  result: {result_str}{c['reset']}")
    
    def on_tool_call_error(self, tool_name: str, params: Dict[str, Any], 
                           error: str, duration_ms: float) -> None:
        c = self.COLORS
        sym = self.symbols["error"]
        self._safe_print(f"{c['error']}[TOOL] {sym} {tool_name} ({duration_ms:.1f}ms){c['reset']}")
        self._safe_print(f"{c['error']}  error: {error}{c['reset']}")

class FileToolObserver(ToolCallObserver):
    """Observer that writes all tool calls to a JSONL log file."""
    
    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path("logs/tool_calls")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"tool_calls_{timestamp}.jsonl"
        print(f"[ToolObserver] Logging to: {self.log_file}")
    
    def _write_entry(self, entry: Dict[str, Any]) -> None:
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, default=str) + "\n")
    
    def on_tool_call_start(self, tool_name: str, params: Dict[str, Any]) -> None:
        self._write_entry({
            "event": "start",
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "params": params
        })
    
    def on_tool_call_success(self, tool_name: str, params: Dict[str, Any], 
                             result: Dict[str, Any], duration_ms: float) -> None:
        self._write_entry({
            "event": "success",
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "params": params,
            "result": result,
            "duration_ms": duration_ms
        })
    
    def on_tool_call_error(self, tool_name: str, params: Dict[str, Any], 
                           error: str, duration_ms: float) -> None:
        self._write_entry({
            "event": "error",
            "timestamp": datetime.now().isoformat(),
            "tool_name": tool_name,
            "params": params,
            "error": error,
            "duration_ms": duration_ms
        })


class ClientToolsManager:
    """
    Manages the registration and routing of client tools to specialized agents.

    This class acts as a bridge between the ElevenLabs Conversation SDK and
    the specialized agent system. When the ElevenLabs agent calls a client tool,
    this manager routes it to the appropriate Python agent for execution.
    """

    def __init__(self, enable_console_logging: bool = True, enable_file_logging: bool = True):
        """Initialize the Client Tools Manager with optional observers."""
        self.client_tools = ClientTools()
        self.agents: Dict[str, Any] = {}
        self.tool_registry: Dict[str, str] = {}
        self.tool_history: List[ToolCallRecord] = []
        self.observers: List[ToolCallObserver] = []
        
        # Add default observers
        if enable_console_logging:
            self.add_observer(ConsoleToolObserver(verbose=True))
        if enable_file_logging:
            self.add_observer(FileToolObserver())
        
        print("[ClientToolsManager] Initialized")

    def add_observer(self, observer: ToolCallObserver) -> None:
        """Add a tool call observer."""
        self.observers.append(observer)
        print(f"[ClientToolsManager] Added observer: {type(observer).__name__}")
    
    def remove_observer(self, observer: ToolCallObserver) -> None:
        """Remove a tool call observer."""
        if observer in self.observers:
            self.observers.remove(observer)

    def _notify_start(self, tool_name: str, params: Dict[str, Any]) -> None:
        """Notify all observers that a tool call is starting."""
        for observer in self.observers:
            try:
                observer.on_tool_call_start(tool_name, params)
            except Exception as e:
                print(f"[ClientToolsManager] Observer error: {e}")

    def _notify_success(self, tool_name: str, params: Dict[str, Any], 
                        result: Dict[str, Any], duration_ms: float) -> None:
        """Notify all observers that a tool call succeeded."""
        for observer in self.observers:
            try:
                observer.on_tool_call_success(tool_name, params, result, duration_ms)
            except Exception as e:
                print(f"[ClientToolsManager] Observer error: {e}")

    def _notify_error(self, tool_name: str, params: Dict[str, Any], 
                      error: str, duration_ms: float) -> None:
        """Notify all observers that a tool call failed."""
        for observer in self.observers:
            try:
                observer.on_tool_call_error(tool_name, params, error, duration_ms)
            except Exception as e:
                print(f"[ClientToolsManager] Observer error: {e}")

    def register_agent(self, agent_name: str, agent_instance: Any) -> None:
        """
        Register a specialized agent

        Args:
            agent_name: Unique name for the agent (e.g., "research", "code")
            agent_instance: Instance of the agent class
        """
        self.agents[agent_name] = agent_instance
        print(f"[ClientToolsManager] Registered agent: {agent_name} ({type(agent_instance).__name__})")

    def register_tool(self, tool_name: str, agent_name: str, is_async: bool = False) -> None:
        """
        Register a client tool that maps to an agent

        Args:
            tool_name: Name of the tool (must match ElevenLabs dashboard config)
            agent_name: Name of the agent to route this tool to
            is_async: Whether the tool function is async

        Raises:
            ValueError: If agent_name is not registered
        """
        if agent_name not in self.agents:
            raise ValueError(f"Agent '{agent_name}' not registered. Register it first using register_agent()")

        # Create a tool function that routes to the agent
        tool_func = self._create_tool_function(tool_name, agent_name)

        # Register with ElevenLabs ClientTools
        self.client_tools.register(tool_name, tool_func, is_async=is_async)

        # Store in our registry
        self.tool_registry[tool_name] = agent_name

        print(f"[ClientToolsManager] Registered tool: '{tool_name}' -> {agent_name}")

    def _create_tool_function(self, tool_name: str, agent_name: str) -> Callable:
        """
        Create a tool function that routes calls to an agent

        Args:
            tool_name: Name of the tool
            agent_name: Name of the agent to route to

        Returns:
            Callable function that executes the agent
        """
        def tool_function(params: Dict[str, Any]) -> Dict[str, Any]:
            """
            Tool function executed when ElevenLabs agent calls this tool

            Args:
                params: Parameters from the tool call

            Returns:
                Results dictionary to send back to the agent
            """
            # Create record and notify start
            record = ToolCallRecord(tool_name=tool_name, params=params)
            self._notify_start(tool_name, params)
            
            agent = self.agents.get(agent_name)
            if not agent:
                error_msg = f"Agent '{agent_name}' not found for tool '{tool_name}'"
                record.error = error_msg
                record.end_time = datetime.now()
                record.duration_ms = (record.end_time - record.start_time).total_seconds() * 1000
                self.tool_history.append(record)
                self._notify_error(tool_name, params, error_msg, record.duration_ms)
                return {
                    "status": "error",
                    "error": error_msg
                }

            try:
                # Execute the agent
                result = agent.execute(params)
                
                # Record success
                record.result = result
                record.end_time = datetime.now()
                record.duration_ms = (record.end_time - record.start_time).total_seconds() * 1000
                self.tool_history.append(record)
                self._notify_success(tool_name, params, result, record.duration_ms)
                
                return result

            except Exception as e:
                error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                record.error = error_msg
                record.end_time = datetime.now()
                record.duration_ms = (record.end_time - record.start_time).total_seconds() * 1000
                self.tool_history.append(record)
                self._notify_error(tool_name, params, error_msg, record.duration_ms)
                
                return {
                    "status": "error",
                    "error": error_msg,
                    "exception_type": type(e).__name__
                }

        return tool_function

    def get_client_tools(self) -> ClientTools:
        """
        Get the ClientTools instance for use in Conversation

        Returns:
            ClientTools instance with all registered tools
        """
        return self.client_tools

    def register_with_observer(self, tool_name: str, tool_func: Callable, is_async: bool = False) -> None:
        """
        Register a tool function directly with observer logging.
        
        This wraps the function to add logging without needing a full agent.
        Use this when you have standalone tool functions.
        
        Args:
            tool_name: Name of the tool
            tool_func: Function to call (params -> result)
            is_async: Whether the function is async
        """
        def wrapped_tool(params: Dict[str, Any]) -> Any:
            """Wrapped tool with observer logging."""
            # Create record and notify start
            record = ToolCallRecord(tool_name=tool_name, params=params)
            self._notify_start(tool_name, params)
            
            try:
                # Execute the actual tool
                result = tool_func(params)
                
                # Normalize result to dict for logging
                result_dict = result if isinstance(result, dict) else {"result": str(result)}
                
                # Record success
                record.result = result_dict
                record.end_time = datetime.now()
                record.duration_ms = (record.end_time - record.start_time).total_seconds() * 1000
                self.tool_history.append(record)
                self._notify_success(tool_name, params, result_dict, record.duration_ms)
                
                return result
                
            except Exception as e:
                error_msg = f"Error in tool '{tool_name}': {str(e)}"
                record.error = error_msg
                record.end_time = datetime.now()
                record.duration_ms = (record.end_time - record.start_time).total_seconds() * 1000
                self.tool_history.append(record)
                self._notify_error(tool_name, params, error_msg, record.duration_ms)
                
                # Return error result instead of raising
                return {"status": "error", "error": error_msg}
        
        # Register the wrapped function with ElevenLabs ClientTools
        self.client_tools.register(tool_name, wrapped_tool, is_async=is_async)
        self.tool_registry[tool_name] = f"direct:{tool_name}"
        
        print(f"[ClientToolsManager] Registered tool with observer: '{tool_name}'")

    def list_registered_tools(self) -> Dict[str, str]:
        """
        Get a dictionary of all registered tools and their agents

        Returns:
            Dictionary mapping tool names to agent names
        """
        return dict(self.tool_registry)
    
    def get_tool_history(self, last_n: int = None) -> List[ToolCallRecord]:
        """
        Get the history of tool calls.
        
        Args:
            last_n: Return only the last N records (None for all)
            
        Returns:
            List of ToolCallRecord objects
        """
        if last_n:
            return self.tool_history[-last_n:]
        return self.tool_history
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about tool calls."""
        total = len(self.tool_history)
        errors = sum(1 for r in self.tool_history if r.error)
        successes = total - errors
        
        # Per-tool stats
        tool_stats = {}
        for record in self.tool_history:
            if record.tool_name not in tool_stats:
                tool_stats[record.tool_name] = {"calls": 0, "errors": 0, "total_ms": 0}
            tool_stats[record.tool_name]["calls"] += 1
            if record.error:
                tool_stats[record.tool_name]["errors"] += 1
            tool_stats[record.tool_name]["total_ms"] += record.duration_ms
        
        return {
            "total_calls": total,
            "successes": successes,
            "errors": errors,
            "error_rate": errors / total if total > 0 else 0,
            "per_tool": tool_stats
        }

    def __str__(self) -> str:
        return f"ClientToolsManager(agents={len(self.agents)}, tools={len(self.tool_registry)}, history={len(self.tool_history)})"
