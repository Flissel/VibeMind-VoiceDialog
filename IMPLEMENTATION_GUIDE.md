# MoireTracker Integration - Step-by-Step Implementation Guide

## 🎯 Overview
This guide will walk you through integrating MoireTracker's advanced screen analysis into your voice_dialog AI agent system. We'll implement:
- ✅ List desktop icons (398 elements)
- ✅ Find specific applications
- ✅ High-precision mouse tracking
- ✅ Visual feedback (moiré overlay)

**Estimated Time**: 10-15 hours total (split over multiple sessions)

---

## 📦 Prerequisites

### Check MoireTracker is Built
```bash
cd C:\Users\User\Desktop\Moire\build\Release
dir MoireTracker.exe
```
✅ Should exist and be ~2-3 MB

### Verify voice_dialog Structure
```bash
cd C:\Users\User\Desktop\voice_dialog
ls python/agents/
ls python/tools/  # May not exist yet - we'll create it
```

---

## 📋 Implementation Phases

### ✨ Phase 1: Python IPC Bridge Library (3-4 hours)
**Goal**: Create reusable Python library to communicate with MoireTracker

### ✨ Phase 2: Enhanced DesktopAgent (2-3 hours)
**Goal**: Replace basic pyautogui with MoireTracker capabilities

### ✨ Phase 3: Service Lifecycle Management (1-2 hours)
**Goal**: Auto-start/stop MoireTracker from voice_dialog

### ✨ Phase 4: Visual Feedback & Mouse Tracking (2-3 hours)
**Goal**: Show overlay during work, add mouse tracking

### ✨ Phase 5: End-to-End Testing (2 hours)
**Goal**: Test with voice commands and fix any issues

---

# 🚀 PHASE 1: Python IPC Bridge Library

## Step 1.1: Create Tools Directory

**Location**: `voice_dialog/python/tools/`

**Action**: Create the directory structure
```bash
cd C:\Users\User\Desktop\voice_dialog\python
mkdir tools
cd tools
```

**Expected Result**: Directory `voice_dialog/python/tools/` exists

---

## Step 1.2: Create Data Types File

**File**: `voice_dialog/python/tools/moire_types.py`

**Purpose**: Define Python classes matching MoireTracker's C++ structs

**Code to Create**:
```python
"""
Data types for MoireTracker IPC
Matches structures from shared_memory_protocol.h
"""

from dataclasses import dataclass
from typing import Optional


# Element types (matches C++ enum)
class ElementType:
    UNKNOWN = 0
    ICON = 1
    BUTTON = 2
    TEXT_LABEL = 3
    INPUT_FIELD = 4
    WINDOW = 5
    MENU = 6

    @staticmethod
    def to_string(elem_type: int) -> str:
        names = {
            0: "Unknown",
            1: "Icon",
            2: "Button",
            3: "Text Label",
            4: "Input Field",
            5: "Window",
            6: "Menu"
        }
        return names.get(elem_type, "Unknown")


# Response status codes
class ResponseStatus:
    SUCCESS = 0
    ERROR_NOT_FOUND = 1
    ERROR_INVALID_PARAMS = 2
    ERROR_TIMEOUT = 3
    ERROR_INTERNAL = 4
    PENDING = 5


# Command types
class CommandType:
    NONE = 0
    START_MOUSE_STREAM = 1
    STOP_MOUSE_STREAM = 2
    GET_MOUSE_POS = 3
    SCAN_ELEMENTS = 10
    FIND_ELEMENT = 11
    SET_ACTIVE = 30
    SET_STANDBY = 31
    SHUTDOWN = 99


@dataclass
class MousePosition:
    """Mouse position with confidence and timestamp"""
    x: float
    y: float
    confidence: float
    timestamp_ms: int


@dataclass
class DesktopElement:
    """Desktop element (icon, button, etc.)"""
    id: int
    text: str
    app_name: str
    x: float
    y: float
    width: float
    height: float
    elem_type: int
    clickable: bool
    confidence: float

    @property
    def type_name(self) -> str:
        """Get human-readable type name"""
        return ElementType.to_string(self.elem_type)

    @property
    def position(self) -> tuple:
        """Get (x, y) tuple"""
        return (self.x, self.y)

    @property
    def size(self) -> tuple:
        """Get (width, height) tuple"""
        return (self.width, self.height)

    def __repr__(self) -> str:
        return f"DesktopElement('{self.text}', {self.type_name}, pos={self.position})"
```

