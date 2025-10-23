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
    CLICK = 12
    CLICK_ELEMENT = 13
    SCAN_WINDOWS = 14
    FOCUS_WINDOW = 15
    CLOSE_WINDOW = 16
    RESIZE_WINDOW = 17
    GET_ACTIVE_WINDOW = 18
    CLICK_WINDOW = 19
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


@dataclass
class WindowData:
    """Window information"""
    hwnd: int
    title: str
    class_name: str
    process_name: str
    process_id: int
    left: int
    top: int
    right: int
    bottom: int
    is_visible: bool
    is_minimized: bool
    is_maximized: bool
    z_order: int

    @property
    def rect(self) -> tuple:
        """Get (left, top, right, bottom) tuple"""
        return (self.left, self.top, self.right, self.bottom)

    @property
    def width(self) -> int:
        """Get window width"""
        return self.right - self.left

    @property
    def height(self) -> int:
        """Get window height"""
        return self.bottom - self.top

    def __repr__(self) -> str:
        return f"WindowData('{self.title}', process='{self.process_name}', visible={self.is_visible})"
