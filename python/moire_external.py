"""
MoireTracker v2 External Bridge

Diese Datei verbindet VibeMind mit dem externen MoireTracker v2 Projekt.
Statt den Code zu kopieren, wird das Original direkt importiert.

Pfad zum Original: C:/Users/User/Desktop/Moire_tracker_v1/MoireTracker_v2/python
"""

import sys
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Path zum externen MoireTracker v2 Projekt
MOIRE_TRACKER_PATH = Path(r"C:\Users\User\Desktop\Moire_tracker_v1\MoireTracker_v2\python")

# Global instances
_orchestrator = None
_interaction_agent = None
_vision_agent = None
_running = False


@dataclass
class TaskResult:
    """Ergebnis eines Desktop-Tasks."""
    success: bool
    message: str
    task_id: str = ""
    actions_executed: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


@dataclass
class ActionResult:
    """Ergebnis einer einzelnen Aktion."""
    success: bool
    message: str
    action_type: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None


def _setup_imports():
    """Fügt das MoireTracker v2 Projekt zum Python-Pfad hinzu."""
    if str(MOIRE_TRACKER_PATH) not in sys.path:
        sys.path.insert(0, str(MOIRE_TRACKER_PATH))
        logger.info(f"Added MoireTracker v2 to path: {MOIRE_TRACKER_PATH}")


async def initialize() -> bool:
    """
    Initialisiert das MoireTracker v2 System.
    
    Returns:
        bool: True wenn erfolgreich
    """
    global _orchestrator, _interaction_agent, _vision_agent, _running
    
    if _running:
        logger.info("MoireTracker already running")
        return True
    
    _setup_imports()
    
    try:
        # Import MoireTracker components
        from agents.orchestrator_v2 import get_orchestrator_v2
        from agents.interaction import get_interaction_agent
        from agents.vision_agent import get_vision_agent
        from core.event_queue import TaskStatus
        
        # Initialize
        _orchestrator = get_orchestrator_v2()
        _interaction_agent = get_interaction_agent()
        _vision_agent = get_vision_agent()
        
        # Wire up
        _orchestrator.set_interaction_agent(_interaction_agent)
        
        # Note: We skip MoireServer connection - use PyAutoGUI directly
        
        # Start orchestrator
        await _orchestrator.start()
        _running = True
        
        logger.info("✓ MoireTracker v2 initialized successfully")
        return True
        
    except ImportError as e:
        logger.error(f"Failed to import MoireTracker v2: {e}")
        logger.error(f"Make sure {MOIRE_TRACKER_PATH} exists and has the required files")
        return False
    except Exception as e:
        logger.error(f"Failed to initialize MoireTracker v2: {e}")
        return False


async def shutdown():
    """Beendet das MoireTracker v2 System."""
    global _orchestrator, _running
    
    if not _running:
        return
    
    try:
        from agents.orchestrator_v2 import shutdown_orchestrator
        await shutdown_orchestrator()
        _running = False
        logger.info("MoireTracker v2 shut down")
    except Exception as e:
        logger.error(f"Error shutting down: {e}")


async def execute_task(goal: str, timeout: float = 120.0) -> TaskResult:
    """
    Führt einen komplexen Desktop-Task aus.
    
    Args:
        goal: Beschreibung des Tasks
        timeout: Timeout in Sekunden
        
    Returns:
        TaskResult mit Ergebnis
    """
    import time
    start_time = time.time()
    
    if not _running:
        if not await initialize():
            return TaskResult(
                success=False,
                message="Failed to initialize MoireTracker",
                error="Initialization failed"
            )
    
    try:
        from core.event_queue import TaskStatus
        
        result_task = await _orchestrator.execute_task(goal)
        duration = time.time() - start_time
        
        if result_task.status == TaskStatus.COMPLETED:
            return TaskResult(
                success=True,
                message=f"Task '{goal}' completed",
                task_id=result_task.id,
                actions_executed=len(result_task.actions),
                duration_seconds=duration
            )
        else:
            return TaskResult(
                success=False,
                message=f"Task failed: {result_task.error}",
                task_id=result_task.id,
                error=result_task.error,
                duration_seconds=duration
            )
            
    except Exception as e:
        return TaskResult(
            success=False,
            message=f"Error executing task: {str(e)}",
            error=str(e),
            duration_seconds=time.time() - start_time
        )


async def press_key(key: str) -> ActionResult:
    """Drückt eine Taste."""
    import time
    start_time = time.time()
    
    if not _running:
        if not await initialize():
            return ActionResult(success=False, message="Not initialized", error="Init failed")
    
    try:
        # Benutze die direkte Methode des InteractionAgents
        result = await _interaction_agent.press_key(key)
        duration_ms = (time.time() - start_time) * 1000
        
        return ActionResult(
            success=result.get('success', False),
            message=f"Pressed key: {key}",
            action_type="press_key",
            duration_ms=duration_ms
        )
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Failed to press key: {e}",
            action_type="press_key",
            error=str(e)
        )