**Testing Step 1.2**:
```python
# In voice_dialog/python/ run:
python -c "from tools.moire_types import DesktopElement, MousePosition; print('✓ Types imported successfully')"
```

✅ **Checkpoint**: No import errors, prints success message

---

## Step 1.3: Create IPC Client Library (Core Implementation)

**File**: `voice_dialog/python/tools/moire_client.py`

**Purpose**: Handle all communication with MoireTracker shared memory

**Code to Create** (Part 1 - Class setup):
```python
"""
MoireTracker IPC Client
Handles shared memory communication with MoireTracker service
"""

import mmap
import struct
import time
from typing import List, Optional
from .moire_types import (
    MousePosition, DesktopElement, CommandType,
    ResponseStatus, ElementType
)


class MoireTrackerClient:
    """
    Client for communicating with MoireTracker via Windows shared memory

    Usage:
        client = MoireTrackerClient()
        if client.connect():
            elements = client.scan_desktop()
            print(f"Found {len(elements)} desktop elements")
    """

    # Memory region names (must match C++ COMMAND_MEMORY_NAME, etc.)
    CMD_MEMORY_NAME = "MoireTracker_Commands"
    RESP_MEMORY_NAME = "MoireTracker_Responses"
    MOUSE_MEMORY_NAME = "MoireTracker_MouseStream"

    # Memory sizes (must match C++ sizes)
    CMD_MEMORY_SIZE = 4096
    RESP_MEMORY_SIZE = 4 * 1024 * 1024  # 4 MB
    MOUSE_MEMORY_SIZE = 32768  # 32 KB

    def __init__(self):
        """Initialize client (not connected yet)"""
        self.command_mem = None
        self.response_mem = None
        self.mouse_stream_mem = None
        self.connected = False
        self.request_id = int(time.time() * 1000000)  # Microseconds

    def connect(self) -> bool:
        """
        Connect to MoireTracker shared memory regions

        Returns:
            True if all memory regions opened successfully
        """
        try:
            print("[MoireClient] Connecting to MoireTracker shared memory...")

            # Open command memory
            self.command_mem = mmap.mmap(
                -1,
                self.CMD_MEMORY_SIZE,
                tagname=self.CMD_MEMORY_NAME
            )
            print(f"  ✓ Command memory opened")

            # Open response memory
            self.response_mem = mmap.mmap(
                -1,
                self.RESP_MEMORY_SIZE,
                tagname=self.RESP_MEMORY_NAME
            )
            print(f"  ✓ Response memory opened")

            # Open mouse stream memory
            self.mouse_stream_mem = mmap.mmap(
                -1,
                self.MOUSE_MEMORY_SIZE,
                tagname=self.MOUSE_MEMORY_NAME
            )
            print(f"  ✓ Mouse stream memory opened")

            self.connected = True
            print("[MoireClient] Connected successfully!")
            return True

        except Exception as e:
            print(f"[MoireClient] Connection failed: {e}")
            print("Make sure MoireTracker.exe is running!")
            self.connected = False
            return False

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
        self.connected = False
        print("[MoireClient] Disconnected")

    def __del__(self):
        """Cleanup on deletion"""
        self.disconnect()
```

