"""
Event Queue System - Kontinuierliche Task-Verarbeitung

Drei Queues:
- task_queue: Eingehende Tasks vom Benutzer
- action_queue: Geplante Aktionen vom Reasoning Agent
- result_queue: Validierungsergebnisse

Portiert von MoireTracker v2 für VibeMind Integration.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EventType(Enum):
    """Typen von Events im System."""
    TASK = "task"           # Neuer Task vom Benutzer
    ACTION = "action"       # Geplante Aktion
    RESULT = "result"       # Ausführungsergebnis
    VALIDATION = "validation"  # Validierungsergebnis
    STATE_CHANGE = "state_change"  # Bildschirmänderung
    ERROR = "error"         # Fehler


class TaskStatus(Enum):
    """Status eines Tasks."""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ActionStatus(Enum):
    """Status einer Aktion."""
    PENDING = "pending"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class TaskEvent:
    """Ein Task der verarbeitet werden soll."""
    id: str
    goal: str
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    actions: List['ActionEvent'] = field(default_factory=list)
    current_action_idx: int = 0
    context: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Any] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3


@dataclass 
class ActionEvent:
    """Eine einzelne Aktion."""
    id: str
    task_id: str
    action_type: str
    params: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    status: ActionStatus = ActionStatus.PENDING
    created_at: float = field(default_factory=time.time)
    executed_at: Optional[float] = None
    completed_at: Optional[float] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    validation: Optional[Dict[str, Any]] = None
    screenshot_before: Optional[str] = None
    screenshot_after: Optional[str] = None


@dataclass
class ValidationEvent:
    """Validierungsergebnis einer Aktion."""
    action_id: str
    task_id: str
    success: bool
    confidence: float = 0.0
    description: str = ""
    state_changed: bool = False
    timestamp: float = field(default_factory=time.time)


class EventQueue:
    """
    Event Queue System für kontinuierliche Verarbeitung.
    
    Verwendet drei asyncio.Queue:
    - task_queue: Eingehende Tasks
    - action_queue: Geplante Aktionen
    - result_queue: Ergebnisse und Validierungen
    """
    
    def __init__(
        self,
        max_concurrent_tasks: int = 1,
        action_timeout: float = 60.0,
        validation_timeout: float = 10.0
    ):
        self.task_queue: asyncio.Queue[TaskEvent] = asyncio.Queue()
        self.action_queue: asyncio.Queue[ActionEvent] = asyncio.Queue()
        self.result_queue: asyncio.Queue[ValidationEvent] = asyncio.Queue()
        
        self.max_concurrent_tasks = max_concurrent_tasks
        self.action_timeout = action_timeout
        self.validation_timeout = validation_timeout
        
        # Active tasks
        self.active_tasks: Dict[str, TaskEvent] = {}
        self.completed_tasks: List[TaskEvent] = []
        
        # Handlers
        self._task_handler: Optional[Callable[[TaskEvent], Awaitable[List[ActionEvent]]]] = None
        self._action_handler: Optional[Callable[[ActionEvent], Awaitable[Dict[str, Any]]]] = None
        self._validation_handler: Optional[Callable[[ActionEvent, Dict[str, Any]], Awaitable[ValidationEvent]]] = None
        self._state_change_handler: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None
        
        # Event callbacks
        self._on_task_start: List[Callable[[TaskEvent], None]] = []
        self._on_task_complete: List[Callable[[TaskEvent], None]] = []
        self._on_action_start: List[Callable[[ActionEvent], None]] = []
        self._on_action_complete: List[Callable[[ActionEvent, ValidationEvent], None]] = []
        self._on_error: List[Callable[[str, Exception], None]] = []
        
        # State
        self._running = False
        self._task_counter = 0
        self._action_counter = 0
        
        # Processing tasks
        self._task_processor: Optional[asyncio.Task] = None
        self._action_processor: Optional[asyncio.Task] = None
        self._result_processor: Optional[asyncio.Task] = None
    
    def _calculate_action_timeout(self, action: ActionEvent) -> float:
        """
        Berechnet dynamischen Timeout basierend auf Aktionstyp.
        """
        base_timeout = self.action_timeout
        
        if action.action_type == "type":
            text = action.params.get("text", "")
            text_timeout = len(text) * 0.05 + 5
            return max(base_timeout, text_timeout)
        
        elif action.action_type == "wait":
            duration = action.params.get("duration", 1.0)
            return duration + 5
        
        elif action.action_type == "click":
            return base_timeout
        
        elif action.action_type == "drag":
            return base_timeout * 1.5
        
        elif action.action_type == "scroll":
            return 15.0
        
        return base_timeout
    
    # ==================== Handler Registration ====================
    
    def set_task_handler(self, handler: Callable[[TaskEvent], Awaitable[List[ActionEvent]]]):
        """Setzt den Handler für Task-Planung (Reasoning Agent)."""
        self._task_handler = handler
    
    def set_action_handler(self, handler: Callable[[ActionEvent], Awaitable[Dict[str, Any]]]):
        """Setzt den Handler für Action-Ausführung (Interaction Agent)."""
        self._action_handler = handler
    
    def set_validation_handler(
        self, 
        handler: Callable[[ActionEvent, Dict[str, Any]], Awaitable[ValidationEvent]]
    ):
        """Setzt den Handler für Action-Validierung."""
        self._validation_handler = handler
    
    def set_state_change_handler(self, handler: Callable[[Dict[str, Any]], Awaitable[None]]):
        """Setzt den Handler für State-Changes."""
        self._state_change_handler = handler
    
    # ==================== Event Callbacks ====================
    
    def on_task_start(self, callback: Callable[[TaskEvent], None]):
        """Callback wenn Task startet."""
        self._on_task_start.append(callback)
    
    def on_task_complete(self, callback: Callable[[TaskEvent], None]):
        """Callback wenn Task abgeschlossen."""
        self._on_task_complete.append(callback)
    
    def on_action_start(self, callback: Callable[[ActionEvent], None]):
        """Callback wenn Aktion startet."""
        self._on_action_start.append(callback)
    
    def on_action_complete(self, callback: Callable[[ActionEvent, ValidationEvent], None]):
        """Callback wenn Aktion abgeschlossen und validiert."""
        self._on_action_complete.append(callback)
    
    def on_error(self, callback: Callable[[str, Exception], None]):
        """Callback bei Fehlern."""
        self._on_error.append(callback)
    
    # ==================== Task Management ====================
    
    async def add_task(self, goal: str, context: Optional[Dict[str, Any]] = None) -> TaskEvent:
        """
        Fügt einen neuen Task zur Queue hinzu.
        """
        self._task_counter += 1
        task = TaskEvent(
            id=f"task_{self._task_counter}_{int(time.time())}",
            goal=goal,
            context=context or {}
        )
        
        await self.task_queue.put(task)
        logger.info(f"Task hinzugefügt: {task.id} - {goal}")
        
        return task
    
    def get_task(self, task_id: str) -> Optional[TaskEvent]:
        """Gibt Task nach ID zurück."""
        return self.active_tasks.get(task_id)
    
    def get_all_tasks(self) -> List[TaskEvent]:
        """Gibt alle aktiven Tasks zurück."""
        return list(self.active_tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        """Bricht einen Task ab."""
        task = self.active_tasks.get(task_id)
        if task:
            task.status = TaskStatus.CANCELLED
            task.completed_at = time.time()
            logger.info(f"Task abgebrochen: {task_id}")
            return True
        return False
    
    # ==================== Processing Loops ====================
    
    async def start(self):
        """Startet die Event-Verarbeitung."""
        if self._running:
            logger.warning("EventQueue already running")
            return
        
        self._running = True
        logger.info("EventQueue gestartet")
        
        self._task_processor = asyncio.create_task(self._process_tasks())
        self._action_processor = asyncio.create_task(self._process_actions())
        self._result_processor = asyncio.create_task(self._process_results())
    
    async def stop(self):
        """Stoppt die Event-Verarbeitung."""
        self._running = False
        
        for processor in [self._task_processor, self._action_processor, self._result_processor]:
            if processor:
                processor.cancel()
                try:
                    await processor
                except asyncio.CancelledError:
                    pass
        
        logger.info("EventQueue gestoppt")
    
    async def _process_tasks(self):
        """Verarbeitet Tasks aus der Queue."""
        while self._running:
            try:
                task = await asyncio.wait_for(
                    self.task_queue.get(),
                    timeout=1.0
                )
                
                active_count = sum(
                    1 for t in self.active_tasks.values() 
                    if t.status in [TaskStatus.PLANNING, TaskStatus.EXECUTING, TaskStatus.VALIDATING]
                )
                
                if active_count >= self.max_concurrent_tasks:
                    await self.task_queue.put(task)
                    await asyncio.sleep(0.5)
                    continue
                
                await self._handle_task(task)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Task processing error: {e}")
                self._emit_error("task_processing", e)
    
    async def _handle_task(self, task: TaskEvent):
        """Verarbeitet einen einzelnen Task."""
        task.status = TaskStatus.PLANNING
        task.started_at = time.time()
        self.active_tasks[task.id] = task
        
        for cb in self._on_task_start:
            try:
                cb(task)
            except Exception as e:
                logger.error(f"Task start callback error: {e}")
        
        logger.info(f"Task wird geplant: {task.id}")
        
        try:
            if self._task_handler:
                actions = await self._task_handler(task)
                task.actions = actions
                
                for action in actions:
                    await self.action_queue.put(action)
                
                task.status = TaskStatus.EXECUTING
                logger.info(f"Task geplant: {task.id} mit {len(actions)} Aktionen")
            else:
                logger.error("Kein Task-Handler registriert")
                task.status = TaskStatus.FAILED
                task.error = "No task handler registered"
        
        except Exception as e:
            logger.error(f"Task planning failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
            self._emit_error("task_planning", e)
    
    async def _process_actions(self):
        """Verarbeitet Aktionen aus der Queue."""
        while self._running:
            try:
                action = await asyncio.wait_for(
                    self.action_queue.get(),
                    timeout=1.0
                )
                
                task = self.active_tasks.get(action.task_id)
                if not task or task.status == TaskStatus.CANCELLED:
                    action.status = ActionStatus.SKIPPED
                    continue
                
                await self._handle_action(action, task)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Action processing error: {e}")
                self._emit_error("action_processing", e)
    
    async def _handle_action(self, action: ActionEvent, task: TaskEvent):
        """Führt eine einzelne Aktion aus."""
        action.status = ActionStatus.EXECUTING
        action.executed_at = time.time()
        
        for cb in self._on_action_start:
            try:
                cb(action)
            except Exception as e:
                logger.error(f"Action start callback error: {e}")
        
        logger.info(f"Aktion wird ausgeführt: {action.action_type} - {action.description}")
        
        timeout = self._calculate_action_timeout(action)
        logger.debug(f"Action timeout: {timeout}s für {action.action_type}")
        
        try:
            if self._action_handler:
                result = await asyncio.wait_for(
                    self._action_handler(action),
                    timeout=timeout
                )
                action.result = result
                
                if self._validation_handler:
                    validation = await asyncio.wait_for(
                        self._validation_handler(action, result),
                        timeout=self.validation_timeout
                    )
                    action.validation = {
                        "success": validation.success,
                        "confidence": validation.confidence,
                        "description": validation.description
                    }
                    
                    await self.result_queue.put(validation)
                else:
                    action.status = ActionStatus.COMPLETED
                    action.completed_at = time.time()
            else:
                logger.error("Kein Action-Handler registriert")
                action.status = ActionStatus.FAILED
                action.error = "No action handler registered"
        
        except asyncio.TimeoutError:
            logger.error(f"Aktion Timeout nach {timeout}s: {action.id}")
            action.status = ActionStatus.FAILED
            action.error = f"Action timeout after {timeout}s"
        
        except Exception as e:
            logger.error(f"Action execution failed: {e}")
            action.status = ActionStatus.FAILED
            action.error = str(e)
            self._emit_error("action_execution", e)
    
    async def _process_results(self):
        """Verarbeitet Validierungsergebnisse."""
        while self._running:
            try:
                validation = await asyncio.wait_for(
                    self.result_queue.get(),
                    timeout=1.0
                )
                
                await self._handle_validation(validation)
                
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Result processing error: {e}")
                self._emit_error("result_processing", e)
    
    async def _handle_validation(self, validation: ValidationEvent):
        """Verarbeitet Validierungsergebnis."""
        task = self.active_tasks.get(validation.task_id)
        if not task:
            return
        
        action = None
        for a in task.actions:
            if a.id == validation.action_id:
                action = a
                break
        
        if not action:
            return
        
        if validation.success:
            action.status = ActionStatus.COMPLETED
            action.completed_at = time.time()
            logger.info(f"Aktion validiert: {action.id} (Confidence: {validation.confidence:.2f})")
            
            for cb in self._on_action_complete:
                try:
                    cb(action, validation)
                except Exception as e:
                    logger.error(f"Action complete callback error: {e}")
            
            all_done = all(
                a.status in [ActionStatus.COMPLETED, ActionStatus.SKIPPED]
                for a in task.actions
            )
            
            if all_done:
                task.status = TaskStatus.COMPLETED
                task.completed_at = time.time()
                self.completed_tasks.append(task)
                
                for cb in self._on_task_complete:
                    try:
                        cb(task)
                    except Exception as e:
                        logger.error(f"Task complete callback error: {e}")
                
                logger.info(f"Task abgeschlossen: {task.id}")
        
        else:
            action.status = ActionStatus.FAILED
            action.error = validation.description
            
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                logger.warning(f"Aktion fehlgeschlagen, Retry {task.retry_count}/{task.max_retries}")
                
                task.status = TaskStatus.PENDING
                await self.task_queue.put(task)
            else:
                task.status = TaskStatus.FAILED
                task.error = f"Max retries exceeded: {validation.description}"
                logger.error(f"Task fehlgeschlagen: {task.id}")
    
    def _emit_error(self, context: str, error: Exception):
        """Emittiert Fehler an Callbacks."""
        for cb in self._on_error:
            try:
                cb(context, error)
            except:
                pass
    
    # ==================== Status ====================
    
    def get_status(self) -> Dict[str, Any]:
        """Gibt Status des EventQueue Systems zurück."""
        return {
            "running": self._running,
            "task_queue_size": self.task_queue.qsize(),
            "action_queue_size": self.action_queue.qsize(),
            "result_queue_size": self.result_queue.qsize(),
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
            "total_tasks_processed": self._task_counter,
            "total_actions_processed": self._action_counter
        }
    
    async def wait_for_task(self, task_id: str, timeout: float = 60.0) -> TaskEvent:
        """Wartet bis ein Task abgeschlossen ist."""
        start = time.time()
        while time.time() - start < timeout:
            task = self.active_tasks.get(task_id)
            if task:
                if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
                    return task
            await asyncio.sleep(0.1)
        
        raise TimeoutError(f"Task {task_id} did not complete within {timeout}s")


# Singleton
_queue_instance: Optional[EventQueue] = None


def get_event_queue() -> EventQueue:
    """Gibt Singleton-Instanz des EventQueue zurück."""
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = EventQueue()
    return _queue_instance


def reset_event_queue():
    """Setzt EventQueue zurück."""
    global _queue_instance
    if _queue_instance:
        asyncio.create_task(_queue_instance.stop())
    _queue_instance = None