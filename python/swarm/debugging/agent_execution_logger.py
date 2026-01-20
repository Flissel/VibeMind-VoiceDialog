"""
Agent Execution Logger - Persistent logging for backend agent activities

Logs all agent events (received, started, completed, error) to JSONL files
for analysis by the Self-Debugging System.
"""

import os
import json
import logging
from typing import Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AgentExecutionLog:
    """A single agent execution log entry."""
    timestamp: str
    session_id: Optional[str]
    agent_name: str
    event_type: str  # "received", "started", "completed", "error"
    job_id: str
    original_event: str  # The event type that triggered this (e.g., "bubble.create")
    tool_name: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    result: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in asdict(self).items() if v is not None}


class AgentExecutionLogger:
    """
    Logs backend agent execution to JSONL files.

    Log files are stored in: logs/agents/{date}.jsonl
    """

    def __init__(self, logs_dir: str = None):
        self.logs_dir = logs_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "logs", "agents"
        )
        Path(self.logs_dir).mkdir(parents=True, exist_ok=True)

        # Track start times for duration calculation
        self._start_times: Dict[str, float] = {}

        # Current session ID (set by VoiceBridgeV2)
        self._session_id: Optional[str] = None

    def set_session_id(self, session_id: str):
        """Set the current session ID for all logs."""
        self._session_id = session_id

    def _get_log_file(self) -> str:
        """Get today's log file path."""
        date_str = datetime.utcnow().strftime("%Y%m%d")
        return os.path.join(self.logs_dir, f"agent_execution_{date_str}.jsonl")

    def _write_log(self, log: AgentExecutionLog):
        """Write a log entry to the JSONL file."""
        try:
            log_path = self._get_log_file()
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(log.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning(f"[AgentExecutionLogger] Failed to write log: {e}")

    def log_event_received(
        self,
        agent_name: str,
        job_id: str,
        event_type: str,
        payload: Dict[str, Any]
    ):
        """Log when an agent receives an event from Redis."""
        import time
        self._start_times[job_id] = time.time()

        log = AgentExecutionLog(
            timestamp=datetime.utcnow().isoformat(),
            session_id=self._session_id,
            agent_name=agent_name,
            event_type="received",
            job_id=job_id,
            original_event=event_type,
            params=payload,
        )
        self._write_log(log)
        logger.debug(f"[AgentLog] {agent_name} received {event_type} (job={job_id})")

    def log_tool_started(
        self,
        agent_name: str,
        job_id: str,
        original_event: str,
        tool_name: str,
        params: Dict[str, Any]
    ):
        """Log when an agent starts executing a tool."""
        log = AgentExecutionLog(
            timestamp=datetime.utcnow().isoformat(),
            session_id=self._session_id,
            agent_name=agent_name,
            event_type="started",
            job_id=job_id,
            original_event=original_event,
            tool_name=tool_name,
            params=params,
        )
        self._write_log(log)
        logger.debug(f"[AgentLog] {agent_name} started {tool_name} (job={job_id})")

    def log_tool_completed(
        self,
        agent_name: str,
        job_id: str,
        original_event: str,
        tool_name: str,
        result: Any
    ):
        """Log when a tool completes successfully."""
        import time

        # Calculate duration
        duration_ms = None
        if job_id in self._start_times:
            duration_ms = (time.time() - self._start_times.pop(job_id)) * 1000

        # Truncate result if too long
        result_str = str(result)
        if len(result_str) > 500:
            result_str = result_str[:500] + "..."

        log = AgentExecutionLog(
            timestamp=datetime.utcnow().isoformat(),
            session_id=self._session_id,
            agent_name=agent_name,
            event_type="completed",
            job_id=job_id,
            original_event=original_event,
            tool_name=tool_name,
            result=result_str,
            duration_ms=duration_ms,
        )
        self._write_log(log)
        logger.info(f"[AgentLog] {agent_name} completed {tool_name} in {duration_ms:.0f}ms (job={job_id})")

    def log_tool_error(
        self,
        agent_name: str,
        job_id: str,
        original_event: str,
        tool_name: Optional[str],
        error: str
    ):
        """Log when a tool fails."""
        import time

        # Calculate duration
        duration_ms = None
        if job_id in self._start_times:
            duration_ms = (time.time() - self._start_times.pop(job_id)) * 1000

        log = AgentExecutionLog(
            timestamp=datetime.utcnow().isoformat(),
            session_id=self._session_id,
            agent_name=agent_name,
            event_type="error",
            job_id=job_id,
            original_event=original_event,
            tool_name=tool_name,
            error=error,
            duration_ms=duration_ms,
        )
        self._write_log(log)
        logger.error(f"[AgentLog] {agent_name} ERROR in {tool_name}: {error} (job={job_id})")

    def get_recent_logs(self, limit: int = 100) -> list:
        """Get the most recent log entries."""
        logs = []
        log_path = self._get_log_file()

        if not os.path.exists(log_path):
            return logs

        try:
            with open(log_path, "r", encoding="utf-8") as f:
                for line in f:
                    try:
                        logs.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"[AgentExecutionLogger] Failed to read logs: {e}")

        return logs[-limit:]

    def get_session_logs(self, session_id: str) -> list:
        """Get all logs for a specific session."""
        all_logs = self.get_recent_logs(limit=1000)
        return [log for log in all_logs if log.get("session_id") == session_id]


# Singleton instance
_logger: Optional[AgentExecutionLogger] = None


def get_agent_execution_logger() -> AgentExecutionLogger:
    """Get or create the singleton AgentExecutionLogger."""
    global _logger
    if _logger is None:
        _logger = AgentExecutionLogger()
    return _logger


__all__ = [
    "AgentExecutionLogger",
    "AgentExecutionLog",
    "get_agent_execution_logger",
]