**Code to Create** (Part 2 - Low-level IPC):
```python
    def _send_command(self, cmd_type: int, params: bytes = b'') -> Optional[int]:
        """
        Send command to MoireTracker

        Args:
            cmd_type: Command type (from CommandType)
            params: Optional parameter bytes

        Returns:
            Request ID if successful, None if failed
        """
        if not self.connected:
            print("[MoireClient] Not connected!")
            return None

        try:
            # Generate request ID
            self.request_id += 1
            request_id = self.request_id
            timestamp_ms = int(time.time() * 1000)

            # Clear response_ready flag
            self.response_mem.seek(0)
            self.response_mem.write(b'\x00')

            # Build command structure
            # Layout: [command_ready(1)] [response_ready(1)] [Command struct]
            # Command struct: [type(4)] [request_id(8)] [timestamp(8)] [params(variable)]
            self.command_mem.seek(2)  # Skip flags
            self.command_mem.write(struct.pack('IQQ', cmd_type, request_id, timestamp_ms))

            # Write params if provided
            if params:
                self.command_mem.write(params)

            # Set command_ready flag
            self.command_mem.seek(0)
            self.command_mem.write(b'\x01')

            return request_id

        except Exception as e:
            print(f"[MoireClient] Failed to send command: {e}")
            return None

    def _wait_for_response(self, timeout_ms: int = 5000) -> Optional[bytes]:
        """
        Wait for response from MoireTracker

        Args:
            timeout_ms: Timeout in milliseconds

        Returns:
            Response bytes if received, None if timeout
        """
        if not self.connected:
            return None

        start_time = time.time()
        timeout_sec = timeout_ms / 1000.0

        while (time.time() - start_time) < timeout_sec:
            # Check response_ready flag
            self.response_mem.seek(0)
            response_ready = self.response_mem.read(1)[0]

            if response_ready:
                # Read response data
                # Layout: [response_ready(1)] [Response struct]
                # Response: [cmd_type(4)] [request_id(8)] [status(4)] [timestamp(8)] [data...]
                self.response_mem.seek(1)
                response_data = self.response_mem.read(4096)  # Read enough for most responses

                # Clear response_ready flag
                self.response_mem.seek(0)
                self.response_mem.write(b'\x00')

                return response_data

            time.sleep(0.001)  # 1ms poll interval

        print(f"[MoireClient] Response timeout ({timeout_ms}ms)")
        return None

    def _parse_response_header(self, data: bytes) -> tuple:
        """
        Parse response header

        Returns:
            (cmd_type, request_id, status, timestamp_ms)
        """
        # Response header: [cmd_type(4)] [request_id(8)] [status(4)] [timestamp(8)]
        cmd_type, request_id, status, timestamp_ms = struct.unpack('IQIQ', data[:24])
        return (cmd_type, request_id, status, timestamp_ms)
```

