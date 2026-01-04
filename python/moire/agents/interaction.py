"""
Interaction Agent - Desktop-Automation via PyAutoGUI

Verantwortlich für:
- Maus-Klicks (links, rechts, doppelt)
- Tastatureingaben (Tippen, Hotkeys)
- Mausbewegungen und Drag&Drop
- Scrollen
- Screenshot-Aufnahme

Portiert von MoireTracker v2 für VibeMind Integration.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, Tuple, List
from dataclasses import dataclass

# PyAutoGUI Import
try:
    import pyautogui
    # Safety settings
    pyautogui.FAILSAFE = True  # Move to corner to abort
    pyautogui.PAUSE = 0.1  # Small pause between actions
    HAS_PYAUTOGUI = True
except ImportError:
    HAS_PYAUTOGUI = False
    pyautogui = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    """Ergebnis einer Interaktions-Aktion."""
    success: bool
    action_type: str
    params: Dict[str, Any]
    duration_ms: float
    error: Optional[str] = None
    screenshot_after: Optional[bytes] = None


class InteractionAgent:
    """
    Interaction Agent - Führt Desktop-Aktionen via PyAutoGUI aus.
    
    Unterstützte Aktionen:
    - click(x, y, button='left', clicks=1)
    - double_click(x, y)
    - right_click(x, y)
    - type_text(text, interval=0.02)
    - press_key(key)
    - hotkey(*keys)
    - scroll(clicks, x=None, y=None)
    - move_to(x, y, duration=0.25)
    - drag(x, y, duration=0.5)
    - wait(duration)
    """
    
    def __init__(self, typing_speed: float = 0.02):
        """
        Initialisiert den Interaction Agent.
        
        Args:
            typing_speed: Sekunden zwischen Tastendrücken beim Tippen
        """
        self.typing_speed = typing_speed
        self._action_counter = 0
        
        if not HAS_PYAUTOGUI:
            logger.error("PyAutoGUI not installed! pip install pyautogui")
        else:
            logger.info("InteractionAgent initialized with PyAutoGUI")
    
    def is_available(self) -> bool:
        """Prüft ob PyAutoGUI verfügbar ist."""
        return HAS_PYAUTOGUI
    
    # ==================== Primary Actions ====================
    
    async def click(
        self,
        x: int,
        y: int,
        button: str = 'left',
        clicks: int = 1
    ) -> ActionResult:
        """
        Klickt an Position (x, y).
        
        Args:
            x: X-Koordinate
            y: Y-Koordinate
            button: 'left', 'right', 'middle'
            clicks: Anzahl Klicks (1 oder 2 für Doppelklick)
        """
        start = time.time()
        
        if not HAS_PYAUTOGUI:
            return ActionResult(
                success=False,
                action_type="click",
                params={"x": x, "y": y, "button": button},
                duration_ms=0,
                error="PyAutoGUI not available"
            )
        
        try:
            await asyncio.to_thread(
                pyautogui.click,
                x=x, y=y,
                button=button,
                clicks=clicks
            )
            
            duration = (time.time() - start) * 1000
            logger.info(f"Click at ({x}, {y}) - {button} button")
            
            return ActionResult(
                success=True,
                action_type="click",
                params={"x": x, "y": y, "button": button, "clicks": clicks},
                duration_ms=duration
            )
        
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return ActionResult(
                success=False,
                action_type="click",
                params={"x": x, "y": y, "button": button},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def double_click(self, x: int, y: int) -> ActionResult:
        """Doppelklick an Position."""
        return await self.click(x, y, clicks=2)
    
    async def right_click(self, x: int, y: int) -> ActionResult:
        """Rechtsklick an Position."""
        return await self.click(x, y, button='right')
    
    async def type_text(
        self,
        text: str,
        interval: Optional[float] = None
    ) -> ActionResult:
        """
        Tippt Text ein.
        
        Args:
            text: Zu tippender Text
            interval: Sekunden zwischen Zeichen (default: self.typing_speed)
        """
        start = time.time()
        interval = interval or self.typing_speed
        
        if not HAS_PYAUTOGUI:
            return ActionResult(
                success=False,
                action_type="type",
                params={"text": text[:50]},
                duration_ms=0,
                error="PyAutoGUI not available"
            )
        
        try:
            # Use write for ASCII, typewrite supports unicode
            await asyncio.to_thread(
                pyautogui.write,
                text,
                interval=interval
            )
            
            duration = (time.time() - start) * 1000
            logger.info(f"Typed {len(text)} characters")
            
            return ActionResult(
                success=True,
                action_type="type",
                params={"text": text[:50], "length": len(text)},
                duration_ms=duration
            )
        
        except Exception as e:
            logger.error(f"Type failed: {e}")
            return ActionResult(
                success=False,
                action_type="type",
                params={"text": text[:50]},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def press_key(self, key: str) -> ActionResult:
        """
        Drückt eine Taste.
        
        Args:
            key: Taste (z.B. 'enter', 'tab', 'escape', 'win', 'f1', etc.)
                 Oder Kombination wie 'ctrl+c', 'alt+tab'
        """
        start = time.time()
        
        if not HAS_PYAUTOGUI:
            return ActionResult(
                success=False,
                action_type="press_key",
                params={"key": key},
                duration_ms=0,
                error="PyAutoGUI not available"
            )
        
        try:
            # Check for key combination
            if '+' in key:
                keys = key.split('+')
                await asyncio.to_thread(pyautogui.hotkey, *keys)
            else:
                await asyncio.to_thread(pyautogui.press, key)
            
            duration = (time.time() - start) * 1000
            logger.info(f"Pressed key: {key}")
            
            return ActionResult(
                success=True,
                action_type="press_key",
                params={"key": key},
                duration_ms=duration
            )
        
        except Exception as e:
            logger.error(f"Press key failed: {e}")
            return ActionResult(
                success=False,
                action_type="press_key",
                params={"key": key},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def hotkey(self, *keys: str) -> ActionResult:
        """
        Drückt eine Tastenkombination.
        
        Args:
            *keys: Tasten (z.B. 'ctrl', 'c' für Ctrl+C)
        """
        start = time.time()
        
        if not HAS_PYAUTOGUI:
            return ActionResult(
                success=False,
                action_type="hotkey",
                params={"keys": keys},
                duration_ms=0,
                error="PyAutoGUI not available"
            )
        
        try:
            await asyncio.to_thread(pyautogui.hotkey, *keys)
            
            duration = (time.time() - start) * 1000
            logger.info(f"Hotkey: {'+'.join(keys)}")
            
            return ActionResult(
                success=True,
                action_type="hotkey",
                params={"keys": list(keys)},
                duration_ms=duration
            )
        
        except Exception as e:
            logger.error(f"Hotkey failed: {e}")
            return ActionResult(
                success=False,
                action_type="hotkey",
                params={"keys": list(keys)},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def scroll(
        self,
        clicks: int,
        x: Optional[int] = None,
        y: Optional[int] = None
    ) -> ActionResult:
        """
        Scrollt am angegebenen Ort.
        
        Args:
            clicks: Positive Werte = nach oben, negative = nach unten
            x, y: Optional Position zum Scrollen
        """
        start = time.time()
        
        if not HAS_PYAUTOGUI:
            return ActionResult(
                success=False,
                action_type="scroll",
                params={"clicks": clicks},
                duration_ms=0,
                error="PyAutoGUI not available"
            )
        
        try:
            await asyncio.to_thread(
                pyautogui.scroll,
                clicks,
                x=x, y=y
            )
            
            duration = (time.time() - start) * 1000
            direction = "up" if clicks > 0 else "down"
            logger.info(f"Scrolled {direction} {abs(clicks)} clicks")
            
            return ActionResult(
                success=True,
                action_type="scroll",
                params={"clicks": clicks, "x": x, "y": y},
                duration_ms=duration
            )
        
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return ActionResult(
                success=False,
                action_type="scroll",
                params={"clicks": clicks},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def move_to(
        self,
        x: int,
        y: int,
        duration: float = 0.25
    ) -> ActionResult:
        """
        Bewegt die Maus zu Position.
        
        Args:
            x, y: Zielposition
            duration: Dauer der Bewegung in Sekunden
        """
        start = time.time()
        
        if not HAS_PYAUTOGUI:
            return ActionResult(
                success=False,
                action_type="move_to",
                params={"x": x, "y": y},
                duration_ms=0,
                error="PyAutoGUI not available"
            )
        
        try:
            await asyncio.to_thread(
                pyautogui.moveTo,
                x, y,
                duration=duration
            )
            
            duration_ms = (time.time() - start) * 1000
            logger.info(f"Moved to ({x}, {y})")
            
            return ActionResult(
                success=True,
                action_type="move_to",
                params={"x": x, "y": y, "duration": duration},
                duration_ms=duration_ms
            )
        
        except Exception as e:
            logger.error(f"Move failed: {e}")
            return ActionResult(
                success=False,
                action_type="move_to",
                params={"x": x, "y": y},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def drag(
        self,
        x: int,
        y: int,
        duration: float = 0.5,
        button: str = 'left'
    ) -> ActionResult:
        """
        Drag zur Position.
        
        Args:
            x, y: Zielposition
            duration: Dauer in Sekunden
            button: Welche Maustaste halten
        """
        start = time.time()
        
        if not HAS_PYAUTOGUI:
            return ActionResult(
                success=False,
                action_type="drag",
                params={"x": x, "y": y},
                duration_ms=0,
                error="PyAutoGUI not available"
            )
        
        try:
            await asyncio.to_thread(
                pyautogui.drag,
                x, y,
                duration=duration,
                button=button
            )
            
            duration_ms = (time.time() - start) * 1000
            logger.info(f"Dragged to ({x}, {y})")
            
            return ActionResult(
                success=True,
                action_type="drag",
                params={"x": x, "y": y, "duration": duration},
                duration_ms=duration_ms
            )
        
        except Exception as e:
            logger.error(f"Drag failed: {e}")
            return ActionResult(
                success=False,
                action_type="drag",
                params={"x": x, "y": y},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def wait(self, duration: float) -> ActionResult:
        """
        Wartet eine bestimmte Zeit.
        
        Args:
            duration: Sekunden zu warten
        """
        start = time.time()
        
        await asyncio.sleep(duration)
        
        return ActionResult(
            success=True,
            action_type="wait",
            params={"duration": duration},
            duration_ms=(time.time() - start) * 1000
        )
    
    # ==================== Advanced Actions ====================
    
    async def select_text(
        self,
        start_x: int,
        start_y: int,
        end_x: int,
        end_y: int
    ) -> ActionResult:
        """
        Selektiert Text durch Klicken und Ziehen.
        """
        start = time.time()
        
        try:
            # Click at start
            await self.click(start_x, start_y)
            await asyncio.sleep(0.1)
            
            # Hold shift and click at end
            await asyncio.to_thread(pyautogui.keyDown, 'shift')
            await self.click(end_x, end_y)
            await asyncio.to_thread(pyautogui.keyUp, 'shift')
            
            return ActionResult(
                success=True,
                action_type="select_text",
                params={
                    "start": (start_x, start_y),
                    "end": (end_x, end_y)
                },
                duration_ms=(time.time() - start) * 1000
            )
        
        except Exception as e:
            logger.error(f"Select text failed: {e}")
            return ActionResult(
                success=False,
                action_type="select_text",
                params={
                    "start": (start_x, start_y),
                    "end": (end_x, end_y)
                },
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def replace_text(
        self,
        new_text: str
    ) -> ActionResult:
        """
        Ersetzt aktuell selektierten Text.
        Voraussetzung: Text ist bereits selektiert.
        """
        start = time.time()
        
        try:
            # Type the new text (replaces selection)
            result = await self.type_text(new_text)
            
            return ActionResult(
                success=result.success,
                action_type="replace_text",
                params={"text": new_text[:50]},
                duration_ms=(time.time() - start) * 1000,
                error=result.error
            )
        
        except Exception as e:
            return ActionResult(
                success=False,
                action_type="replace_text",
                params={"text": new_text[:50]},
                duration_ms=(time.time() - start) * 1000,
                error=str(e)
            )
    
    async def take_screenshot(self) -> Tuple[bool, Optional[bytes]]:
        """
        Macht einen Screenshot.
        
        Returns:
            Tuple (success, screenshot_bytes)
        """
        if not HAS_PYAUTOGUI:
            return False, None
        
        try:
            screenshot = await asyncio.to_thread(pyautogui.screenshot)
            
            # Convert to bytes
            from io import BytesIO
            buffer = BytesIO()
            screenshot.save(buffer, format='PNG')
            screenshot_bytes = buffer.getvalue()
            
            logger.info("Screenshot captured")
            return True, screenshot_bytes
        
        except Exception as e:
            logger.error(f"Screenshot failed: {e}")
            return False, None
    
    def get_screen_size(self) -> Tuple[int, int]:
        """Gibt die Bildschirmgröße zurück."""
        if HAS_PYAUTOGUI:
            return pyautogui.size()
        return (1920, 1080)  # Default
    
    def get_mouse_position(self) -> Tuple[int, int]:
        """Gibt die aktuelle Mausposition zurück."""
        if HAS_PYAUTOGUI:
            return pyautogui.position()
        return (0, 0)
    
    # ==================== Action Dispatcher ====================
    
    async def execute_action(self, action_type: str, params: Dict[str, Any]) -> ActionResult:
        """
        Führt eine Aktion basierend auf Typ und Parametern aus.
        
        Dies ist die Hauptschnittstelle für den Orchestrator.
        
        Args:
            action_type: Art der Aktion (click, type, press_key, etc.)
            params: Parameter für die Aktion
        
        Returns:
            ActionResult
        """
        self._action_counter += 1
        
        action_map = {
            'click': lambda p: self.click(
                p.get('x', 0),
                p.get('y', 0),
                p.get('button', 'left'),
                p.get('clicks', 1)
            ),
            'double_click': lambda p: self.double_click(
                p.get('x', 0),
                p.get('y', 0)
            ),
            'right_click': lambda p: self.right_click(
                p.get('x', 0),
                p.get('y', 0)
            ),
            'type': lambda p: self.type_text(
                p.get('text', ''),
                p.get('interval')
            ),
            'press_key': lambda p: self.press_key(
                p.get('key', '')
            ),
            'hotkey': lambda p: self.hotkey(
                *p.get('keys', [])
            ),
            'scroll': lambda p: self.scroll(
                p.get('clicks', 0),
                p.get('x'),
                p.get('y')
            ),
            'move_to': lambda p: self.move_to(
                p.get('x', 0),
                p.get('y', 0),
                p.get('duration', 0.25)
            ),
            'drag': lambda p: self.drag(
                p.get('x', 0),
                p.get('y', 0),
                p.get('duration', 0.5),
                p.get('button', 'left')
            ),
            'wait': lambda p: self.wait(
                p.get('duration', 1.0)
            ),
            'select_text': lambda p: self.select_text(
                p.get('start_x', 0),
                p.get('start_y', 0),
                p.get('end_x', 0),
                p.get('end_y', 0)
            ),
            'replace_text': lambda p: self.replace_text(
                p.get('text', '')
            )
        }
        
        if action_type not in action_map:
            return ActionResult(
                success=False,
                action_type=action_type,
                params=params,
                duration_ms=0,
                error=f"Unknown action type: {action_type}"
            )
        
        return await action_map[action_type](params)
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken zurück."""
        return {
            "actions_executed": self._action_counter,
            "pyautogui_available": HAS_PYAUTOGUI,
            "screen_size": self.get_screen_size(),
            "mouse_position": self.get_mouse_position()
        }


# Singleton
_interaction_instance: Optional[InteractionAgent] = None


def get_interaction_agent() -> InteractionAgent:
    """Gibt Singleton-Instanz des Interaction Agents zurück."""
    global _interaction_instance
    if _interaction_instance is None:
        _interaction_instance = InteractionAgent()
    return _interaction_instance


def reset_interaction_agent():
    """Setzt Interaction Agent zurück."""
    global _interaction_instance
    _interaction_instance = None