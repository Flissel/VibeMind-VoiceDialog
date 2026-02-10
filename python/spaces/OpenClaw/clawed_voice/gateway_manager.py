"""
OpenClaw Gateway Process Manager

Handles starting, stopping, and monitoring the OpenClaw Gateway process.
Supports on-demand startup and automatic shutdown after idle timeout.
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path
from typing import Optional
from enum import Enum

try:
    import psutil
    _HAS_PSUTIL = True
except ImportError:
    _HAS_PSUTIL = False

from .config import get_config

logger = logging.getLogger(__name__)


# Lock file location (same as OpenClaw uses)
LOCK_DIR = Path("/tmp/openclaw") if os.name != "nt" else Path("C:/tmp/openclaw")


def _find_lock_files() -> list[Path]:
    """Find all gateway lock files."""
    if not LOCK_DIR.exists():
        return []
    return list(LOCK_DIR.glob("gateway.*.lock"))


def _read_lock_file(lock_path: Path) -> Optional[dict]:
    """Read and parse a lock file."""
    try:
        content = lock_path.read_text()
        return json.loads(content)
    except (json.JSONDecodeError, IOError):
        return None


def _is_gateway_process(pid: int) -> bool:
    """Check if a PID is actually an OpenClaw gateway process."""
    if not _HAS_PSUTIL:
        # Without psutil, we can't verify - assume it might be valid
        return True

    try:
        proc = psutil.Process(pid)
        name = proc.name().lower()
        cmdline = " ".join(proc.cmdline()).lower()

        # Check if it's a node process running openclaw/clawdbot gateway
        if "node" in name:
            if "openclaw" in cmdline or "clawdbot" in cmdline:
                if "gateway" in cmdline:
                    return True

        return False
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return False


def cleanup_stale_locks() -> int:
    """
    Find and remove stale gateway lock files.

    A lock is considered stale if:
    - The PID doesn't exist
    - The PID exists but isn't an OpenClaw gateway process

    Returns:
        Number of stale locks removed
    """
    removed = 0

    for lock_path in _find_lock_files():
        lock_data = _read_lock_file(lock_path)

        if lock_data is None:
            # Can't read lock file - remove it
            logger.warning(f"Removing unreadable lock file: {lock_path}")
            try:
                lock_path.unlink()
                removed += 1
            except IOError as e:
                logger.error(f"Failed to remove lock file: {e}")
            continue

        pid = lock_data.get("pid")
        if pid is None:
            # No PID in lock file - remove it
            logger.warning(f"Removing lock file without PID: {lock_path}")
            try:
                lock_path.unlink()
                removed += 1
            except IOError as e:
                logger.error(f"Failed to remove lock file: {e}")
            continue

        # Check if PID is actually a gateway process
        if not _is_gateway_process(pid):
            logger.warning(
                f"Removing stale lock file: {lock_path} "
                f"(PID {pid} is not a gateway process)"
            )
            try:
                lock_path.unlink()
                removed += 1
            except IOError as e:
                logger.error(f"Failed to remove lock file: {e}")

    return removed


class GatewayState(str, Enum):
    """Gateway process state."""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


class GatewayManager:
    """
    Manages OpenClaw Gateway process lifecycle.

    Features:
    - Start gateway on-demand
    - Health checking and readiness waiting
    - Auto-shutdown after idle timeout
    - Process cleanup on exit
    """

    def __init__(
        self,
        openclaw_path: Optional[str] = None,
        port: Optional[int] = None,
        idle_timeout: Optional[int] = None,
    ):
        config = get_config()
        self.openclaw_path = openclaw_path or config.openclaw_path
        self.port = port or config.gateway_port
        self.idle_timeout = idle_timeout or config.idle_timeout_seconds

        self._process: Optional[subprocess.Popen] = None
        self._state = GatewayState.STOPPED
        self._last_activity = time.time()
        self._idle_task: Optional[asyncio.Task] = None
        self._started_by_us = False

    @property
    def state(self) -> GatewayState:
        """Current gateway state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if gateway is running (started by us or externally)."""
        # First check our process
        if self._process is not None:
            if self._process.poll() is None:
                return True
            else:
                # Process died
                self._process = None
                self._state = GatewayState.STOPPED
                self._started_by_us = False

        # Check if running externally (by port)
        return self._check_port_in_use()

    def _check_port_in_use(self) -> bool:
        """Check if gateway port is in use."""
        import socket
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.settimeout(1)
                s.connect(("127.0.0.1", self.port))
                return True
            except (socket.timeout, ConnectionRefusedError, OSError):
                return False

    async def start(self, wait_ready: bool = True, timeout: float = 30.0) -> bool:
        """
        Start the OpenClaw Gateway if not running.

        Args:
            wait_ready: Wait for gateway to accept connections
            timeout: Timeout for readiness check

        Returns:
            True if gateway is running (started or already running)
        """
        # Already running?
        if self.is_running:
            logger.info("Gateway already running")
            self._touch_activity()
            return True

        # Clean up stale lock files before starting
        stale_removed = cleanup_stale_locks()
        if stale_removed > 0:
            logger.info(f"Cleaned up {stale_removed} stale lock file(s)")

        self._state = GatewayState.STARTING
        logger.info(f"Starting OpenClaw Gateway on port {self.port}...")

        try:
            # Build command
            cmd = [self.openclaw_path, "gateway", "--port", str(self.port)]

            # Start process
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if hasattr(subprocess, 'CREATE_NEW_PROCESS_GROUP') else 0,
            )
            self._started_by_us = True

            logger.info(f"Gateway process started (PID: {self._process.pid})")

            if wait_ready:
                ready = await self._wait_ready(timeout)
                if not ready:
                    logger.error("Gateway failed to become ready")
                    await self.stop()
                    return False

            self._state = GatewayState.RUNNING
            self._touch_activity()

            # Start idle monitor
            self._start_idle_monitor()

            logger.info("Gateway is ready")
            return True

        except FileNotFoundError:
            logger.error(f"OpenClaw not found at: {self.openclaw_path}")
            self._state = GatewayState.ERROR
            return False
        except Exception as e:
            logger.error(f"Failed to start gateway: {e}")
            self._state = GatewayState.ERROR
            return False

    async def _wait_ready(self, timeout: float) -> bool:
        """Wait for gateway to accept connections."""
        start = time.time()
        check_interval = 0.5

        while time.time() - start < timeout:
            if self._check_port_in_use():
                # Additional check: try WebSocket handshake
                if await self._check_ws_ready():
                    return True

            # Check if process died
            if self._process and self._process.poll() is not None:
                stderr = self._process.stderr.read().decode() if self._process.stderr else ""
                logger.error(f"Gateway process died: {stderr}")
                return False

            await asyncio.sleep(check_interval)

        return False

    async def _check_ws_ready(self) -> bool:
        """Check if WebSocket endpoint is ready."""
        try:
            import websockets
            config = get_config()
            async with asyncio.timeout(2):
                ws = await websockets.connect(config.gateway_url)
                await ws.close()
                return True
        except Exception:
            return False

    async def stop(self, force: bool = False) -> bool:
        """
        Stop the OpenClaw Gateway.

        Args:
            force: Force kill without graceful shutdown

        Returns:
            True if stopped successfully
        """
        # Cancel idle monitor
        if self._idle_task:
            self._idle_task.cancel()
            self._idle_task = None

        # Only stop if we started it
        if not self._started_by_us:
            logger.info("Gateway not started by us, not stopping")
            return True

        if self._process is None:
            self._state = GatewayState.STOPPED
            return True

        self._state = GatewayState.STOPPING
        logger.info("Stopping OpenClaw Gateway...")

        try:
            if force:
                self._process.kill()
            else:
                # Try graceful termination
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    logger.warning("Graceful shutdown timed out, forcing...")
                    self._process.kill()
                    self._process.wait(timeout=5)

            self._process = None
            self._state = GatewayState.STOPPED
            self._started_by_us = False
            logger.info("Gateway stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop gateway: {e}")
            self._state = GatewayState.ERROR
            return False

    def touch_activity(self):
        """Record activity to reset idle timer."""
        self._touch_activity()

    def _touch_activity(self):
        """Internal: record activity timestamp."""
        self._last_activity = time.time()

    def _start_idle_monitor(self):
        """Start background task to monitor idle timeout."""
        if self._idle_task is not None:
            return

        async def _monitor():
            while self._state == GatewayState.RUNNING:
                await asyncio.sleep(30)  # Check every 30 seconds

                idle_time = time.time() - self._last_activity
                if idle_time > self.idle_timeout:
                    logger.info(f"Gateway idle for {idle_time:.0f}s, stopping...")
                    await self.stop()
                    break

        self._idle_task = asyncio.create_task(_monitor())

    async def ensure_running(self) -> bool:
        """Ensure gateway is running, starting if needed."""
        if self.is_running:
            self._touch_activity()
            return True
        return await self.start()

    def get_status(self) -> dict:
        """Get gateway status information."""
        return {
            "state": self._state.value,
            "running": self.is_running,
            "started_by_us": self._started_by_us,
            "port": self.port,
            "pid": self._process.pid if self._process else None,
            "idle_seconds": time.time() - self._last_activity,
            "idle_timeout": self.idle_timeout,
        }


# Singleton instance
_manager: Optional[GatewayManager] = None


def get_gateway_manager() -> GatewayManager:
    """Get or create GatewayManager singleton."""
    global _manager
    if _manager is None:
        _manager = GatewayManager()
    return _manager


async def start_gateway() -> bool:
    """Convenience: start gateway."""
    return await get_gateway_manager().start()


async def stop_gateway() -> bool:
    """Convenience: stop gateway."""
    return await get_gateway_manager().stop()


async def ensure_gateway() -> bool:
    """Convenience: ensure gateway is running."""
    return await get_gateway_manager().ensure_running()


__all__ = [
    "GatewayState",
    "GatewayManager",
    "get_gateway_manager",
    "start_gateway",
    "stop_gateway",
    "ensure_gateway",
    "cleanup_stale_locks",
]