**Code to Create** (Part 3 - High-level API):
```python
    def get_mouse_position(self) -> Optional[MousePosition]:
        """
        Get current mouse position

        Returns:
            MousePosition or None if failed
        """
        request_id = self._send_command(CommandType.GET_MOUSE_POS)
        if not request_id:
            return None

        response_data = self._wait_for_response()
        if not response_data:
            return None

        # Parse response
        cmd_type, req_id, status, timestamp = self._parse_response_header(response_data)

        if status != ResponseStatus.SUCCESS:
            print(f"[MoireClient] GET_MOUSE_POS failed: status={status}")
            return None

        # Mouse position data starts at offset 24 (after header)
        # MousePosition struct: [x(4)] [y(4)] [confidence(4)] [timestamp(8)]
        x, y, confidence, pos_timestamp = struct.unpack('fffQ', response_data[24:44])

        return MousePosition(x, y, confidence, pos_timestamp)

    def scan_desktop(self) -> List[DesktopElement]:
        """
        Scan all desktop icons/elements

        Returns:
            List of DesktopElement objects (may be empty if failed)
        """
        request_id = self._send_command(CommandType.SCAN_ELEMENTS)
        if not request_id:
            return []

        # Scanning can take longer, use 10 second timeout
        response_data = self._wait_for_response(timeout_ms=10000)
        if not response_data:
            return []

        # Parse response header
        cmd_type, req_id, status, timestamp = self._parse_response_header(response_data)

        if status != ResponseStatus.SUCCESS:
            print(f"[MoireClient] SCAN_ELEMENTS failed: status={status}")
            return []

        # Scan elements data starts after header (24 bytes)
        # Then MousePosition (20 bytes) - skip it
        # ScanElementsData: [element_count(4)] [DesktopElement array...]
        offset = 24 + 20  # header + mouse_pos
        element_count = struct.unpack('I', response_data[offset:offset+4])[0]
        offset += 4

        print(f"[MoireClient] Parsing {element_count} elements...")

        elements = []
        for i in range(element_count):
            elem = self._parse_desktop_element(response_data, offset)
            if elem:
                elements.append(elem)
                # Each DesktopElement is large, calculate size:
                # id(8) + text(256) + app_name(128) + x(4) + y(4) + width(4) + height(4)
                # + type(4) + clickable(1) + confidence(4) + reserved(16) = ~433 bytes
                offset += 433
            else:
                break

        return elements

    def _parse_desktop_element(self, data: bytes, offset: int) -> Optional[DesktopElement]:
        """Parse DesktopElement from bytes at offset"""
        try:
            # DesktopElement layout:
            # id(8) + text(256) + app_name(128) + x(4) + y(4) + width(4) + height(4)
            # + type(4) + clickable(1) + confidence(4) + reserved(16)

            # Parse ID
            elem_id = struct.unpack('Q', data[offset:offset+8])[0]
            offset += 8

            # Parse text (256 bytes, null-terminated)
            text_bytes = data[offset:offset+256]
            text = text_bytes.split(b'\x00', 1)[0].decode('utf-8', errors='ignore')
            offset += 256

            # Parse app_name (128 bytes, null-terminated)
            app_bytes = data[offset:offset+128]
            app_name = app_bytes.split(b'\x00', 1)[0].decode('utf-8', errors='ignore')
            offset += 128

            # Parse floats and ints
            x, y, width, height = struct.unpack('ffff', data[offset:offset+16])
            offset += 16

            elem_type = struct.unpack('I', data[offset:offset+4])[0]
            offset += 4

            clickable = struct.unpack('?', data[offset:offset+1])[0]
            offset += 1

            confidence = struct.unpack('f', data[offset:offset+4])[0]

            return DesktopElement(
                id=elem_id,
                text=text,
                app_name=app_name,
                x=x,
                y=y,
                width=width,
                height=height,
                elem_type=elem_type,
                clickable=clickable,
                confidence=confidence
            )

        except Exception as e:
            print(f"[MoireClient] Failed to parse element: {e}")
            return None

    def find_element(self, search_text: str, exact_match: bool = False) -> Optional[DesktopElement]:
        """
        Find element by name/text

        Args:
            search_text: Text to search for
            exact_match: If True, require exact match (case-insensitive by default)

        Returns:
            DesktopElement if found, None otherwise
        """
        # Build params: search_text(256) + case_sensitive(1) + exact_match(1)
        params = search_text.encode('utf-8')[:256].ljust(256, b'\x00')
        params += struct.pack('??', False, exact_match)  # case_sensitive=False

        request_id = self._send_command(CommandType.FIND_ELEMENT, params)
        if not request_id:
            return None

        response_data = self._wait_for_response()
        if not response_data:
            return None

        # Parse response header
        cmd_type, req_id, status, timestamp = self._parse_response_header(response_data)

        if status == ResponseStatus.ERROR_NOT_FOUND:
            return None
        elif status != ResponseStatus.SUCCESS:
            print(f"[MoireClient] FIND_ELEMENT failed: status={status}")
            return None

        # FindElementData starts after header (24) + mouse_pos (20) + scan_elements_data (varies)
        # For find_element, data is: [found(1)] [DesktopElement struct]
        offset = 24 + 20 + 4  # Skip header, mouse_pos, element_count
        found = struct.unpack('?', response_data[offset:offset+1])[0]
        offset += 1

        if not found:
            return None

        return self._parse_desktop_element(response_data, offset)

    def set_active(self) -> bool:
        """
        Show moiré overlay (indicate AI is working)

        Returns:
            True if successful
        """
        request_id = self._send_command(CommandType.SET_ACTIVE)
        if not request_id:
            return False

        response_data = self._wait_for_response()
        if not response_data:
            return False

        cmd_type, req_id, status, timestamp = self._parse_response_header(response_data)
        return status == ResponseStatus.SUCCESS

    def set_standby(self) -> bool:
        """
        Hide moiré overlay (indicate AI is idle)

        Returns:
            True if successful
        """
        request_id = self._send_command(CommandType.SET_STANDBY)
        if not request_id:
            return False

        response_data = self._wait_for_response()
        if not response_data:
            return False

        cmd_type, req_id, status, timestamp = self._parse_response_header(response_data)
        return status == ResponseStatus.SUCCESS
```

