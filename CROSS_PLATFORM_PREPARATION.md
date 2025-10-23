# MoireTracker Cross-Platform Preparation Guide

**Status:** 🚧 Planning Phase - Preparing for cross-platform IPC migration

**Goal:** Make voice_dialog + MoireTracker work on Windows, macOS, and Linux

---

## 🎯 Current Architecture Analysis

### Windows-Only Dependencies

| Component | Windows API | Cross-Platform Alternative |
|-----------|-------------|---------------------------|
| **IPC Communication** | Windows shared memory (`mmap`) | Unix domain sockets / Named pipes |
| **Graphics** | DirectX 11 (MoireTracker) | Vulkan / OpenGL |
| **OCR** | Windows.Media.Ocr | Tesseract OCR (cross-platform) |
| **Process Management** | `subprocess.CREATE_NO_WINDOW` | Standard subprocess with platform checks |
| **Build System** | Visual Studio 2022 | CMake + platform-agnostic compilers |

---

## 📋 Migration Strategy

### Phase 1: Abstract IPC Layer (voice_dialog changes)

**Create platform-agnostic IPC abstraction:**

```
python/tools/
├── ipc_backend.py          # Abstract base class
├── ipc_windows.py          # Windows shared memory (current)
├── ipc_unix.py             # Unix domain sockets (new)
├── ipc_factory.py          # Platform detection + instantiation
└── moire_client.py         # Updated to use abstraction
```

**Key changes:**

1. **Abstract IPC Interface** (`ipc_backend.py`):
```python
from abc import ABC, abstractmethod
from typing import Optional, List
from .moire_types import MousePosition, DesktopElement, CommandType

class IPCBackend(ABC):
    """Abstract IPC backend for cross-platform support"""

    @abstractmethod
    def connect(self) -> bool:
        """Connect to MoireTracker service"""
        pass

    @abstractmethod
    def send_command(self, cmd_type: CommandType, data: bytes = b'') -> bool:
        """Send command to service"""
        pass

    @abstractmethod
    def receive_response(self, timeout_ms: int) -> Optional[tuple]:
        """Receive response from service"""
        pass

    @abstractmethod
    def disconnect(self):
        """Close connection"""
        pass
```

2. **Windows Implementation** (`ipc_windows.py`):
```python
import mmap
from .ipc_backend import IPCBackend

class WindowsSharedMemoryIPC(IPCBackend):
    """Windows shared memory implementation (current code)"""

    CMD_MEMORY_NAME = "MoireTracker_Commands"
    RESP_MEMORY_NAME = "MoireTracker_Responses"
    MOUSE_MEMORY_NAME = "MoireTracker_MouseStream"

    def connect(self) -> bool:
        try:
            self.cmd_mem = mmap.mmap(-1, 4096, self.CMD_MEMORY_NAME)
            self.resp_mem = mmap.mmap(-1, 4194304, self.RESP_MEMORY_NAME)
            self.mouse_mem = mmap.mmap(-1, 20480, self.MOUSE_MEMORY_NAME)
            return True
        except Exception as e:
            logger.error(f"Windows IPC connect failed: {e}")
            return False

    # ... rest of current implementation
```

3. **Unix Implementation** (`ipc_unix.py`):
```python
import socket
import struct
from pathlib import Path
from .ipc_backend import IPCBackend

class UnixDomainSocketIPC(IPCBackend):
    """Unix domain socket implementation for Linux/macOS"""

    SOCKET_PATH = "/tmp/moire_tracker.sock"

    def __init__(self):
        self.socket = None
        self.connected = False

    def connect(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            self.socket.connect(self.SOCKET_PATH)
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Unix socket connect failed: {e}")
            return False

    def send_command(self, cmd_type: CommandType, data: bytes = b'') -> bool:
        if not self.connected:
            return False

        try:
            # Protocol: [4 bytes length][4 bytes cmd_type][data]
            msg_len = 8 + len(data)
            header = struct.pack('II', msg_len, cmd_type.value)
            self.socket.sendall(header + data)
            return True
        except Exception as e:
            logger.error(f"Send command failed: {e}")
            return False

    def receive_response(self, timeout_ms: int) -> Optional[tuple]:
        if not self.connected:
            return None

        try:
            self.socket.settimeout(timeout_ms / 1000.0)

            # Read header: [4 bytes length][response data]
            header = self._recv_exact(8)
            if not header:
                return None

            msg_len, status = struct.unpack('II', header)
            data = self._recv_exact(msg_len - 8)

            return (status, data)
        except socket.timeout:
            return None
        except Exception as e:
            logger.error(f"Receive response failed: {e}")
            return None

    def _recv_exact(self, n: int) -> bytes:
        """Receive exactly n bytes"""
        data = b''
        while len(data) < n:
            chunk = self.socket.recv(n - len(data))
            if not chunk:
                break
            data += chunk
        return data if len(data) == n else None

    def disconnect(self):
        if self.socket:
            self.socket.close()
            self.socket = None
            self.connected = False
```

