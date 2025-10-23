"""
POSIX Shared Memory IPC Backend for Linux/macOS

Uses POSIX shared memory (shm_open/mmap) to match MoireTracker's Unix implementation.
Compatible with MoireTracker's cross_platform_shm.cpp.
"""

import mmap
import struct
import time
import sys
from pathlib import Path
from typing import Optional, Tuple

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger import get_logger

# Handle both module import and standalone execution
try:
    from .ipc_backend import IPCBackend
    from .moire_types import MousePosition, CommandType, ResponseStatus
except ImportError:
    from ipc_backend import IPCBackend
    from moire_types import MousePosition, CommandType, ResponseStatus

logger = get_logger(__name__)

# Try to import posix_ipc (install with: pip install posix-ipc)
try:
    import posix_ipc
    POSIX_IPC_AVAILABLE = True
except ImportError:
    POSIX_IPC_AVAILABLE = False
    logger.warning("posix_ipc module not available. Install with: pip install posix-ipc")


class PosixSharedMemoryIPC(IPCBackend):
    """
    POSIX shared memory IPC backend for Linux and macOS

    Uses shm_open/mmap to match MoireTracker's C++ implementation.

    Memory Regions:
    ---------------
    1. Command Memory: /MoireTracker_Commands (4KB)
    2. Response Memory: /MoireTracker_Responses (4MB)
    3. Mouse Stream Memory: /MoireTracker_MouseStream (21KB)

    Note: POSIX shared memory names MUST start with "/" on Linux/macOS
    """

    # Memory region names (POSIX requires leading slash)
    CMD_MEMORY_NAME = "/MoireTracker_Commands"
    RESP_MEMORY_NAME = "/MoireTracker_Responses"
    MOUSE_MEMORY_NAME = "/MoireTracker_MouseStream"

    # Memory sizes (must match MoireTracker C++)
    CMD_MEMORY_SIZE = 4096  # 4KB
    RESP_MEMORY_SIZE = 4 * 1024 * 1024  # 4MB
    MOUSE_MEMORY_SIZE = 21504  # 21KB

    # Protocol constants
    HEADER_SIZE = 16  # Command/Response header
    MOUSE_POSITION_SIZE = 24  # MousePosition struct size

    def __init__(self, timeout_ms: int = 5000):
        """
        Initialize POSIX shared memory IPC backend

        Args:
            timeout_ms: Default timeout in milliseconds
        """
        if not POSIX_IPC_AVAILABLE:
            raise ImportError("posix_ipc module required. Install with: pip install posix-ipc")

        self.timeout_ms = timeout_ms
        self.connected = False

        # Shared memory objects
        self.cmd_shm = None
        self.resp_shm = None
        self.mouse_shm = None

        # Memory-mapped regions
        self.command_mem = None
        self.response_mem = None
        self.mouse_stream_mem = None

        logger.debug("POSIX Shared Memory IPC initialized")

    def connect(self) -> bool:
        """
        Connect to MoireTracker shared memory regions

        Returns:
            True if connection successful
        """
        try:
            # Open command memory
            logger.debug(f"Opening command memory: {self.CMD_MEMORY_NAME}")
            self.cmd_shm = posix_ipc.SharedMemory(self.CMD_MEMORY_NAME)
            self.command_mem = mmap.mmap(
                self.cmd_shm.fd,
                self.CMD_MEMORY_SIZE,
                prot=mmap.PROT_READ | mmap.PROT_WRITE
            )

            # Open response memory
            logger.debug(f"Opening response memory: {self.RESP_MEMORY_NAME}")
            self.resp_shm = posix_ipc.SharedMemory(self.RESP_MEMORY_NAME)
            self.response_mem = mmap.mmap(
                self.resp_shm.fd,
                self.RESP_MEMORY_SIZE,
                prot=mmap.PROT_READ | mmap.PROT_WRITE
            )

            # Open mouse stream memory
            logger.debug(f"Opening mouse stream memory: {self.MOUSE_MEMORY_NAME}")
            self.mouse_shm = posix_ipc.SharedMemory(self.MOUSE_MEMORY_NAME)
            self.mouse_stream_mem = mmap.mmap(
                self.mouse_shm.fd,
                self.MOUSE_MEMORY_SIZE,
                prot=mmap.PROT_READ | mmap.PROT_WRITE
            )

            self.connected = True
            logger.info("Connected to MoireTracker via POSIX shared memory")
            return True

        except posix_ipc.ExistentialError:
            logger.error("Shared memory regions not found - MoireTracker may not be running")
            logger.info("Expected regions: " +
                       f"{self.CMD_MEMORY_NAME}, {self.RESP_MEMORY_NAME}, {self.MOUSE_MEMORY_NAME}")
            return False
        except Exception as e:
            logger.error(f"Failed to connect to shared memory: {e}")
            return False

    def send_command(self, cmd_type: CommandType, request_id: int, data: bytes = b'') -> bool:
        """
        Send command to MoireTracker via shared memory

        Args:
            cmd_type: Command type enum
            request_id: Unique request ID
            data: Optional command payload

        Returns:
            True if send successful
        """
        if not self.connected or not self.command_mem:
            logger.error("Not connected to service")
            return False

        try:
            # Build command header: [cmd_type:4][request_id:8][data_length:4]
            header = struct.pack(
                'IQI',
                cmd_type.value,
                request_id,
                len(data)
            )

            # Write to command memory
            self.command_mem.seek(0)
            self.command_mem.write(header)
            if data:
                self.command_mem.write(data)

            # Set command_ready flag (first byte after header+data)
            # MoireTracker polls this flag to know a command is ready
            flag_offset = self.HEADER_SIZE + len(data)
            self.command_mem.seek(flag_offset)
            self.command_mem.write(b'\x01')  # Set ready flag

            logger.debug(f"Sent command: {cmd_type.name} (ID: {request_id}, {len(data)} bytes)")
            return True

        except Exception as e:
            logger.error(f"Send command failed: {e}")
            return False

    def receive_response(self, timeout_ms: int) -> Optional[Tuple[int, int, int, bytes]]:
        """
        Receive response from MoireTracker via shared memory

        Args:
            timeout_ms: Timeout in milliseconds

        Returns:
            Tuple of (cmd_type, request_id, status, data) or None
        """
        if not self.connected or not self.response_mem:
            logger.error("Not connected to service")
            return None

        try:
            # Poll for response_ready flag
            start_time = time.time()
            timeout_sec = timeout_ms / 1000.0

            while (time.time() - start_time) < timeout_sec:
                # Check response_ready flag (first byte)
                self.response_mem.seek(0)
                ready_flag = self.response_mem.read(1)

                if ready_flag == b'\x01':
                    # Response is ready, read it
                    self.response_mem.seek(1)  # Skip flag byte

                    # Read response header: [cmd_type:4][request_id:8][status:4][data_length:4]
                    header_data = self.response_mem.read(20)
                    if len(header_data) < 20:
                        logger.error("Incomplete response header")
                        return None

                    cmd_type, request_id, status, data_length = struct.unpack('IQII', header_data)

                    # Read payload data
                    if data_length > 0:
                        payload = self.response_mem.read(data_length)
                    else:
                        payload = b''

                    # Clear response_ready flag
                    self.response_mem.seek(0)
                    self.response_mem.write(b'\x00')

                    logger.debug(f"Received response: cmd={cmd_type}, ID={request_id}, "
                               f"status={status}, {len(payload)} bytes")
                    return (cmd_type, request_id, status, payload)

                # Sleep briefly before polling again (avoid busy-wait)
                time.sleep(0.001)  # 1ms

            logger.debug(f"Receive timeout after {timeout_ms}ms")
            return None

        except Exception as e:
            logger.error(f"Receive response failed: {e}")
            return None

    def receive_mouse_position(self) -> Optional[MousePosition]:
        """
        Receive real-time mouse position from shared ring buffer

        Returns:
            MousePosition object or None
        """
        if not self.connected or not self.mouse_stream_mem:
            logger.error("Mouse stream memory not connected")
            return None

        try:
            # Read ring buffer header: [active:1][write_index:4][read_index:4]
            self.mouse_stream_mem.seek(0)
            header = self.mouse_stream_mem.read(9)

            if len(header) < 9:
                logger.error("Invalid mouse stream header")
                return None

            active, write_index, read_index = struct.unpack('BII', header)

            if not active:
                logger.debug("Mouse stream not active")
                return None

            # Check if data available
            if read_index == write_index:
                logger.debug("No new mouse data")
                return None

            # Read from ring buffer at read_index
            # Ring buffer starts at offset 9, each entry is 24 bytes
            entry_offset = 9 + (read_index * self.MOUSE_POSITION_SIZE)
            self.mouse_stream_mem.seek(entry_offset)
            mouse_data = self.mouse_stream_mem.read(self.MOUSE_POSITION_SIZE)

            if len(mouse_data) < self.MOUSE_POSITION_SIZE:
                logger.error("Incomplete mouse position data")
                return None

            # Parse: [x:4][y:4][confidence:4][padding:4][timestamp:8]
            x, y, confidence, _, timestamp = struct.unpack('ffffQ', mouse_data)

            # Update read_index (circular buffer)
            max_entries = (self.MOUSE_MEMORY_SIZE - 9) // self.MOUSE_POSITION_SIZE
            new_read_index = (read_index + 1) % max_entries

            self.mouse_stream_mem.seek(5)  # Offset to read_index field
            self.mouse_stream_mem.write(struct.pack('I', new_read_index))

            return MousePosition(x=x, y=y, confidence=confidence, timestamp=timestamp)

        except Exception as e:
            logger.error(f"Failed to receive mouse position: {e}")
            return None

    def disconnect(self):
        """Close all shared memory connections"""
        try:
            if self.command_mem:
                self.command_mem.close()
                self.command_mem = None

            if self.response_mem:
                self.response_mem.close()
                self.response_mem = None

            if self.mouse_stream_mem:
                self.mouse_stream_mem.close()
                self.mouse_stream_mem = None

            # Close shared memory file descriptors
            if self.cmd_shm:
                self.cmd_shm.close_fd()
                self.cmd_shm = None

            if self.resp_shm:
                self.resp_shm.close_fd()
                self.resp_shm = None

            if self.mouse_shm:
                self.mouse_shm.close_fd()
                self.mouse_shm = None

            self.connected = False
            logger.info("Disconnected from POSIX shared memory")

        except Exception as e:
            logger.debug(f"Error during disconnect: {e}")

    def is_connected(self) -> bool:
        """Check if connected"""
        return self.connected

    def get_backend_name(self) -> str:
        """Get backend name"""
        return "POSIX Shared Memory"

    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()


# Alias for backward compatibility with existing code
UnixDomainSocketIPC = PosixSharedMemoryIPC


if __name__ == "__main__":
    # Quick test
    logger.info("Testing POSIX Shared Memory IPC...")

    if not POSIX_IPC_AVAILABLE:
        logger.error("posix_ipc module not available. Install with: pip install posix-ipc")
        sys.exit(1)

    ipc = PosixSharedMemoryIPC()

    if ipc.connect():
        logger.info("Connection successful!")

        # Test mouse position
        mouse = ipc.receive_mouse_position()
        if mouse:
            logger.info(f"Mouse position: ({mouse.x:.2f}, {mouse.y:.2f})")

        ipc.disconnect()
    else:
        logger.error("Connection failed - make sure MoireTracker is running")
