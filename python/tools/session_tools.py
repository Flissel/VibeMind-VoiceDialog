"""
Voice Session Management Tools

Tools for managing the voice conversation session including:
- Session timeout handling
- Session restart
- Graceful session ending
- Session status checking

These tools help handle ElevenLabs session timeouts gracefully by allowing
the user or agent to manage session state.
"""

import sys
import os
import time
from pathlib import Path
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import Electron broadcast function from workspace_tools
from tools.workspace_tools import _broadcast_to_electron

# Session state tracking
_session_start_time: Optional[float] = None
_session_active: bool = False
_last_interaction_time: Optional[float] = None

# Configurable timeout (in seconds) - ElevenLabs default is ~10 minutes
SESSION_TIMEOUT_SECONDS = int(os.getenv("VOICE_SESSION_TIMEOUT", 540))  # 9 minutes default (before 10 min limit)
INACTIVITY_WARNING_SECONDS = int(os.getenv("VOICE_INACTIVITY_WARNING", 300))  # 5 minutes of inactivity


def mark_session_start():
    """Called when a voice session starts."""
    global _session_start_time, _session_active, _last_interaction_time
    _session_start_time = time.time()
    _session_active = True
    _last_interaction_time = time.time()
    logger.info("Voice session started")


def mark_interaction():
    """Called when user or agent speaks - resets inactivity timer."""
    global _last_interaction_time
    _last_interaction_time = time.time()


def mark_session_end():
    """Called when voice session ends."""
    global _session_active
    _session_active = False
    logger.info("Voice session ended")


def get_session_elapsed_seconds() -> float:
    """Get seconds elapsed since session start."""
    if _session_start_time is None:
        return 0
    return time.time() - _session_start_time


def get_inactivity_seconds() -> float:
    """Get seconds since last interaction."""
    if _last_interaction_time is None:
        return 0
    return time.time() - _last_interaction_time


# =============================================================================
# SESSION TOOLS
# =============================================================================

def check_session_status(params: Dict[str, Any]) -> str:
    """
    Check the current voice session status.
    
    Voice triggers: "How long have we been talking?", "Session status"
    
    Returns:
        str: Session status information
    """
    if not _session_active:
        return "No active voice session."
    
    elapsed = get_session_elapsed_seconds()
    inactivity = get_inactivity_seconds()
    
    elapsed_min = int(elapsed // 60)
    elapsed_sec = int(elapsed % 60)
    
    remaining = max(0, SESSION_TIMEOUT_SECONDS - elapsed)
    remaining_min = int(remaining // 60)
    
    status_parts = [
        f"Session active for {elapsed_min} minutes {elapsed_sec} seconds.",
        f"About {remaining_min} minutes remaining before timeout."
    ]
    
    if inactivity > INACTIVITY_WARNING_SECONDS / 2:
        status_parts.append(f"No recent activity for {int(inactivity // 60)} minutes.")
    
    return " ".join(status_parts)


def extend_session(params: Dict[str, Any]) -> str:
    """
    Acknowledge session continuation - prevents inactivity timeout.
    
    Voice triggers: "I'm still here", "Continue", "Keep going"
    
    This tool is called to indicate the user is still engaged.
    It resets the inactivity timer.
    
    Returns:
        str: Confirmation message
    """
    mark_interaction()
    
    elapsed = get_session_elapsed_seconds()
    remaining = max(0, SESSION_TIMEOUT_SECONDS - elapsed)
    remaining_min = int(remaining // 60)
    
    return f"Great! Session extended. About {remaining_min} minutes remaining."


def request_session_restart(params: Dict[str, Any]) -> str:
    """
    Request to restart the voice session (to reset the 10-minute timer).
    
    Voice triggers: "Restart the session", "Refresh voice", "Reset timer"
    
    This signals Electron to stop and restart the voice session,
    which resets the ElevenLabs 10-minute session limit.
    
    Args (via params):
        reason: Optional reason for restart
        
    Returns:
        str: Instruction to user that session will restart
    """
    reason = params.get("reason", "session timeout approaching")
    
    # Broadcast restart request to Electron
    _broadcast_to_electron({
        "type": "voice_restart_requested",
        "reason": reason,
        "elapsed_seconds": get_session_elapsed_seconds()
    })
    
    logger.info(f"Voice session restart requested: {reason}")
    
    return "I'll restart the voice session now. Just a moment..."


def end_session_gracefully(params: Dict[str, Any]) -> str:
    """
    End the voice session gracefully with a summary.
    
    Voice triggers: "Let's wrap up", "End session", "That's all for now"
    
    Args (via params):
        summary: Optional summary of what was discussed
        
    Returns:
        str: Farewell message
    """
    summary = params.get("summary", "")
    
    # Broadcast end request to Electron
    _broadcast_to_electron({
        "type": "voice_end_requested",
        "summary": summary,
        "elapsed_seconds": get_session_elapsed_seconds()
    })
    
    mark_session_end()
    
    if summary:
        return f"Session ended. Summary: {summary}. Talk to you later!"
    else:
        return "Session ended. Talk to you later!"


def check_timeout_warning(params: Dict[str, Any]) -> str:
    """
    Check if session is approaching timeout and warn user.
    
    This tool can be used by the agent proactively to check
    if a timeout warning should be issued.
    
    Returns:
        str: Warning message if timeout approaching, otherwise empty
    """
    if not _session_active:
        return ""
    
    elapsed = get_session_elapsed_seconds()
    remaining = SESSION_TIMEOUT_SECONDS - elapsed
    
    # Warning at 2 minutes remaining
    if remaining < 120 and remaining > 0:
        return f"Heads up! Only {int(remaining // 60)} minutes left in this session. Say 'restart session' to continue without interruption."
    
    # Warning at 1 minute remaining
    if remaining < 60 and remaining > 0:
        return "Less than a minute left! I'll restart the session automatically to keep us talking."
    
    return ""


def should_auto_restart() -> bool:
    """
    Check if session should auto-restart (for internal use).
    
    Returns True if session is active and near timeout.
    """
    if not _session_active:
        return False
    
    elapsed = get_session_elapsed_seconds()
    remaining = SESSION_TIMEOUT_SECONDS - elapsed
    
    return remaining < 30  # Auto-restart with 30 seconds remaining


# =============================================================================
# TOOL REGISTRY
# =============================================================================

SESSION_TOOLS = {
    "check_session_status": check_session_status,
    "extend_session": extend_session,
    "request_session_restart": request_session_restart,
    "end_session_gracefully": end_session_gracefully,
    "check_timeout_warning": check_timeout_warning,
}


def register_session_tools(tools_manager) -> None:
    """Register all session tools with the tools manager."""
    print("Registering session tools with observer...")
    for tool_name, tool_func in SESSION_TOOLS.items():
        try:
            tools_manager.register_with_observer(tool_name, tool_func)
            print(f"  - {tool_name}")
        except ValueError:
            print(f"  - {tool_name} (skipped - already registered)")


__all__ = [
    "check_session_status",
    "extend_session",
    "request_session_restart",
    "end_session_gracefully",
    "check_timeout_warning",
    "mark_session_start",
    "mark_interaction",
    "mark_session_end",
    "should_auto_restart",
    "SESSION_TOOLS",
    "register_session_tools",
]