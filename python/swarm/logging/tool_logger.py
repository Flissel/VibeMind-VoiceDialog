"""
Tool execution logging for VibeMind.

Logs each tool execution to a JSONL file for analysis.
Tracks latency, success/failure, and parameters.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class ToolLogger:
    """
    Structured JSON logging for tool execution.

    Writes one JSON object per line (JSONL format) to daily log files.
    """

    def __init__(self, log_dir: str = "logs/tools"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self._current_date = None
        self._current_file = None
        logger.info(f"ToolLogger initialized, writing to {self.log_dir}")

    def _get_log_file(self) -> Path:
        """Get current log file path, rotating daily."""
        today = datetime.now().strftime("%Y-%m-%d")
        if self._current_date != today:
            self._current_date = today
            self._current_file = self.log_dir / f"tools_{today}.jsonl"
        return self._current_file

    def log_execution(
        self,
        tool_name: str,
        params: Dict[str, Any],
        result: Optional[str],
        latency_ms: float,
        success: bool,
        source_event: Optional[str] = None,
        error: Optional[str] = None
    ):
        """
        Log a single tool execution.

        Args:
            tool_name: Name of the tool/event that was executed
            params: Parameters passed to the tool
            result: Result string from the tool (truncated to 500 chars)
            latency_ms: Time taken for execution in milliseconds
            success: Whether the execution succeeded
            source_event: Source event type that triggered this tool
            error: Error message if execution failed
        """
        # Truncate result to avoid huge log files
        result_truncated = None
        if result:
            result_truncated = result[:500] if len(result) > 500 else result

        # Sanitize params (remove sensitive data, truncate large values)
        safe_params = {}
        for key, value in (params or {}).items():
            if isinstance(value, str) and len(value) > 200:
                safe_params[key] = value[:200] + "..."
            else:
                safe_params[key] = value

        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "tool_name": tool_name,
            "params": safe_params,
            "result": result_truncated,
            "metrics": {
                "latency_ms": round(latency_ms, 2),
                "success": success
            },
            "source_event": source_event,
            "error": error
        }

        # Write to file
        try:
            log_file = self._get_log_file()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Failed to write tool log: {e}")

    def log_error(
        self,
        tool_name: str,
        params: Dict[str, Any],
        error: str,
        latency_ms: float
    ):
        """Log a tool execution error."""
        self.log_execution(
            tool_name=tool_name,
            params=params,
            result=None,
            latency_ms=latency_ms,
            success=False,
            error=error
        )


# Singleton instance
_tool_logger: Optional[ToolLogger] = None


def get_tool_logger() -> ToolLogger:
    """Get or create ToolLogger singleton."""
    global _tool_logger
    if _tool_logger is None:
        _tool_logger = ToolLogger()
    return _tool_logger


__all__ = ["ToolLogger", "get_tool_logger"]
