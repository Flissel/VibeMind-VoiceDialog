"""
IPC Backend Factory - Platform Detection and Instantiation

Automatically selects the appropriate IPC backend based on the current platform.
"""

import platform
import sys
from pathlib import Path

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger import get_logger

# Handle both module import and standalone execution
try:
    from .ipc_backend import IPCBackend
except ImportError:
    from ipc_backend import IPCBackend

logger = get_logger(__name__)


def create_ipc_backend(**kwargs) -> IPCBackend:
    """
    Create appropriate IPC backend for current platform

    Args:
        **kwargs: Backend-specific configuration parameters

    Returns:
        IPCBackend instance for the current platform

    Raises:
        RuntimeError: If platform is not supported
    """

    system = platform.system()

    logger.info(f"Detecting platform: {system}")

    if system == "Windows":
        try:
            from .ipc_windows import WindowsSharedMemoryIPC
        except ImportError:
            from ipc_windows import WindowsSharedMemoryIPC
        logger.info("Using Windows Shared Memory IPC backend")
        return WindowsSharedMemoryIPC(**kwargs)

    elif system == "Linux":
        try:
            from .ipc_unix import PosixSharedMemoryIPC
        except ImportError:
            from ipc_unix import PosixSharedMemoryIPC
        logger.info("Using POSIX Shared Memory IPC backend (Linux)")
        return PosixSharedMemoryIPC(**kwargs)

    elif system == "Darwin":  # macOS
        try:
            from .ipc_unix import PosixSharedMemoryIPC
        except ImportError:
            from ipc_unix import PosixSharedMemoryIPC
        logger.info("Using POSIX Shared Memory IPC backend (macOS)")
        return PosixSharedMemoryIPC(**kwargs)

    else:
        error_msg = f"Unsupported platform: {system}"
        logger.error(error_msg)
        raise RuntimeError(error_msg)


def get_platform_info() -> dict:
    """
    Get detailed platform information

    Returns:
        Dictionary with platform details
    """
    return {
        'system': platform.system(),
        'release': platform.release(),
        'version': platform.version(),
        'machine': platform.machine(),
        'processor': platform.processor(),
        'python_version': platform.python_version(),
    }


def is_windows() -> bool:
    """Check if running on Windows"""
    return platform.system() == "Windows"


def is_linux() -> bool:
    """Check if running on Linux"""
    return platform.system() == "Linux"


def is_macos() -> bool:
    """Check if running on macOS"""
    return platform.system() == "Darwin"


if __name__ == "__main__":
    # Quick platform detection test
    info = get_platform_info()
    print(f"Platform Information:")
    for key, value in info.items():
        print(f"  {key}: {value}")

    try:
        backend = create_ipc_backend()
        print(f"\nSelected IPC Backend: {backend.get_backend_name()}")
    except RuntimeError as e:
        print(f"\nError: {e}")
