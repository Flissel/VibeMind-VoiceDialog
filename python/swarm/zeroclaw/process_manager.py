"""
ZeroClaw Process Manager

Spawns and manages the ZeroClaw gateway as a subprocess.
Handles health checks, auto-restart, and graceful shutdown.
"""

import asyncio
import logging
import os
import shutil
import signal
import subprocess
import sys
from typing import Optional

logger = logging.getLogger(__name__)


class ZeroClawProcessManager:
    """
    Manages ZeroClaw gateway as a subprocess.

    Similar to how Electron spawns the Python backend,
    this spawns ZeroClaw and monitors its health.
    """

    def __init__(
        self,
        binary: str = None,
        port: int = None,
        config_path: str = None,
        max_restarts: int = 3,
    ):
        self._binary = binary or os.getenv("ZEROCLAW_BINARY", "zeroclaw")
        self._port = port or int(os.getenv("ZEROCLAW_PORT", "42618"))
        self._config_path = config_path or os.getenv("ZEROCLAW_CONFIG_PATH", "")
        self._max_restarts = max_restarts
        self._process: Optional[subprocess.Popen] = None
        self._restart_count = 0
        self._running = False
        self._health_task: Optional[asyncio.Task] = None

    @property
    def port(self) -> int:
        return self._port

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def _find_binary(self) -> Optional[str]:
        """Find zeroclaw binary path."""
        # Check configured path
        if os.path.isfile(self._binary):
            return self._binary

        # Check submodule build
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))
        )))
        submodule_binary = os.path.join(
            project_root, "external", "zeroclaw", "target", "release", "zeroclaw"
        )
        if sys.platform == "win32":
            submodule_binary += ".exe"
        if os.path.isfile(submodule_binary):
            return submodule_binary

        # Check PATH
        found = shutil.which(self._binary)
        if found:
            return found

        return None

    def start(self) -> bool:
        """
        Start ZeroClaw gateway subprocess.

        Returns:
            True if started successfully
        """
        if self.is_running:
            logger.info(f"ZeroClaw already running (pid={self._process.pid})")
            return True

        binary_path = self._find_binary()
        if not binary_path:
            logger.error(
                f"ZeroClaw binary not found: '{self._binary}'. "
                f"Install with: cargo install zeroclaw "
                f"or build submodule: cd external/zeroclaw && cargo build --release"
            )
            return False

        cmd = [binary_path, "gateway", "--port", str(self._port)]

        if self._config_path and os.path.isfile(self._config_path):
            cmd.extend(["--config", self._config_path])

        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            logger.info(
                f"ZeroClaw gateway started (pid={self._process.pid}, port={self._port})"
            )
            self._running = True
            return True

        except FileNotFoundError:
            logger.error(f"ZeroClaw binary not executable: {binary_path}")
            return False
        except Exception as e:
            logger.error(f"Failed to start ZeroClaw: {e}")
            return False

    def stop(self):
        """Gracefully stop ZeroClaw subprocess."""
        self._running = False

        if self._health_task and not self._health_task.done():
            self._health_task.cancel()

        if not self._process:
            return

        if self._process.poll() is not None:
            logger.info("ZeroClaw already stopped")
            self._process = None
            return

        pid = self._process.pid
        logger.info(f"Stopping ZeroClaw (pid={pid})...")

        try:
            if sys.platform == "win32":
                self._process.terminate()
            else:
                self._process.send_signal(signal.SIGTERM)

            try:
                self._process.wait(timeout=5)
                logger.info(f"ZeroClaw stopped gracefully (pid={pid})")
            except subprocess.TimeoutExpired:
                logger.warning(f"ZeroClaw did not stop gracefully, killing (pid={pid})")
                self._process.kill()
                self._process.wait(timeout=3)

        except Exception as e:
            logger.error(f"Error stopping ZeroClaw: {e}")
        finally:
            self._process = None

    async def health_check(self) -> bool:
        """
        Check if ZeroClaw gateway is responding.

        Returns:
            True if healthy
        """
        if not self.is_running:
            return False

        try:
            import aiohttp
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/v1/models",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    return resp.status == 200
        except Exception:
            return False

    async def wait_for_ready(self, timeout: float = 30.0) -> bool:
        """
        Wait for ZeroClaw gateway to become ready.

        Args:
            timeout: Max seconds to wait

        Returns:
            True if ready within timeout
        """
        start = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start < timeout:
            if await self.health_check():
                logger.info(f"ZeroClaw gateway ready on port {self._port}")
                return True
            await asyncio.sleep(0.5)

        logger.error(f"ZeroClaw gateway not ready after {timeout}s")
        return False

    async def start_with_health_monitoring(self) -> bool:
        """
        Start ZeroClaw and begin health monitoring.

        Returns:
            True if started and ready
        """
        if not self.start():
            return False

        if not await self.wait_for_ready():
            self.stop()
            return False

        self._health_task = asyncio.create_task(self._monitor_health())
        return True

    async def _monitor_health(self):
        """Background task to monitor ZeroClaw health and auto-restart."""
        while self._running:
            await asyncio.sleep(30)

            if not self._running:
                break

            if not self.is_running:
                if self._restart_count >= self._max_restarts:
                    logger.error(
                        f"ZeroClaw crashed {self._restart_count} times, giving up"
                    )
                    self._running = False
                    break

                self._restart_count += 1
                logger.warning(
                    f"ZeroClaw crashed, restarting "
                    f"(attempt {self._restart_count}/{self._max_restarts})"
                )

                if self.start():
                    if await self.wait_for_ready(timeout=15):
                        logger.info("ZeroClaw restarted successfully")
                    else:
                        logger.error("ZeroClaw restart failed (not ready)")

    def __del__(self):
        self.stop()


# Singleton
_manager: Optional[ZeroClawProcessManager] = None


def get_zeroclaw_manager() -> ZeroClawProcessManager:
    """Get or create ZeroClawProcessManager singleton."""
    global _manager
    if _manager is None:
        _manager = ZeroClawProcessManager()
    return _manager
