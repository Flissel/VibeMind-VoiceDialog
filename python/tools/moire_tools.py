"""
Moire Tools - BACKWARD COMPATIBILITY STUB

Real implementation migrated to: spaces/desktop/tools/moire_tools.py
This file re-exports for backward compatibility.
"""

import logging

logger = logging.getLogger(__name__)

from spaces.desktop.tools.moire_tools import (
    moire_scan,
    moire_find_element,
    moire_get_ui_context,
    MoireServerClient,
    get_moire_client,
    MOIRE_TOOLS,
    register_moire_tools,
    UIElement,
    ScanResult,
)

__all__ = [
    "moire_scan",
    "moire_find_element",
    "moire_get_ui_context",
    "MoireServerClient",
    "get_moire_client",
    "MOIRE_TOOLS",
    "register_moire_tools",
    "UIElement",
    "ScanResult",
]
