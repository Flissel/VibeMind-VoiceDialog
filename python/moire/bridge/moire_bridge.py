"""
MoireBridge - VibeMind Integration Layer für MoireTracker Agent-Team

Stellt eine einfache API für ElevenLabs Client Tools bereit:
- execute_task(goal) - Führt komplexen Desktop-Task aus
- click_element(description) - Klickt auf beschriebenes Element
- type_text(text) - Tippt Text
- press_key(key) - Drückt Taste
- take_screenshot() - Screenshot für Analyse

Diese Bridge verwaltet den Orchestrator und die Agenten.
"""

import asyncio
import logging
import time
import base64
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

# Import from parent package
from ..agents.orchestrator_v2 import OrchestratorV2, get_orchestrator
from ..agents.interaction import InteractionAgent, get_interaction_agent
from ..agents.reasoning import ReasoningAgent, get_reasoning_agent
from ..core.event_queue import TaskStatus

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class TaskResult:
    """Ergebnis eines Desktop-Tasks."""
    success: bool
    message: str
    task_id: str
    actions_executed: int
    duration_seconds: float
    error: Optional[str] = None
    screenshot_base64: Optional[str] = None


@dataclass
class ActionResult:
    """Ergebnis einer einzelnen Desktop-Aktion."""
    success: bool
    message: str
    action_type: str
    duration_ms: float
    error: Optional[str] = None


