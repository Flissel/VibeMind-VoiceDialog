"""
OrchestratorV2 - Event-driven Task-Koordination

Verantwortlich für:
- Task-Entgegennahme und Planung
- Action-Ausführung via InteractionAgent
- Validierung und Replanning
- Screenshot-basierte Zustandsüberwachung

Portiert von MoireTracker v2 für VibeMind Integration.
Unterschied: Kein WebSocket zu MoireServer, nutzt direkt PyAutoGUI Screenshots.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from enum import Enum

# Import from same package
from ..core.event_queue import (
    EventQueue, get_event_queue,
    TaskEvent, ActionEvent, ValidationEvent,
    TaskStatus, ActionStatus
)
from .interaction import InteractionAgent, get_interaction_agent
from .reasoning import ReasoningAgent, get_reasoning_agent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrchestratorState(Enum):
    """Zustand des Orchestrators."""
    IDLE = "idle"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    WAITING = "waiting"
    ERROR = "error"


@dataclass
class OrchestratorStatus:
    """Status des Orchestrators."""
    state: OrchestratorState
    current_task: Optional[str]
    current_action: Optional[str]
    tasks_completed: int
    tasks_failed: int
    actions_executed: int
    uptime_seconds: float


class OrchestratorV2:
    """
    Event-driven Orchestrator für Desktop-Automation.
    
    Koordiniert:
    - ReasoningAgent für Task-Planung
    - InteractionAgent für Action-Ausführung
    - VisionAgent (via ReasoningAgent) für Element-Lokalisierung
    
    Verwendet EventQueue für asynchrone Verarbeitung.
    """
    
    def __init__(
        self,
        auto_validate: bool = True,
        max_task_retries: int = 3,
        action_delay: float = 0.5
    ):
        """
        Initialisiert den Orchestrator.
        
        Args:
            auto_validate: Automatisch nach jeder Aktion validieren
            max_task_retries: Max Wiederholungen bei Fehlern
            action_delay: Pause zwischen Aktionen in Sekunden
        """
        # Agents
        self.interaction_agent = get_interaction_agent()
        self.reasoning_agent = get_reasoning_agent()
        
        # Event Queue
        self.event_queue = get_event_queue()
        
        # Configuration
        self.auto_validate = auto_validate
        self.max_task_retries = max_task_retries
        self.action_delay = action_delay
        
        # State
        self.state = OrchestratorState.IDLE
        self.start_time = time.time()
        self._running = False
        
        # Statistics
        self.stats = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "actions_executed": 0,
            "validations_success": 0,
            "validations_failed": 0
        }
        
        # Callbacks
        self._on_task_complete: List[Callable[[TaskEvent], None]] = []
        self._on_action_complete: List[Callable[[ActionEvent], None]] = []
        self._on_error: List[Callable[[str, Exception], None]] = []
        
        # Register handlers with event queue
        self._setup_event_handlers()
        
        logger.info("OrchestratorV2 initialized")
    
    def _setup_event_handlers(self):
        """Registriert Event Handler beim EventQueue."""
        # Task Handler: Planung durch ReasoningAgent
        self.event_queue.set_task_handler(self._plan_task)
        
        # Action Handler: Ausführung durch InteractionAgent
        self.event_queue.set_action_handler(self._execute_action)
        
        # Validation Handler
        if self.auto_validate:
            self.event_queue.set_validation_handler(self._validate_action)
        
        # Callbacks
        self.event_queue.on_task_complete(self._on_task_completed)
        self.event_queue.on_error(self._on_queue_error)
    
    # ==================== Public API ====================
    
    async def start(self):
        """Startet den Orchestrator."""
        if self._running:
            logger.warning("Orchestrator already running")
            return
        
        self._running = True
        self.state = OrchestratorState.IDLE
        self.start_time = time.time()
        
        await self.event_queue.start()
        logger.info("OrchestratorV2 started")
    
    async def stop(self):
        """Stoppt den Orchestrator."""
        self._running = False
        self.state = OrchestratorState.IDLE
        
        await self.event_queue.stop()
        logger.info("OrchestratorV2 stopped")
    
    async def submit_task(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None
    ) -> TaskEvent:
        """
        Submittiert einen neuen Task.
        
        Args:
            goal: Beschreibung des Ziels
            context: Optionaler Kontext
        
        Returns:
            TaskEvent
        """
        if not self._running:
            raise RuntimeError("Orchestrator not running. Call start() first.")
        
        logger.info(f"Submitting task: {goal}")
        
        task = await self.event_queue.add_task(goal, context)
        return task
    
    async def execute_task_and_wait(
        self,
        goal: str,
        context: Optional[Dict[str, Any]] = None,
        timeout: float = 120.0
    ) -> TaskEvent:
        """
        Führt Task aus und wartet auf Abschluss.
        
        Args:
            goal: Beschreibung des Ziels
            context: Optionaler Kontext
            timeout: Max. Wartezeit
        
        Returns:
            TaskEvent mit Ergebnis
        """
        task = await self.submit_task(goal, context)
        
        try:
            completed_task = await self.event_queue.wait_for_task(
                task.id,
                timeout=timeout
            )
            return completed_task
        except TimeoutError:
            task.status = TaskStatus.FAILED
            task.error = f"Task timed out after {timeout}s"
            return task
    
    async def execute_single_action(
        self,
        action_type: str,
        params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Führt eine einzelne Aktion direkt aus (ohne Task).
        
        Args:
            action_type: Art der Aktion
            params: Parameter
        
        Returns:
            Ergebnis-Dict
        """
        result = await self.interaction_agent.execute_action(action_type, params)
        
        self.stats["actions_executed"] += 1
        
        return {
            "success": result.success,
            "action_type": result.action_type,
            "duration_ms": result.duration_ms,
            "error": result.error
        }
    
    def get_status(self) -> OrchestratorStatus:
        """Gibt aktuellen Status zurück."""
        current_task = None
        current_action = None
        
        for task in self.event_queue.get_all_tasks():
            if task.status in [TaskStatus.PLANNING, TaskStatus.EXECUTING]:
                current_task = task.goal
                for action in task.actions:
                    if action.status == ActionStatus.EXECUTING:
                        current_action = action.description
                        break
                break
        
        return OrchestratorStatus(
            state=self.state,
            current_task=current_task,
            current_action=current_action,
            tasks_completed=self.stats["tasks_completed"],
            tasks_failed=self.stats["tasks_failed"],
            actions_executed=self.stats["actions_executed"],
            uptime_seconds=time.time() - self.start_time
        )
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken zurück."""
        return {
            **self.stats,
            "state": self.state.value,
            "uptime_seconds": time.time() - self.start_time,
            "event_queue": self.event_queue.get_status(),
            "interaction_agent": self.interaction_agent.get_stats(),
            "reasoning_agent": self.reasoning_agent.get_stats()
        }
    
    # ==================== Event Handlers ====================
    
    async def _plan_task(self, task: TaskEvent) -> List[ActionEvent]:
        """
        Handler für Task-Planung.
        
        Wird vom EventQueue aufgerufen wenn ein neuer Task kommt.
        """
        self.state = OrchestratorState.PLANNING
        
        logger.info(f"Planning task: {task.goal}")
        
        try:
            # Screenshot für Kontext
            screenshot_bytes = None
            success, screenshot = await self.interaction_agent.take_screenshot()
            if success:
                screenshot_bytes = screenshot
            
            # ReasoningAgent plant Aktionen
            actions = await self.reasoning_agent.plan_task(
                task,
                screen_state=task.context.get('screen_state', {}),
                screenshot_bytes=screenshot_bytes
            )
            
            logger.info(f"Planned {len(actions)} actions for task")
            return actions
        
        except Exception as e:
            logger.error(f"Task planning failed: {e}")
            self.state = OrchestratorState.ERROR
            raise
    
    async def _execute_action(self, action: ActionEvent) -> Dict[str, Any]:
        """
        Handler für Action-Ausführung.
        
        Wird vom EventQueue aufgerufen für jede geplante Aktion.
        """
        self.state = OrchestratorState.EXECUTING
        
        logger.info(f"Executing action: {action.action_type} - {action.description}")
        
        # Kurze Pause vor der Aktion
        if self.action_delay > 0:
            await asyncio.sleep(self.action_delay)
        
        # Screenshot vor der Aktion
        before_success, before_screenshot = await self.interaction_agent.take_screenshot()
        if before_success:
            action.screenshot_before = before_screenshot
        
        # Führe Aktion aus
        result = await self.interaction_agent.execute_action(
            action.action_type,
            action.params
        )
        
        self.stats["actions_executed"] += 1
        
        # Screenshot nach der Aktion
        await asyncio.sleep(0.3)  # Kurz warten für UI-Update
        after_success, after_screenshot = await self.interaction_agent.take_screenshot()
        if after_success:
            action.screenshot_after = after_screenshot
        
        return {
            "success": result.success,
            "error": result.error,
            "duration_ms": result.duration_ms,
            "screenshot_before": before_screenshot if before_success else None,
            "screenshot_after": after_screenshot if after_success else None
        }
    
    async def _validate_action(
        self,
        action: ActionEvent,
        result: Dict[str, Any]
    ) -> ValidationEvent:
        """
        Handler für Action-Validierung.
        
        Prüft ob die Aktion erfolgreich war basierend auf Screenshots.
        """
        self.state = OrchestratorState.VALIDATING
        
        # Einfache Validierung basierend auf PyAutoGUI Ergebnis
        success = result.get("success", False)
        confidence = 0.9 if success else 0.1
        description = "Action completed" if success else result.get("error", "Unknown error")
        
        # TODO: Vision-basierte Validierung hinzufügen
        # Vergleiche before/after Screenshots um zu prüfen ob sich etwas geändert hat
        
        if success:
            self.stats["validations_success"] += 1
        else:
            self.stats["validations_failed"] += 1
        
        self.state = OrchestratorState.IDLE
        
        return ValidationEvent(
            action_id=action.id,
            task_id=action.task_id,
            success=success,
            confidence=confidence,
            description=description,
            state_changed=success
        )
    
    def _on_task_completed(self, task: TaskEvent):
        """Callback wenn Task abgeschlossen."""
        if task.status == TaskStatus.COMPLETED:
            self.stats["tasks_completed"] += 1
            logger.info(f"Task completed successfully: {task.goal}")
        else:
            self.stats["tasks_failed"] += 1
            logger.warning(f"Task failed: {task.goal} - {task.error}")
        
        self.state = OrchestratorState.IDLE
        
        # Notify callbacks
        for cb in self._on_task_complete:
            try:
                cb(task)
            except Exception as e:
                logger.error(f"Task complete callback error: {e}")
    
    def _on_queue_error(self, context: str, error: Exception):
        """Callback bei Queue-Fehlern."""
        logger.error(f"Queue error in {context}: {error}")
        
        for cb in self._on_error:
            try:
                cb(context, error)
            except:
                pass
    
    # ==================== Callbacks ====================
    
    def on_task_complete(self, callback: Callable[[TaskEvent], None]):
        """Registriert Callback für Task-Abschluss."""
        self._on_task_complete.append(callback)
    
    def on_action_complete(self, callback: Callable[[ActionEvent], None]):
        """Registriert Callback für Action-Abschluss."""
        self._on_action_complete.append(callback)
    
    def on_error(self, callback: Callable[[str, Exception], None]):
        """Registriert Callback für Fehler."""
        self._on_error.append(callback)


# Singleton
_orchestrator_instance: Optional[OrchestratorV2] = None


def get_orchestrator() -> OrchestratorV2:
    """Gibt Singleton-Instanz des Orchestrators zurück."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = OrchestratorV2()
    return _orchestrator_instance


def reset_orchestrator():
    """Setzt Orchestrator zurück."""
    global _orchestrator_instance
    if _orchestrator_instance:
        asyncio.create_task(_orchestrator_instance.stop())
    _orchestrator_instance = None


async def test_orchestrator():
    """Test-Funktion für Orchestrator."""
    orch = get_orchestrator()
    
    print("Starting orchestrator...")
    await orch.start()
    
    print(f"Status: {orch.get_status()}")
    
    # Test task
    result = await orch.execute_task_and_wait(
        "Öffne Notepad",
        timeout=30.0
    )
    
    print(f"Task result: {result.status.value}")
    print(f"Stats: {orch.get_stats()}")
    
    await orch.stop()


if __name__ == "__main__":
    asyncio.run(test_orchestrator())