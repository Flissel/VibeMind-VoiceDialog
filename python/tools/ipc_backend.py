"""
Abstract IPC Backend for Cross-Platform Support

Defines the interface for communicating with MoireTracker service
across different platforms (Windows, Linux, macOS).
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Tuple
from enum import Enum

# Handle both module import and standalone execution
try:
    from .moire_types import MousePosition, DesktopElement, CommandType, ResponseStatus
except ImportError:
    from moire_types import MousePosition, DesktopElement, CommandType, ResponseStatus


class IPCBackend(ABC):
    """Abstract IPC backend for cross-platform MoireTracker communication"""

    @abstractmethod
    def connect(self) -> bool:
        """
        Connect to MoireTracker service

        Returns:
            True if connection successful, False otherwise
        """
        pass

    @abstractmethod
    def send_command(self, cmd_type: CommandType, request_id: int, data: bytes = b'') -> bool:
        """
        Send command to MoireTracker service

        Args:
            cmd_type: Type of command to send
            request_id: Unique request identifier for tracking
            data: Optional command payload

        Returns:
            True if send successful, False otherwise
        """
        pass

    @abstractmethod
    def receive_response(self, timeout_ms: int) -> Optional[Tuple[int, int, int, bytes]]:
        """
        Receive response from MoireTracker service

        Args:
            timeout_ms: Maximum time to wait for response (milliseconds)

        Returns:
            Tuple of (cmd_type, request_id, status, data) or None on timeout/error
        """
        pass

    @abstractmethod
    def receive_mouse_position(self) -> Optional[MousePosition]:
        """
        Receive real-time mouse position data

        Returns:
            MousePosition object or None if unavailable
        """
        pass

    @abstractmethod
    def disconnect(self):
        """
        Close connection to MoireTracker service
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        Check if currently connected to service

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    def get_backend_name(self) -> str:
        """
        Get the name of this IPC backend

        Returns:
            Backend name (e.g., "Windows Shared Memory", "Unix Domain Socket")
        """
        pass


class IPCCapabilities:
    """
    Defines capabilities of different IPC backends
    """

    def __init__(
        self,
        supports_streaming: bool = False,
        supports_bidirectional: bool = True,
        max_message_size: int = 4194304,
        platform_specific: bool = False
    ):
        """
        Initialize IPC capabilities

        Args:
            supports_streaming: True if backend supports continuous streaming
            supports_bidirectional: True if backend supports two-way communication
            max_message_size: Maximum message size in bytes
            platform_specific: True if backend is platform-specific
        """
        self.supports_streaming = supports_streaming
        self.supports_bidirectional = supports_bidirectional
        self.max_message_size = max_message_size
        self.platform_specific = platform_specific