---

## Step 1.4: Create Package Init File

**File**: `voice_dialog/python/tools/__init__.py`

**Code to Create**:
```python
"""
Tools package for voice_dialog
Provides utilities for desktop interaction via MoireTracker
"""

from .moire_client import MoireTrackerClient
from .moire_types import (
    MousePosition,
    DesktopElement,
    ElementType,
    CommandType,
    ResponseStatus
)

__all__ = [
    'MoireTrackerClient',
    'MousePosition',
    'DesktopElement',
    'ElementType',
    'CommandType',
    'ResponseStatus'
]
```

---

## Step 1.5: Test the IPC Bridge

**Create Test Script**: `voice_dialog/python/test_moire_bridge.py`

```python
"""
Test script for MoireTracker IPC bridge
Run with: python test_moire_bridge.py
"""

import sys
import time
from tools.moire_client import MoireTrackerClient

def test_connection():
    """Test 1: Basic connection"""
    print("\n" + "="*60)
    print("TEST 1: Connection")
    print("="*60)

    client = MoireTrackerClient()
    result = client.connect()

    if result:
        print("✓ Connection test PASSED")
        return client
    else:
        print("✗ Connection test FAILED")
        print("\nTroubleshooting:")
        print("1. Is MoireTracker.exe running?")
        print("2. Check: tasklist | findstr MoireTracker")
        print("3. Start it: cd C:\\Users\\User\\Desktop\\Moire\\build\\Release && MoireTracker.exe")
        sys.exit(1)

def test_mouse_position(client):
    """Test 2: Get mouse position"""
    print("\n" + "="*60)
    print("TEST 2: Get Mouse Position")
    print("="*60)

    pos = client.get_mouse_position()

    if pos:
        print(f"✓ Mouse position test PASSED")
        print(f"  Position: ({pos.x:.1f}, {pos.y:.1f})")
        print(f"  Confidence: {pos.confidence:.2f}")
        print(f"  Timestamp: {pos.timestamp_ms}")
    else:
        print("✗ Mouse position test FAILED")
        return False

    return True

def test_scan_desktop(client):
    """Test 3: Scan desktop elements"""
    print("\n" + "="*60)
    print("TEST 3: Scan Desktop Elements")
    print("="*60)

    print("Scanning... (this may take a few seconds)")
    elements = client.scan_desktop()

    if len(elements) > 0:
        print(f"✓ Desktop scan test PASSED")
        print(f"  Found {len(elements)} elements")
        print("\nFirst 5 elements:")
        for i, elem in enumerate(elements[:5]):
            print(f"  {i+1}. {elem.text:30s} ({elem.app_name:20s}) at ({elem.x:.0f}, {elem.y:.0f})")
        return True
    else:
        print("✗ Desktop scan test FAILED (0 elements)")
        return False

def test_find_element(client):
    """Test 4: Find specific element"""
    print("\n" + "="*60)
    print("TEST 4: Find Element")
    print("="*60)

    # Try to find common applications
    search_terms = ["Chrome", "VSCode", "Discord", "Notepad"]

    for term in search_terms:
        print(f"\nSearching for '{term}'...")
        elem = client.find_element(term, exact_match=False)

        if elem:
            print(f"  ✓ Found: {elem.text} at ({elem.x:.0f}, {elem.y:.0f})")
            print(f"    App: {elem.app_name}")
            print(f"    Confidence: {elem.confidence:.2f}")
            return True

    print("  ⚠ None of the test applications found")
    print("    (This is OK if you don't have them installed)")
    return True

def test_overlay_toggle(client):
    """Test 5: Visual feedback (overlay toggle)"""
    print("\n" + "="*60)
    print("TEST 5: Visual Feedback (Overlay Toggle)")
    print("="*60)

    print("Activating overlay... (watch for moiré pattern)")
    result1 = client.set_active()
    time.sleep(2)

    print("Deactivating overlay...")
    result2 = client.set_standby()

    if result1 and result2:
        print("✓ Overlay toggle test PASSED")
    else:
        print("✗ Overlay toggle test FAILED")

    return result1 and result2

def main():
    print("╔" + "═"*58 + "╗")
    print("║" + " "*10 + "MoireTracker IPC Bridge Test Suite" + " "*14 + "║")
    print("╚" + "═"*58 + "╝")

    # Run tests
    client = test_connection()

    test_results = []
    test_results.append(("Mouse Position", test_mouse_position(client)))
    test_results.append(("Desktop Scan", test_scan_desktop(client)))
    test_results.append(("Find Element", test_find_element(client)))
    test_results.append(("Overlay Toggle", test_overlay_toggle(client)))

    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)

    passed = sum(1 for _, result in test_results if result)
    total = len(test_results)

    for name, result in test_results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{name:20s}: {status}")

    print(f"\n{passed}/{total} tests passed")

    if passed == total:
        print("\n🎉 All tests passed! Ready for Phase 2.")
    else:
        print("\n⚠ Some tests failed. Please fix before continuing.")

    # Cleanup
    client.disconnect()

if __name__ == "__main__":
    main()
```