4. **Platform Factory** (`ipc_factory.py`):
```python
import platform
from .ipc_backend import IPCBackend
from .ipc_windows import WindowsSharedMemoryIPC
from .ipc_unix import UnixDomainSocketIPC

def create_ipc_backend() -> IPCBackend:
    """Create appropriate IPC backend for current platform"""

    system = platform.system()

    if system == "Windows":
        return WindowsSharedMemoryIPC()
    elif system in ["Linux", "Darwin"]:  # Darwin = macOS
        return UnixDomainSocketIPC()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
```

5. **Update moire_client.py**:
```python
from .ipc_factory import create_ipc_backend

class MoireTrackerClient:
    def __init__(self, max_retries=3, timeout_ms=5000):
        # Platform-agnostic IPC backend
        self.ipc = create_ipc_backend()

        # ... rest of initialization

    def connect(self) -> bool:
        """Connect using platform-specific IPC"""
        return self.ipc.connect()

    def _send_command(self, cmd_type: CommandType, data: bytes = b''):
        return self.ipc.send_command(cmd_type, data)

    # ... rest of methods use self.ipc
```

---

### Phase 2: MoireTracker C++ Cross-Platform Changes

**Required MoireTracker modifications:**

1. **Abstract Graphics Backend**
   - Keep DirectX 11 for Windows
   - Add Vulkan backend for Linux/macOS
   - OR: Switch to OpenGL for full cross-platform

2. **IPC Server Changes**
   - Windows: Keep shared memory
   - Unix: Add domain socket server
   - Factory pattern for platform selection

3. **OCR Backend Abstraction**
   - Windows: Windows.Media.Ocr (current)
   - Linux/macOS: Tesseract OCR

4. **Build System**
   - CMake with platform detection
   - Conditional compilation for platform-specific code

**Example C++ IPC abstraction:**

```cpp
// ipc_backend.hpp
class IPCBackend {
public:
    virtual ~IPCBackend() = default;
    virtual bool Initialize() = 0;
    virtual bool SendResponse(const Response& response) = 0;
    virtual bool ReceiveCommand(Command& command) = 0;
};

// ipc_windows.hpp
class WindowsSharedMemoryIPC : public IPCBackend {
    HANDLE cmd_handle_;
    HANDLE resp_handle_;
    // ... current implementation
};

// ipc_unix.hpp
class UnixDomainSocketIPC : public IPCBackend {
    int server_fd_;
    int client_fd_;
    // Unix socket server implementation
};

// ipc_factory.cpp
std::unique_ptr<IPCBackend> CreateIPCBackend() {
#ifdef _WIN32
    return std::make_unique<WindowsSharedMemoryIPC>();
#else
    return std::make_unique<UnixDomainSocketIPC>();
#endif
}
```

---

### Phase 3: Desktop Detection Alternatives

**Windows (Current):**
- Windows.Media.Ocr
- Icon template matching
- Window enumeration

**Linux:**
```python
# Use X11 tools
import subprocess

def get_desktop_elements_linux():
    # xdotool for window enumeration
    windows = subprocess.check_output(['xdotool', 'search', '--name', '.*'])

    # xwininfo for window details
    for wid in windows.split():
        info = subprocess.check_output(['xwininfo', '-id', wid])

    # OCR with Tesseract
    import pytesseract
    from PIL import Image
    screenshot = Image.open('/tmp/screenshot.png')
    text = pytesseract.image_to_string(screenshot)

    return elements
```

**macOS:**
```python
# Use Accessibility API
import AppKit

def get_desktop_elements_macos():
    # AppleScript for window enumeration
    script = '''
    tell application "System Events"
        get every window of every process
    end tell
    '''

    # Accessibility API for UI elements
    # NSAccessibility* classes

    return elements
```

---

## 🛠️ Implementation Checklist

### voice_dialog Changes

