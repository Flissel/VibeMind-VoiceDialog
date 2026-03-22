"""
System Status Monitor - Real-time visibility into VibeMind operations.

Tracks:
- Active operations (LLM calls, tool executions)
- Request queue depth
- Last N operations with timing
- Concurrent operation count
"""

import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import deque
import logging

logger = logging.getLogger(__name__)

_logger = logging.getLogger(__name__)


@dataclass
class ActiveOperation:
    """An operation currently in progress."""
    id: str
    operation_type: str  # "llm_call", "tool_exec", "rag_classify", etc.
    description: str
    started_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def elapsed_seconds(self) -> float:
        return time.time() - self.started_at

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.operation_type,
            "description": self.description,
            "elapsed_s": round(self.elapsed_seconds, 2),
            "started": datetime.fromtimestamp(self.started_at).strftime("%H:%M:%S"),
            "metadata": self.metadata,
        }


@dataclass
class CompletedOperation:
    """A completed operation."""
    id: str
    operation_type: str
    description: str
    duration_s: float
    success: bool
    completed_at: float = field(default_factory=time.time)
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.operation_type,
            "description": self.description,
            "duration_s": round(self.duration_s, 2),
            "success": self.success,
            "completed": datetime.fromtimestamp(self.completed_at).strftime("%H:%M:%S"),
            "error": self.error,
        }


class SystemStatusMonitor:
    """
    Singleton monitor for tracking system operations in real-time.

    Usage:
        from swarm.monitoring.system_status import get_status_monitor

        monitor = get_status_monitor()

        # Start tracking an operation
        op_id = monitor.start_operation("llm_call", "RAG classification for: 'Liste alle Bubbles'")

        # ... do work ...

        # Mark as complete
        monitor.complete_operation(op_id, success=True)

        # Get current status
        status = monitor.get_status()
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._active_ops: Dict[str, ActiveOperation] = {}
        self._completed_ops: deque = deque(maxlen=50)  # Last 50 operations
        self._op_counter = 0
        self._ops_lock = threading.Lock()

        # Counters
        self._total_operations = 0
        self._total_errors = 0
        self._start_time = time.time()

        self._initialized = True
        logger.info("[SystemStatus] Monitor initialized")

    def start_operation(
        self,
        operation_type: str,
        description: str,
        metadata: Dict[str, Any] = None
    ) -> str:
        """
        Start tracking a new operation.

        Args:
            operation_type: Type of operation (llm_call, tool_exec, rag_classify)
            description: Human-readable description
            metadata: Optional additional data

        Returns:
            Operation ID for later completion
        """
        with self._ops_lock:
            self._op_counter += 1
            op_id = f"op_{self._op_counter}_{int(time.time())}"

            op = ActiveOperation(
                id=op_id,
                operation_type=operation_type,
                description=description[:100],  # Truncate
                metadata=metadata or {},
            )
            self._active_ops[op_id] = op

        # Print status line
        self._print_status_line(f"[+] {operation_type}: {description[:50]}")

        return op_id

    def complete_operation(
        self,
        op_id: str,
        success: bool = True,
        error: str = None
    ):
        """Mark an operation as complete."""
        with self._ops_lock:
            op = self._active_ops.pop(op_id, None)
            if not op:
                return

            self._total_operations += 1
            if not success:
                self._total_errors += 1

            completed = CompletedOperation(
                id=op_id,
                operation_type=op.operation_type,
                description=op.description,
                duration_s=op.elapsed_seconds,
                success=success,
                error=error,
            )
            self._completed_ops.append(completed)

        # Print completion line
        status_char = "OK" if success else "ERR"
        self._print_status_line(f"[-] {op.operation_type}: {status_char} ({op.elapsed_seconds:.1f}s)")

    def _print_status_line(self, msg: str):
        """Log a status line with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        active_count = len(self._active_ops)
        prefix = f"[{timestamp}] [{active_count} active]"
        _logger.debug(f"{prefix} {msg}")

    def get_status(self) -> Dict[str, Any]:
        """Get current system status."""
        with self._ops_lock:
            active = [op.to_dict() for op in self._active_ops.values()]
            recent = [op.to_dict() for op in list(self._completed_ops)[-10:]]

        uptime = time.time() - self._start_time

        return {
            "uptime_s": round(uptime, 0),
            "total_operations": self._total_operations,
            "total_errors": self._total_errors,
            "active_count": len(active),
            "active_operations": active,
            "recent_completed": recent,
            "error_rate": round(self._total_errors / max(1, self._total_operations), 2),
        }

    def get_active_operations(self) -> List[Dict[str, Any]]:
        """Get list of currently active operations."""
        with self._ops_lock:
            return [op.to_dict() for op in self._active_ops.values()]

    def print_status_summary(self):
        """Log a human-readable status summary."""
        status = self.get_status()

        lines = [
            "=" * 50,
            "SYSTEM STATUS",
            "=" * 50,
            f"Uptime: {status['uptime_s']:.0f}s | Operations: {status['total_operations']} | Errors: {status['total_errors']}",
            "",
        ]

        if status['active_operations']:
            lines.append(f"ACTIVE ({status['active_count']}):")
            for op in status['active_operations']:
                lines.append(f"  [{op['elapsed_s']:.1f}s] {op['type']}: {op['description'][:40]}")
        else:
            lines.append("No active operations")

        lines.append("")
        lines.append("RECENT (last 5):")
        for op in status['recent_completed'][-5:]:
            status_char = "OK" if op['success'] else "ERR"
            lines.append(f"  [{op['duration_s']:.1f}s] {status_char} {op['type']}: {op['description'][:40]}")

        lines.append("=" * 50)

        _logger.debug("\n".join(lines))

    def check_stuck_operations(self, threshold_seconds: float = 15.0) -> List[Dict[str, Any]]:
        """Check for operations that have been running too long."""
        stuck = []
        with self._ops_lock:
            for op in self._active_ops.values():
                if op.elapsed_seconds > threshold_seconds:
                    stuck.append(op.to_dict())

        if stuck:
            _logger.debug(f"[WARNING] {len(stuck)} stuck operations (>{threshold_seconds}s):")
            for op in stuck:
                _logger.debug(f"  [{op['elapsed_s']:.0f}s] {op['type']}: {op['description'][:50]}")

        return stuck


# Singleton accessor
_monitor: Optional[SystemStatusMonitor] = None


def get_status_monitor() -> SystemStatusMonitor:
    """Get the singleton SystemStatusMonitor."""
    global _monitor
    if _monitor is None:
        _monitor = SystemStatusMonitor()
    return _monitor


__all__ = [
    "SystemStatusMonitor",
    "get_status_monitor",
    "ActiveOperation",
    "CompletedOperation",
]
