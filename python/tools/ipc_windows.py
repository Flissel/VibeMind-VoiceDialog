"""
Windows Shared Memory IPC Backend
Implements IPCBackend using Windows named shared memory (mmap)
"""

import mmap
import struct
import time
from typing import Optional, Tuple
from pathlib import Path
import sys

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from logger import get_logger

# Handle both module import and standalone execution
try:
    from .ipc_backend import IPCBackend
    from .moire_types import CommandType, ResponseStatus
except ImportError:
    from ipc_backend import IPCBackend
    from moire_types import CommandType, ResponseStatus

logger = get_logger(__name__)


class WindowsSharedMemoryIPC(IPCBackend):
    """
    Windows shared memory implementation for MoireTracker IPC
    Uses Windows named memory-mapped files
    """

    # Memory region names (must match C++ COMMAND_MEMORY_NAME, etc.)
    CMD_MEMORY_NAME = "MoireTracker_Commands"
    RESP_MEMORY_NAME = "MoireTracker_Responses"
    MOUSE_MEMORY_NAME = "MoireTracker_MouseStream"

    # Memory sizes (must match or be larger than C++ sizes)
    CMD_MEMORY_SIZE = 4096
    RESP_MEMORY_SIZE = 4 * 1024 * 1024
    MOUSE_MEMORY_SIZE = 21000

    def __init__(self):
        self.command_mem = None
        self.response_mem = None
        self.mouse_stream_mem = None
        self._connected = False
        self.request_id = int(time.time() * 1000000)  # Microseconds

    def connect(self) -> bool:
        """Connect to MoireTracker shared memory regions"""
        try:
            logger.debug("Opening Windows shared memory regions...")

            # Open command memory
            self.command_mem = mmap.mmap(
                -1,
                self.CMD_MEMORY_SIZE,
                tagname=self.CMD_MEMORY_NAME
            )
            logger.debug("Command memory opened")

            # Open response memory
            self.response_mem = mmap.mmap(
                -1,
                self.RESP_MEMORY_SIZE,
                tagname=self.RESP_MEMORY_NAME
            )
            logger.debug("Response memory opened")

            # Open mouse stream memory
            self.mouse_stream_mem = mmap.mmap(
                -1,
                self.MOUSE_MEMORY_SIZE,
                tagname=self.MOUSE_MEMORY_NAME
            )
            logger.debug("Mouse stream memory opened")

            self._connected = True
            logger.info("Connected to Windows shared memory")
            return True

        except Exception as e:
            logger.error(f"Failed to connect to Windows shared memory: {e}")
            self._cleanup()
            return False

    def _cleanup(self):
        """Close any partially opened connections"""
        if self.command_mem:
            try:
                self.command_mem.close()
            except:
                pass
            self.command_mem = None
        if self.response_mem:
            try:
                self.response_mem.close()
            except:
                pass
            self.response_mem = None
        if self.mouse_stream_mem:
            try:
                self.mouse_stream_mem.close()
            except:
                pass
            self.mouse_stream_mem = None

    def send_command(self, cmd_type: CommandType, request_id: int, data: bytes = b'') -> bool:
        """Send command to MoireTracker via shared memory"""
        if not self._connected:
            logger.error("Cannot send command: not connected")
            return False

        try:
            timestamp_ms = int(time.time() * 1000)

            # Clear response_ready flag in response memory
            self.response_mem.seek(0)
            self.response_mem.write(b'\x00')

            # Build command structure
            # SharedMemoryCommand layout:
            # - [command_ready (bool, 1 byte)]
            # - [response_ready (bool, 1 byte)]
            # - [padding (6 bytes, to align Command to 8 bytes)]
            # - [Command struct at offset 8]
            # Command struct: [type(4)] [padding(4)] [request_id(8)] [timestamp(8)] [params...]
            self.command_mem.seek(8)  # Skip to Command struct (8-byte aligned)

            # Pack command with proper alignment
            # Handle both int and enum types
            cmd_value = cmd_type.value if hasattr(cmd_type, 'value') else cmd_type
            self.command_mem.write(struct.pack('I', cmd_value))  # type
            self.command_mem.write(b'\x00' * 4)  # padding for alignment
            self.command_mem.write(struct.pack('QQ', request_id, timestamp_ms))  # request_id, timestamp

            # Write params if provided
            if data:
                self.command_mem.write(data)

            # Set command_ready flag (this signals C++ to process)
            self.command_mem.seek(0)
            self.command_mem.write(b'\x01')

            logger.debug(f"Sent command: type={cmd_value}, request_id={request_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to send command type={cmd_type}: {e}", exc_info=True)
            return False

    def receive_response(self, timeout_ms: int) -> Optional[Tuple[int, int, int, bytes]]:
        """Wait for response from MoireTracker"""
        if not self._connected:
            return None

        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0

        while (time.time() - start_time) < timeout_sec:
            try:
                # Check response_ready flag (first byte)
                self.response_mem.seek(0)
                flag_bytes = self.response_mem.read(1)
                if len(flag_bytes) == 0:
                    time.sleep(0.001)
                    continue

                response_ready = flag_bytes[0]

                if response_ready:
                    # Read response data starting after response_ready flag
                    # SharedMemoryResponse layout: [response_ready (bool, 1 byte)] [padding (7 bytes)] [Response struct]
                    # Response struct is aligned to 8 bytes
                    self.response_mem.seek(8)
                    response_data = self.response_mem.read(100000)  # Read large buffer

                    # Clear response_ready flag
                    self.response_mem.seek(0)
                    self.response_mem.write(b'\x00')

                    # Parse response header
                    cmd_type, request_id, status, timestamp_ms = self._parse_response_header(response_data)

                    logger.debug(f"Received response: cmd_type={cmd_type}, request_id={request_id}, status={status}")

                    return (cmd_type, request_id, status, response_data)

                time.sleep(0.001)  # 1ms poll interval

            except Exception as e:
                logger.error(f"Error reading response: {e}", exc_info=True)
                return None

        logger.warning(f"Response timeout after {timeout_ms}ms")
        return None

    def _parse_response_header(self, data: bytes) -> Tuple[int, int, int, int]:
        """
        Parse response header

        Returns:
            (cmd_type, request_id, status, timestamp_ms)
        """
        # Response header with padding for 8-byte alignment:
        # [cmd_type(4)] [padding(4)] [request_id(8)] [status(4)] [padding(4)] [timestamp(8)]
        # Total: 32 bytes
        if len(data) < 32:
            raise ValueError(f"Response header requires 32 bytes, got {len(data)}")

        # Unpack with explicit padding (4x = 4 bytes padding)
        cmd_type, request_id, status, timestamp_ms = struct.unpack('I4xQI4xQ', data[:32])
        return (cmd_type, request_id, status, timestamp_ms)

    def receive_mouse_position(self) -> Optional[bytes]:
        """Receive real-time mouse position data from mouse stream memory"""
        if not self._connected or not self.mouse_stream_mem:
            return None

        try:
            # Read mouse stream memory structure
            # MouseStream: [stream_ready (bool, 4 bytes)] [read_index (uint32, 4 bytes)]
            #              [write_index (uint32, 4 bytes)] [positions array...]
            self.mouse_stream_mem.seek(0)
            stream_ready = struct.unpack('I', self.mouse_stream_mem.read(4))[0]

            if not stream_ready:
                return None

            read_index = struct.unpack('I', self.mouse_stream_mem.read(4))[0]
            write_index = struct.unpack('I', self.mouse_stream_mem.read(4))[0]

            if read_index == write_index:
                return None  # No new data

            # Read MousePosition at read_index
            # MousePosition: [x(4)] [y(4)] [confidence(4)] [padding(4)] [timestamp(8)] = 24 bytes
            offset = 12 + (read_index * 24)  # 12 = header size
            self.mouse_stream_mem.seek(offset)
            mouse_data = self.mouse_stream_mem.read(24)

            return mouse_data

        except Exception as e:
            logger.error(f"Error reading mouse stream: {e}")
            return None

    def disconnect(self):
        """Close all shared memory connections"""
        if self.command_mem:
            self.command_mem.close()
            self.command_mem = None
        if self.response_mem:
            self.response_mem.close()
            self.response_mem = None
        if self.mouse_stream_mem:
            self.mouse_stream_mem.close()
            self.mouse_stream_mem = None
        self._connected = False
        logger.info("Disconnected from Windows shared memory")

    def is_connected(self) -> bool:
        """Check if currently connected to service"""
        return self._connected

    def get_backend_name(self) -> str:
        """Get the name of this IPC backend"""
        return "Windows Shared Memory"