class MoireBridge:
    """
    Bridge zwischen VibeMind und MoireTracker Agent-Team.
    
    Bietet eine einfache, synchrone API die von ElevenLabs Client Tools
    aufgerufen werden kann.
    
    Usage:
        bridge = MoireBridge()
        await bridge.start()
        
        # Im ElevenLabs Client Tool:
        result = await bridge.execute_task("Öffne Word und erstelle ein neues Dokument")
        result = await bridge.click_element("Speichern Button")
        result = await bridge.type_text("Hello World")
        result = await bridge.press_key("ctrl+s")
    """
    
    def __init__(self, auto_start: bool = False):
        """
        Initialisiert die Bridge.
        
        Args:
            auto_start: Wenn True, startet Orchestrator automatisch
        """
        self._orchestrator: Optional[OrchestratorV2] = None
        self._interaction: Optional[InteractionAgent] = None
        self._reasoning: Optional[ReasoningAgent] = None
        self._started = False
        self._start_time = time.time()
        
        logger.info("MoireBridge initialized")
        
        if auto_start:
            # Schedule start for later
            asyncio.create_task(self.start())
    
    async def start(self):
        """Startet die Bridge und den Orchestrator."""
        if self._started:
            logger.warning("MoireBridge already started")
            return
        
        logger.info("Starting MoireBridge...")
        
        # Initialize agents
        self._orchestrator = get_orchestrator()
        self._interaction = get_interaction_agent()
        self._reasoning = get_reasoning_agent()
        
        # Start orchestrator
        await self._orchestrator.start()
        
        self._started = True
        self._start_time = time.time()
        
        logger.info("MoireBridge started successfully")
    
    async def stop(self):
        """Stoppt die Bridge und den Orchestrator."""
        if not self._started:
            return
        
        logger.info("Stopping MoireBridge...")
        
        if self._orchestrator:
            await self._orchestrator.stop()
        
        self._started = False
        logger.info("MoireBridge stopped")
    
    def is_ready(self) -> bool:
        """Prüft ob die Bridge bereit ist."""
        return self._started and self._orchestrator is not None
    
    # ==================== High-Level API ====================
    
    async def execute_task(
        self,
        goal: str,
        timeout: float = 120.0
    ) -> TaskResult:
        """
        Führt einen komplexen Desktop-Task aus.
        
        Der ReasoningAgent analysiert das Ziel und plant mehrere Aktionen,
        die dann sequentiell ausgeführt werden.
        
        Args:
            goal: Beschreibung des Ziels (z.B. "Öffne Word und erstelle ein neues Dokument")
            timeout: Maximale Ausführungszeit in Sekunden
        
        Returns:
            TaskResult mit Erfolg/Misserfolg und Details
        """
        if not self.is_ready():
            return TaskResult(
                success=False,
                message="MoireBridge not started. Call start() first.",
                task_id="",
                actions_executed=0,
                duration_seconds=0,
                error="Bridge not ready"
            )
        
        start_time = time.time()
        
        try:
            logger.info(f"Executing task: {goal}")
            
            task = await self._orchestrator.execute_task_and_wait(
                goal=goal,
                timeout=timeout
            )
            
            duration = time.time() - start_time
            
            if task.status == TaskStatus.COMPLETED:
                # Take final screenshot
                screenshot_b64 = None
                success, screenshot = await self._interaction.take_screenshot()
                if success and screenshot:
                    screenshot_b64 = base64.b64encode(screenshot).decode('utf-8')
                
                return TaskResult(
                    success=True,
                    message=f"Task erfolgreich abgeschlossen: {goal}",
                    task_id=task.id,
                    actions_executed=len(task.actions),
                    duration_seconds=duration,
                    screenshot_base64=screenshot_b64
                )
            else:
                return TaskResult(
                    success=False,
                    message=f"Task fehlgeschlagen: {task.error or 'Unbekannter Fehler'}",
                    task_id=task.id,
                    actions_executed=len([a for a in task.actions if a.status.value == 'completed']),
                    duration_seconds=duration,
                    error=task.error
                )
        
        except asyncio.TimeoutError:
            return TaskResult(
                success=False,
                message=f"Task Timeout nach {timeout}s",
                task_id="",
                actions_executed=0,
                duration_seconds=time.time() - start_time,
                error="Timeout"
            )
        
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            return TaskResult(
                success=False,
                message=f"Fehler bei Task-Ausführung: {str(e)}",
                task_id="",
                actions_executed=0,
                duration_seconds=time.time() - start_time,
                error=str(e)
            )
    
    async def click_element(self, description: str) -> ActionResult:
        """
        Klickt auf ein UI-Element basierend auf Beschreibung.
        
        Verwendet Vision Agent um das Element zu finden und dann zu klicken.
        
        Args:
            description: Beschreibung des Elements (z.B. "Speichern Button", "Datei Menü")
        
        Returns:
            ActionResult
        """
        if not self.is_ready():
            return ActionResult(
                success=False,
                message="Bridge not ready",
                action_type="click",
                duration_ms=0,
                error="Bridge not started"
            )
        
        start_time = time.time()
        
        try:
            # Screenshot für Vision
            success, screenshot = await self._interaction.take_screenshot()
            if not success or not screenshot:
                return ActionResult(
                    success=False,
                    message="Screenshot fehlgeschlagen",
                    action_type="click",
                    duration_ms=0,
                    error="Could not take screenshot"
                )
            
            # Vision Agent findet Element
            location = await self._reasoning.find_element_for_click(
                screenshot,
                description
            )
            
            if location is None:
                return ActionResult(
                    success=False,
                    message=f"Element nicht gefunden: {description}",
                    action_type="click",
                    duration_ms=(time.time() - start_time) * 1000,
                    error="Element not found by Vision"
                )
            
            # Klick ausführen
            result = await self._interaction.click(
                location['x'],
                location['y']
            )
            
            duration_ms = (time.time() - start_time) * 1000
            
            if result.success:
                return ActionResult(
                    success=True,
                    message=f"Klick auf '{description}' bei ({location['x']}, {location['y']})",
                    action_type="click",
                    duration_ms=duration_ms
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Klick fehlgeschlagen: {result.error}",
                    action_type="click",
                    duration_ms=duration_ms,
                    error=result.error
                )
        
        except Exception as e:
            logger.error(f"Click element failed: {e}")
            return ActionResult(
                success=False,
                message=f"Fehler: {str(e)}",
                action_type="click",
                duration_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    async def type_text(self, text: str) -> ActionResult:
        """
        Tippt Text ein.
        
        Args:
            text: Der zu tippende Text
        
        Returns:
            ActionResult
        """
        if not self.is_ready():
            return ActionResult(
                success=False,
                message="Bridge not ready",
                action_type="type",
                duration_ms=0,
                error="Bridge not started"
            )
        
        try:
            result = await self._interaction.type_text(text)
            
            if result.success:
                return ActionResult(
                    success=True,
                    message=f"Text eingegeben: '{text[:50]}{'...' if len(text) > 50 else ''}'",
                    action_type="type",
                    duration_ms=result.duration_ms
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Texteingabe fehlgeschlagen: {result.error}",
                    action_type="type",
                    duration_ms=result.duration_ms,
                    error=result.error
                )
        
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return ActionResult(
                success=False,
                message=f"Fehler: {str(e)}",
                action_type="type",
                duration_ms=0,
                error=str(e)
            )
    
    async def press_key(self, key: str) -> ActionResult:
        """
        Drückt eine Taste oder Tastenkombination.
        
        Args:
            key: Taste (z.B. "enter", "tab", "escape", "ctrl+s", "alt+f4")
        
        Returns:
            ActionResult
        """
        if not self.is_ready():
            return ActionResult(
                success=False,
                message="Bridge not ready",
                action_type="press_key",
                duration_ms=0,
                error="Bridge not started"
            )
        
        try:
            result = await self._interaction.press_key(key)
            
            if result.success:
                return ActionResult(
                    success=True,
                    message=f"Taste gedrückt: {key}",
                    action_type="press_key",
                    duration_ms=result.duration_ms
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Tastendruck fehlgeschlagen: {result.error}",
                    action_type="press_key",
                    duration_ms=result.duration_ms,
                    error=result.error
                )
        
        except Exception as e:
            logger.error(f"Press key failed: {e}")
            return ActionResult(
                success=False,
                message=f"Fehler: {str(e)}",
                action_type="press_key",
                duration_ms=0,
                error=str(e)
            )
    
    async def take_screenshot(self) -> Tuple[bool, Optional[str]]:
        """
        Macht einen Screenshot und gibt ihn als Base64 zurück.
        
        Returns:
            Tuple (success, base64_screenshot)
        """
        if not self.is_ready():
            return False, None
        
        try:
            success, screenshot = await self._interaction.take_screenshot()
            
            if success and screenshot:
                b64 = base64.b64encode(screenshot).decode('utf-8')
                return True, b64
            
            return False, None
        
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False, None
    
    async def scroll(self, direction: str = "down", amount: int = 3) -> ActionResult:
        """
        Scrollt in die angegebene Richtung.
        
        Args:
            direction: "up" oder "down"
            amount: Anzahl Scroll-Clicks
        
        Returns:
            ActionResult
        """
        if not self.is_ready():
            return ActionResult(
                success=False,
                message="Bridge not ready",
                action_type="scroll",
                duration_ms=0,
                error="Bridge not started"
            )
        
        try:
            clicks = amount if direction == "up" else -amount
            result = await self._interaction.scroll(clicks)
            
            if result.success:
                return ActionResult(
                    success=True,
                    message=f"Gescrollt: {direction} ({amount} Clicks)",
                    action_type="scroll",
                    duration_ms=result.duration_ms
                )
            else:
                return ActionResult(
                    success=False,
                    message=f"Scroll fehlgeschlagen: {result.error}",
                    action_type="scroll",
                    duration_ms=result.duration_ms,
                    error=result.error
                )
        
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return ActionResult(
                success=False,
                message=f"Fehler: {str(e)}",
                action_type="scroll",
                duration_ms=0,
                error=str(e)
            )
    
    # ==================== Status API ====================
    
    def get_status(self) -> Dict[str, Any]:
        """Gibt Status der Bridge zurück."""
        return {
            "started": self._started,
            "uptime_seconds": time.time() - self._start_time if self._started else 0,
            "orchestrator_status": self._orchestrator.get_status().__dict__ if self._orchestrator else None,
            "pyautogui_available": self._interaction.is_available() if self._interaction else False
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken zurück."""
        if not self._orchestrator:
            return {"error": "Not started"}
        
        return self._orchestrator.get_stats()


# Singleton
_bridge_instance: Optional[MoireBridge] = None


def get_moire_bridge() -> MoireBridge:
    """Gibt Singleton-Instanz der MoireBridge zurück."""
    global _bridge_instance
    if _bridge_instance is None:
        _bridge_instance = MoireBridge()
    return _bridge_instance


def reset_moire_bridge():
    """Setzt MoireBridge zurück."""
    global _bridge_instance
    if _bridge_instance:
        asyncio.create_task(_bridge_instance.stop())
    _bridge_instance = None


async def test_bridge():
    """Test-Funktion für MoireBridge."""
    bridge = get_moire_bridge()
    
    print("Starting MoireBridge...")
    await bridge.start()
    
    print(f"Status: {bridge.get_status()}")
    
    # Test screenshot
    success, screenshot = await bridge.take_screenshot()
    print(f"Screenshot: {success}, {len(screenshot) if screenshot else 0} chars")
    
    # Test press key
    result = await bridge.press_key("win")
    print(f"Press Win: {result}")
    
    await asyncio.sleep(1)
    
    result = await bridge.press_key("escape")
    print(f"Press Escape: {result}")
    
    await bridge.stop()


if __name__ == "__main__":
    asyncio.run(test_bridge())