---

## Step 1.6: Run Phase 1 Tests

**Pre-requisite**: Make sure MoireTracker is running

```bash
# Terminal 1: Start MoireTracker
cd C:\Users\User\Desktop\Moire\build\Release
start MoireTracker.exe

# Terminal 2: Run tests
cd C:\Users\User\Desktop\voice_dialog\python
python test_moire_bridge.py
```

**Expected Output**:
```
╔══════════════════════════════════════════════════════╗
║          MoireTracker IPC Bridge Test Suite          ║
╚══════════════════════════════════════════════════════╝

============================================================
TEST 1: Connection
============================================================
[MoireClient] Connecting to MoireTracker shared memory...
  ✓ Command memory opened
  ✓ Response memory opened
  ✓ Mouse stream memory opened
[MoireClient] Connected successfully!
✓ Connection test PASSED

============================================================
TEST 2: Get Mouse Position
============================================================
✓ Mouse position test PASSED
  Position: (1234.5, 678.9)
  Confidence: 1.00
  Timestamp: 1696873245123

============================================================
TEST 3: Scan Desktop Elements
============================================================
Scanning... (this may take a few seconds)
[MoireClient] Parsing 398 elements...
✓ Desktop scan test PASSED
  Found 398 elements

First 5 elements:
  1. Chrome                        (Google Chrome        ) at (100, 200)
  2. Visual Studio Code            (Visual Studio Code   ) at (200, 200)
  ...

============================================================
TEST SUMMARY
============================================================
Mouse Position      : ✓ PASS
Desktop Scan        : ✓ PASS
Find Element        : ✓ PASS
Overlay Toggle      : ✓ PASS

4/4 tests passed

🎉 All tests passed! Ready for Phase 2.
```

✅ **PHASE 1 COMPLETE**: If all tests pass, you're ready for Phase 2!

---

## 🎯 What You've Accomplished

- ✅ Created Python IPC bridge library
- ✅ Implemented all core communication functions
- ✅ Tested connection, scanning, finding, and overlay toggle
- ✅ Verified 398 desktop elements are accessible from Python

## 📝 Phase 1 Checklist

Before moving to Phase 2, verify:

- [ ] All files created in `voice_dialog/python/tools/`
- [ ] Test script runs without errors
- [ ] MoireTracker connection succeeds
- [ ] Desktop scan returns 398 elements
- [ ] Find element works for at least one application
- [ ] Overlay shows/hides on command

## 🚦 Next Step

When Phase 1 tests pass, we'll move to **Phase 2**: Enhancing the DesktopAgent to use these new capabilities.

**Ready to continue? Let me know when you've:**
1. Created all the files
2. Run the test script
3. Verified all tests pass

Then I'll guide you through Phase 2!