- [ ] Create `python/tools/ipc_backend.py` (abstract interface)
- [ ] Create `python/tools/ipc_windows.py` (move current code)
- [ ] Create `python/tools/ipc_unix.py` (new Unix sockets)
- [ ] Create `python/tools/ipc_factory.py` (platform detection)
- [ ] Update `python/tools/moire_client.py` to use abstraction
- [ ] Update `python/tools/moire_service.py` for cross-platform process management
- [ ] Add platform-specific desktop detection fallbacks
- [ ] Update tests to run on all platforms
- [ ] Update `CLAUDE.md` with cross-platform notes

### MoireTracker C++ Changes (Separate Repository)

- [ ] Abstract IPC layer (Windows shared memory / Unix sockets)
- [ ] Abstract graphics backend (DirectX 11 / Vulkan / OpenGL)
- [ ] Abstract OCR backend (Windows.Media.Ocr / Tesseract)
- [ ] CMake platform detection
- [ ] Cross-platform build scripts
- [ ] Update build documentation

### Testing

- [ ] Windows: Test with current shared memory IPC
- [ ] Linux: Test with Unix domain sockets
- [ ] macOS: Test with Unix domain sockets
- [ ] Cross-platform integration tests
- [ ] Performance benchmarks per platform

---

## 📊 Platform Capability Matrix

| Feature | Windows | Linux | macOS | Implementation |
|---------|---------|-------|-------|----------------|
| **IPC** | ✅ Shared Memory | 🔄 Unix Sockets | 🔄 Unix Sockets | Phase 1 |
| **Graphics** | ✅ DirectX 11 | ⏳ Vulkan | ⏳ Vulkan | Phase 2 |
| **OCR** | ✅ Windows.Media | ⏳ Tesseract | ⏳ Tesseract | Phase 2 |
| **Desktop Scan** | ✅ Native | ⏳ X11 tools | ⏳ Accessibility | Phase 3 |
| **Mouse Tracking** | ✅ High precision | ⏳ Basic | ⏳ Basic | Phase 2 |
| **Build System** | ✅ CMake + VS | ⏳ CMake + GCC | ⏳ CMake + Clang | Phase 2 |

**Legend:**
- ✅ Implemented
- 🔄 In Progress
- ⏳ Planned

---

## 🚀 Quick Start: Begin Migration

**Step 1: Test current code structure**
```bash
cd C:\Users\User\Desktop\voice_dialog\python
python tests/test_end_to_end.py  # Ensure Windows version works
```

**Step 2: Create IPC abstraction files**
```bash
# Create the new files in python/tools/
touch python/tools/ipc_backend.py
touch python/tools/ipc_windows.py
touch python/tools/ipc_unix.py
touch python/tools/ipc_factory.py
```

**Step 3: Implement abstract interface**
- Copy code from sections above
- Start with `ipc_backend.py` (abstract base class)
- Move current `moire_client.py` code to `ipc_windows.py`
- Implement `ipc_unix.py` for Linux/macOS

**Step 4: Update moire_client.py**
- Replace direct `mmap` usage with `self.ipc.send_command()`
- Use factory pattern: `self.ipc = create_ipc_backend()`

**Step 5: Test on Windows**
- Ensure Windows still works with abstraction layer
- No behavior changes for Windows users

**Step 6: Test on Linux/macOS** (requires MoireTracker Unix socket support)
- Build MoireTracker with Unix socket IPC
- Test voice_dialog connection

---

## 💡 Benefits of Cross-Platform Support

1. **Wider Adoption**: Works on developer's preferred OS
2. **Better Testing**: Can test on multiple platforms
3. **Future-Proof**: Not locked into Windows ecosystem
4. **Community**: Opens up Linux/macOS contributors
5. **Flexibility**: Deploy where needed

---

## 📚 References

- **Unix Domain Sockets**: https://man7.org/linux/man-pages/man7/unix.7.html
- **Python socket module**: https://docs.python.org/3/library/socket.html
- **Tesseract OCR**: https://github.com/tesseract-ocr/tesseract
- **X11 tools (Linux)**: xdotool, xwininfo, wmctrl
- **macOS Accessibility**: NSAccessibility API

---

## 🎯 Next Steps

1. **Review this document** with MoireTracker maintainer
2. **Prioritize platforms**: Windows (maintain) → Linux (next) → macOS (later)
3. **Create GitHub issue** in MoireTracker repo for tracking
4. **Start with Phase 1** (voice_dialog IPC abstraction)
5. **Coordinate with MoireTracker** for Phase 2 (C++ changes)

---

**Document Version:** 1.0
**Last Updated:** 2025-10-19
**Author:** AI Desktop Automation Team
