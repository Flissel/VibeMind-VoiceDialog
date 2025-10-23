"""
MoireTracker Service Lifecycle Manager
Handles automatic starting and stopping of MoireTracker service
Production version with proper logging, error handling, and cross-platform support

Platform Support:
- Windows: MoireTracker.exe (shared memory IPC)
- Linux: MoireTracker (Unix domain socket IPC)
- macOS: MoireTracker (Unix domain socket IPC)
"""

import subprocess
import time
import os
import sys
import platform
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import get_config, MoireTrackerConfig
from logger import get_logger
from ipc_auth import IPCAuthManager

logger = get_logger(__name__)


def get_moire_executable_name() -> str:
    """Get platform-specific executable name"""
    return "MoireTracker.exe" if platform.system() == "Windows" else "MoireTracker"


# Note: POSIX shared memory does not require file cleanup like Unix sockets.
# Shared memory objects persist in /dev/shm on Linux and are cleaned up
# by MoireTracker on shutdown.


class MoireTrackerService:
    """
    Manages MoireTracker lifecycle as a background service

    Usage:
        service = MoireTrackerService()
        if service.start():
            # MoireTracker is running
            client = MoireTrackerClient()
            client.connect()
            ...
        service.stop()
    """

    def __init__(self, config: Optional[MoireTrackerConfig] = None):
        """
        Initialize service manager

        Args:
            config: MoireTracker configuration (uses default if None)
        """
        if config is None:
            app_config = get_config()
            config = app_config.moire_tracker

        self.config = config
        self.moire_path = config.path

        # Platform-specific executable name
        exe_name = get_moire_executable_name()
        self.moire_exe = self.moire_path / exe_name

        self.process: Optional[subprocess.Popen] = None
        self.start_attempts = 0
        self.max_start_attempts = 3

        # IPC authentication manager
        self.auth_manager = IPCAuthManager() if config.ipc_auth_enabled else None
        self.auth_token: Optional[bytes] = None

        logger.info(f"MoireTrackerService initialized with path: {self.moire_path}")
        logger.info(f"Platform: {platform.system()}, Executable: {exe_name}")
        if config.ipc_auth_enabled:
            logger.info("IPC authentication enabled")

    def start(self) -> bool:
        """
        Start MoireTracker in background

        Returns:
            True if started successfully or already running
        """
        # Check if already running
        if self.is_running():
            logger.info("MoireTracker already running")
            return True

        # Check if executable exists
        if not self.moire_exe.exists():
            logger.error(f"MoireTracker executable not found at {self.moire_exe}")
            logger.error("Please build MoireTracker first")
            return False

        # Note: POSIX shared memory doesn't need pre-start cleanup
        # MoireTracker will create shared memory regions on startup

        # Retry logic
        for attempt in range(1, self.max_start_attempts + 1):
            logger.info(f"Starting MoireTracker (attempt {attempt}/{self.max_start_attempts})...")
            logger.info(f"  Path: {self.moire_path}")

            try:
                # Start process in background with proper error handling
                self.process = subprocess.Popen(
                    [str(self.moire_exe)],
                    cwd=str(self.moire_path),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
                    encoding='utf-8',
                    errors='replace'  # Handle Unicode gracefully
                )

                # Wait for initialization
                # - Shared memory creation: ~1-2 seconds
                # - Desktop auto-scan: triggers after 5 seconds
                # Total wait: 7 seconds to ensure desktop scan completes
                logger.info("Waiting for initialization (7 seconds)...")
                logger.debug("  - Shared memory creation: ~2s")
                logger.debug("  - Desktop scan: ~5s")
                time.sleep(7)

                # Check if process is still alive
                if self.is_running():
                    logger.info("MoireTracker started and initialized successfully")
                    self.start_attempts = 0

                    # Generate and store IPC auth token (if enabled)
                    if self.auth_manager:
                        logger.info("Generating IPC authentication token...")
                        self.auth_token = self.auth_manager.generate_and_store_token()
                        if self.auth_token:
                            logger.info("IPC token generated and stored successfully")
                        else:
                            logger.error("Failed to generate IPC token - authentication disabled")
                            self.auth_manager = None

                    return True
                else:
                    exit_code = self.process.poll()
                    logger.error(f"MoireTracker failed to start (exit code: {exit_code})")

                    # Try to read error output
                    if self.process.stdout:
                        stdout = self.process.stdout.read()
                        if stdout:
                            logger.debug(f"STDOUT: {stdout}")
                    if self.process.stderr:
                        stderr = self.process.stderr.read()
                        if stderr:
                            logger.error(f"STDERR: {stderr}")

                    if attempt < self.max_start_attempts:
                        logger.warning(f"Retrying in 2 seconds...")
                        time.sleep(2)

            except Exception as e:
                logger.error(f"Failed to start MoireTracker: {e}", exc_info=True)
                if attempt < self.max_start_attempts:
                    logger.warning(f"Retrying in 2 seconds...")
                    time.sleep(2)

        # All attempts failed
        logger.critical("Failed to start MoireTracker after maximum attempts")
        self.start_attempts += 1
        return False

    def stop(self):
        """
        Stop MoireTracker gracefully

        Tries to terminate gracefully first, then kills if necessary
        """
        if not self.process:
            logger.debug("No MoireTracker process to stop")
            return

        try:
            logger.info("Stopping MoireTracker...")

            # Try graceful termination first
            self.process.terminate()

            # Wait up to 5 seconds
            try:
                self.process.wait(timeout=5)
                logger.info("MoireTracker stopped gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if graceful termination failed
                logger.warning("Graceful shutdown timed out, force killing...")
                self.process.kill()
                self.process.wait()
                logger.warning("MoireTracker force killed")

        except Exception as e:
            logger.error(f"Error stopping MoireTracker: {e}", exc_info=True)

        finally:
            # Clean up IPC auth token
            if self.auth_manager:
                logger.debug("Deleting IPC authentication token...")
                self.auth_manager.delete_token()
                self.auth_token = None

            # Note: POSIX shared memory cleanup is handled by MoireTracker
            # Shared memory regions are removed when MoireTracker exits

            self.process = None

    def is_running(self) -> bool:
        """
        Check if MoireTracker is currently running

        Returns:
            True if running, False otherwise
        """
        # Check our managed process first
        if self.process:
            return self.process.poll() is None

        # Check if any MoireTracker process is running (not managed by us)
        try:
            exe_name = get_moire_executable_name()

            if os.name == 'nt':  # Windows
                result = subprocess.run(
                    ['tasklist', '/FI', f'IMAGENAME eq {exe_name}'],
                    capture_output=True,
                    text=True,
                    encoding='utf-8',
                    errors='replace',  # Handle Unicode gracefully
                    creationflags=subprocess.CREATE_NO_WINDOW,
                    timeout=5
                )
                return exe_name in result.stdout
            else:  # Unix-like (Linux, macOS)
                result = subprocess.run(
                    ['pgrep', '-f', exe_name],
                    capture_output=True,
                    timeout=5
                )
                return result.returncode == 0
        except subprocess.TimeoutExpired:
            logger.warning("Process check timed out")
            return False
        except Exception as e:
            logger.debug(f"Process check failed: {e}")
            return False

    def restart(self) -> bool:
        """
        Restart MoireTracker

        Returns:
            True if restarted successfully
        """
        logger.info("Restarting MoireTracker...")
        self.stop()
        time.sleep(1)  # Brief pause
        return self.start()

    def get_health_status(self) -> dict:
        """
        Get detailed health status

        Returns:
            Dictionary with health information
        """
        return {
            'running': self.is_running(),
            'process_managed': self.process is not None,
            'exe_path': str(self.moire_exe),
            'exe_exists': self.moire_exe.exists(),
            'start_attempts': self.start_attempts,
            'config_timeout': self.config.timeout_ms,
            'ipc_auth_enabled': self.config.ipc_auth_enabled,
            'ipc_auth_token_exists': self.auth_token is not None
        }

    def get_auth_token(self) -> Optional[bytes]:
        """
        Get the current IPC authentication token

        Returns:
            Auth token bytes if authentication is enabled and token exists,
            None otherwise
        """
        return self.auth_token

    def __del__(self):
        """Cleanup on deletion"""
        if self.process and self.is_running():
            logger.info("Auto-stopping MoireTracker on cleanup")
            self.stop()


# Convenience function for backward compatibility
def create_service(moire_path: Optional[str] = None) -> MoireTrackerService:
    """
    Create MoireTrackerService instance

    Args:
        moire_path: Path to MoireTracker (deprecated, use config instead)

    Returns:
        MoireTrackerService instance
    """
    if moire_path:
        logger.warning("Passing moire_path directly is deprecated. Use config instead.")
        from config import MoireTrackerConfig
        config = MoireTrackerConfig(path=Path(moire_path))
        return MoireTrackerService(config)
    return MoireTrackerService()