async def type_text(text: str) -> ActionResult:
    """Tippt Text ein."""
    import time
    start_time = time.time()
    
    if not _running:
        if not await initialize():
            return ActionResult(success=False, message="Not initialized", error="Init failed")
    
    try:
        # Benutze die direkte Methode des InteractionAgents
        result = await _interaction_agent.type_text(text)
        duration_ms = (time.time() - start_time) * 1000
        
        return ActionResult(
            success=result.get('success', False),
            message=f"Typed {len(text)} characters",
            action_type="type_text", 
            duration_ms=duration_ms
        )
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Failed to type: {e}",
            action_type="type_text",
            error=str(e)
        )


async def click(x: int, y: int, button: str = "left") -> ActionResult:
    """Klickt an Position."""
    import time
    start_time = time.time()
    
    if not _running:
        if not await initialize():
            return ActionResult(success=False, message="Not initialized", error="Init failed")
    
    try:
        # Import MouseButton enum
        from agents.interaction import MouseButton
        
        # Konvertiere button string zu enum
        mouse_button = MouseButton.LEFT
        if button.lower() == "right":
            mouse_button = MouseButton.RIGHT
        elif button.lower() == "middle":
            mouse_button = MouseButton.MIDDLE
        
        # Benutze die direkte Methode - target als Tuple
        result = await _interaction_agent.click(target=(x, y), button=mouse_button)
        duration_ms = (time.time() - start_time) * 1000
        
        return ActionResult(
            success=result.get('success', False),
            message=f"Clicked at ({x}, {y})",
            action_type="click",
            duration_ms=duration_ms
        )
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Failed to click: {e}",
            action_type="click",
            error=str(e)
        )


async def take_screenshot() -> tuple:
    """Macht einen Screenshot."""
    if not _running:
        if not await initialize():
            return False, None
    
    try:
        # Screenshots kommen vom VisionAgent
        if _vision_agent and hasattr(_vision_agent, 'take_screenshot'):
            screenshot_b64 = await _vision_agent.take_screenshot()
            return True, screenshot_b64
        else:
            # Fallback: PyAutoGUI direkt
            import pyautogui
            import io
            import base64
            
            screenshot = pyautogui.screenshot()
            buffer = io.BytesIO()
            screenshot.save(buffer, format='PNG')
            screenshot_b64 = base64.b64encode(buffer.getvalue()).decode()
            return True, screenshot_b64
            
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return False, None


async def scroll(direction: str = "down", amount: int = 3) -> ActionResult:
    """Scrollt die Seite."""
    import time
    start_time = time.time()
    
    if not _running:
        if not await initialize():
            return ActionResult(success=False, message="Not initialized", error="Init failed")
    
    try:
        # Import ScrollDirection enum
        from agents.interaction import ScrollDirection
        
        # Benutze die direkte Methode
        scroll_dir = ScrollDirection.DOWN if direction.lower() == "down" else ScrollDirection.UP
        result = await _interaction_agent.scroll(direction=scroll_dir, amount=amount)
        duration_ms = (time.time() - start_time) * 1000
        
        return ActionResult(
            success=result.get('success', False),
            message=f"Scrolled {direction} by {amount}",
            action_type="scroll",
            duration_ms=duration_ms
        )
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Failed to scroll: {e}",
            action_type="scroll",
            error=str(e)
        )


async def hotkey(*keys: str) -> ActionResult:
    """Drückt Tastenkombination (z.B. ctrl+c, alt+tab)."""
    import time
    start_time = time.time()
    
    if not _running:
        if not await initialize():
            return ActionResult(success=False, message="Not initialized", error="Init failed")
    
    try:
        result = await _interaction_agent.hotkey(*keys)
        duration_ms = (time.time() - start_time) * 1000
        
        key_combo = '+'.join(keys)
        return ActionResult(
            success=result.get('success', False),
            message=f"Pressed hotkey: {key_combo}",
            action_type="hotkey",
            duration_ms=duration_ms
        )
    except Exception as e:
        return ActionResult(
            success=False,
            message=f"Failed to press hotkey: {e}",
            action_type="hotkey",
            error=str(e)
        )


def get_status() -> Dict[str, Any]:
    """Gibt den Status des Systems zurück."""
    if not _running or not _orchestrator:
        return {
            "running": False,
            "orchestrator": None,
            "interaction_agent": False,
            "vision_agent": False
        }
    
    try:
        status = _orchestrator.get_status()
        status["vision_agent"] = _vision_agent is not None
        return status
    except:
        return {
            "running": _running,
            "vision_agent": _vision_agent is not None
        }


# ==================== Test ====================

async def test():
    """Test-Funktion."""
    print("Testing MoireTracker v2 External Bridge...")
    
    # Initialize
    success = await initialize()
    print(f"Initialize: {'✓' if success else '✗'}")
    
    if not success:
        print("Cannot continue without initialization")
        return
    
    # Test press_key
    result = await press_key("win")
    print(f"Press Win: {'✓' if result.success else '✗'}")
    
    await asyncio.sleep(1)
    
    result = await press_key("escape")
    print(f"Press Escape: {'✓' if result.success else '✗'}")
    
    # Test screenshot
    success, screenshot = await take_screenshot()
    print(f"Screenshot: {'✓' if success else '✗'}")
    if screenshot:
        print(f"  Screenshot size: {len(screenshot)} bytes")
    
    # Shutdown
    await shutdown()
    print("Test completed")


if __name__ == "__main__":
    asyncio.run(test())