"""
Reasoning Agent - Task-Analyse und Action Planning

Verantwortlich für:
- Analyse von Benutzer-Tasks
- Erstellung von Action-Plänen
- Replanning bei Fehlern
- Kontextuelle Entscheidungen
- Vision-basierte Element-Lokalisierung für Klicks

Portiert von MoireTracker v2 für VibeMind Integration.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

# Import from same package
from ..core.openrouter_client import OpenRouterClient, ModelType, get_openrouter_client
from ..core.event_queue import TaskEvent, ActionEvent, ActionStatus

# Import Vision Agent
try:
    from .vision_agent import VisionAnalystAgent, get_vision_agent, ElementLocation
    HAS_VISION = True
except ImportError:
    HAS_VISION = False
    ElementLocation = None

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class ActionPlan:
    """Ein geplanter Aktionsplan."""
    task_id: str
    goal: str
    actions: List[ActionEvent]
    reasoning: str
    confidence: float
    created_at: float


class ReasoningAgent:
    """
    Reasoning Agent - Plant Aktionen für Tasks.
    
    Verwendet Claude Sonnet 4 via OpenRouter für:
    - Task-Analyse und Verständnis
    - Action-Sequenz Planung
    - Fehlerbehandlung und Replanning
    - Vision-basierte Click-Koordinaten
    """
    
    def __init__(self, openrouter_client: Optional[OpenRouterClient] = None):
        self.client = openrouter_client or get_openrouter_client()
        self.action_counter = 0
        self.plan_history: List[ActionPlan] = []
        
        # Vision Agent für Element-Lokalisierung
        self.vision_agent: Optional[VisionAnalystAgent] = None
        if HAS_VISION:
            try:
                self.vision_agent = get_vision_agent()
                logger.info("Reasoning Agent: Vision Agent verfügbar")
            except Exception as e:
                logger.warning(f"Vision Agent nicht verfügbar: {e}")
        
        # Domänenspezifisches Wissen
        self.domain_knowledge = {
            "windows_apps": {
                "league of legends": ["win", "League of Legends", "enter"],
                "chrome": ["win", "Chrome", "enter"],
                "discord": ["win", "Discord", "enter"],
                "spotify": ["win", "Spotify", "enter"],
                "steam": ["win", "Steam", "enter"],
                "visual studio code": ["win", "Visual Studio Code", "enter"],
                "vscode": ["win", "Visual Studio Code", "enter"],
                "notepad": ["win", "Notepad", "enter"],
                "word": ["win", "Word", "enter"],
                "excel": ["win", "Excel", "enter"],
                "explorer": ["win", "e"],
                "settings": ["win", "i"],
            },
            "common_patterns": {
                "start_app": ["press_key:win", "wait:0.5", "type:{app_name}", "wait:0.5", "press_key:enter"],
                "close_window": ["press_key:alt+f4"],
                "switch_window": ["press_key:alt+tab"],
                "search": ["press_key:ctrl+f", "type:{query}"],
            },
            "ui_elements": {
                "leeres dokument": "Blank document option or template",
                "neues dokument": "New document button or option",
                "speichern": "Save button or icon",
                "öffnen": "Open file button or option",
                "schließen": "Close button or X icon",
            }
        }
    
    async def plan_task(
        self,
        task: TaskEvent,
        screen_state: Optional[Dict[str, Any]] = None,
        screenshot_bytes: Optional[bytes] = None
    ) -> List[ActionEvent]:
        """
        Plant Aktionen für einen Task.
        
        Args:
            task: Der zu planende Task
            screen_state: Aktueller Bildschirmzustand
            screenshot_bytes: Screenshot für Vision-Analyse
        
        Returns:
            Liste von ActionEvents
        """
        logger.info(f"Planning task: {task.goal}")
        
        # Zuerst: Schnelle Pattern-basierte Planung prüfen
        quick_actions = self._try_pattern_match(task.goal)
        if quick_actions:
            logger.info(f"Using pattern match for task: {len(quick_actions)} actions")
            return self._create_action_events(task.id, quick_actions)
        
        # Vision-basierte Planung wenn Screenshot verfügbar
        if screenshot_bytes and self.vision_agent and self.vision_agent.is_available():
            vision_plan = await self._plan_with_vision(task, screenshot_bytes, screen_state)
            if vision_plan:
                logger.info(f"Using vision-based plan: {len(vision_plan)} actions")
                return vision_plan
        
        # LLM-basierte Planung mit Screen-State
        try:
            actions_data = await self.client.plan_actions(
                goal=task.goal,
                screen_state=screen_state or {},
                history=self._get_recent_history()
            )
            
            if actions_data:
                # Für click-Actions ohne Koordinaten, Vision Agent nutzen
                if screenshot_bytes:
                    actions_data = await self._enrich_click_actions_with_vision(
                        actions_data, screenshot_bytes
                    )
                
                actions = self._create_action_events(task.id, actions_data)
                
                # Speichere Plan
                plan = ActionPlan(
                    task_id=task.id,
                    goal=task.goal,
                    actions=actions,
                    reasoning="LLM-generated plan",
                    confidence=0.8,
                    created_at=time.time()
                )
                self.plan_history.append(plan)
                
                logger.info(f"LLM plan created: {len(actions)} actions")
                return actions
            
        except Exception as e:
            logger.error(f"LLM planning failed: {e}")
        
        # Fallback: Regelbasierte Planung
        return self._fallback_planning(task)
    
    async def _plan_with_vision(
        self,
        task: TaskEvent,
        screenshot_bytes: bytes,
        screen_state: Optional[Dict[str, Any]]
    ) -> Optional[List[ActionEvent]]:
        """Plant Task mit Vision Agent."""
        try:
            from PIL import Image
            from io import BytesIO
            
            image = Image.open(BytesIO(screenshot_bytes))
            
            analysis = await self.vision_agent.analyze_screen_for_task(
                image, task.goal
            )
            
            if 'error' in analysis:
                logger.warning(f"Vision analysis failed: {analysis['error']}")
                return None
            
            if not analysis.get('task_completable', False):
                logger.info(f"Vision: Task nicht ausführbar - {analysis.get('reason', 'unknown')}")
                return None
            
            actions = []
            suggested = analysis.get('suggested_action', {})
            
            if suggested:
                action_type = suggested.get('type', 'wait')
                
                action = {
                    "action": action_type,
                    "description": suggested.get('description', 'Vision-basierte Aktion')
                }
                
                if action_type == 'click':
                    action['x'] = suggested.get('x', 0)
                    action['y'] = suggested.get('y', 0)
                    action['target'] = analysis.get('target_element', {}).get('description', '')
                elif action_type == 'type':
                    action['text'] = suggested.get('text', '')
                elif action_type == 'press_key':
                    action['key'] = suggested.get('key', '')
                elif action_type == 'wait':
                    action['duration'] = suggested.get('duration', 1.0)
                
                actions.append(action)
            
            if actions:
                return self._create_action_events(task.id, actions)
            
            return None
        
        except Exception as e:
            logger.error(f"_plan_with_vision failed: {e}")
            return None
    
    async def _enrich_click_actions_with_vision(
        self,
        actions_data: List[Dict[str, Any]],
        screenshot_bytes: bytes
    ) -> List[Dict[str, Any]]:
        """Reichert click-Actions mit Vision-basierten Koordinaten an."""
        if not self.vision_agent or not self.vision_agent.is_available():
            return actions_data
        
        enriched = []
        
        for action in actions_data:
            if action.get('action') == 'click':
                x = action.get('x')
                y = action.get('y')
                target = action.get('target', action.get('description', ''))
                
                needs_vision = (
                    x is None or y is None or
                    (x == 0 and y == 0) or
                    (x == 960 and y == 400)  # Bildschirmmitte = blind
                )
                
                if needs_vision and target:
                    logger.info(f"Using Vision to find: {target}")
                    
                    location = await self.vision_agent.find_element_from_screenshot(
                        screenshot_bytes,
                        target
                    )
                    
                    if location.found and location.confidence > 0.5:
                        action['x'] = location.x
                        action['y'] = location.y
                        action['vision_confidence'] = location.confidence
                        action['vision_description'] = location.description
                        logger.info(f"Vision found element at ({location.x}, {location.y})")
                    else:
                        logger.warning(f"Vision could not find: {target}")
            
            enriched.append(action)
        
        return enriched
    
    async def find_element_for_click(
        self,
        screenshot_bytes: bytes,
        element_description: str
    ) -> Optional[Dict[str, Any]]:
        """Public method: Findet Element für Klick via Vision."""
        if not self.vision_agent or not self.vision_agent.is_available():
            return None
        
        location = await self.vision_agent.find_element_from_screenshot(
            screenshot_bytes,
            element_description
        )
        
        if location.found:
            return {
                'x': location.x,
                'y': location.y,
                'confidence': location.confidence,
                'description': location.description,
                'element_type': location.element_type
            }
        
        return None
    
    def _try_pattern_match(self, goal: str) -> Optional[List[Dict[str, Any]]]:
        """Versucht Pattern-basierte Planung."""
        goal_lower = goal.lower()
        
        # Check für App-Start
        if "starte" in goal_lower or "start" in goal_lower or "öffne" in goal_lower or "open" in goal_lower:
            for app_name, keys in self.domain_knowledge["windows_apps"].items():
                if app_name in goal_lower:
                    actions = []
                    
                    # Windows-Taste
                    actions.append({
                        "action": "press_key",
                        "key": "win",
                        "description": "Windows-Taste drücken"
                    })
                    actions.append({
                        "action": "wait",
                        "duration": 0.7,
                        "description": "Warten auf Startmenü"
                    })
                    
                    # App-Name tippen
                    search_term = keys[1] if len(keys) > 1 else app_name
                    actions.append({
                        "action": "type",
                        "text": search_term,
                        "description": f"'{search_term}' eingeben"
                    })
                    actions.append({
                        "action": "wait",
                        "duration": 0.5,
                        "description": "Warten auf Suchergebnisse"
                    })
                    
                    # Enter drücken
                    actions.append({
                        "action": "press_key",
                        "key": "enter",
                        "description": "Enter drücken zum Starten"
                    })
                    
                    # Warten auf App-Start
                    actions.append({
                        "action": "wait",
                        "duration": 2.0,
                        "description": f"Warten auf {app_name} Start"
                    })
                    
                    return actions
        
        # Klick-Aktionen - brauchen Vision für Koordinaten
        if "klick" in goal_lower or "click" in goal_lower:
            target = goal_lower
            for word in ["klicke auf", "click on", "klick", "click", "drücke", "press"]:
                target = target.replace(word, "")
            target = target.strip()
            
            if target:
                return [{
                    "action": "click",
                    "target": target,
                    "x": None,
                    "y": None,
                    "description": f"Klick auf: {target}"
                }]
        
        return None
    
    def _create_action_events(
        self,
        task_id: str,
        actions_data: List[Dict[str, Any]]
    ) -> List[ActionEvent]:
        """Erstellt ActionEvent-Objekte aus Action-Dicts."""
        events = []
        
        for i, action_dict in enumerate(actions_data):
            self.action_counter += 1
            
            action_type = action_dict.get("action", "unknown")
            params = {}
            
            # Extrahiere Parameter basierend auf Action-Typ
            if action_type == "press_key":
                params["key"] = action_dict.get("key", "")
            elif action_type == "type":
                params["text"] = action_dict.get("text", "")
            elif action_type == "click":
                params["x"] = action_dict.get("x")
                params["y"] = action_dict.get("y")
                params["target"] = action_dict.get("target")
                if "vision_confidence" in action_dict:
                    params["vision_confidence"] = action_dict["vision_confidence"]
                if "vision_description" in action_dict:
                    params["vision_description"] = action_dict["vision_description"]
            elif action_type == "wait":
                params["duration"] = action_dict.get("duration", 1.0)
            elif action_type == "scroll":
                params["direction"] = action_dict.get("direction", "down")
                params["amount"] = action_dict.get("amount", 3)
            
            # Kopiere alle anderen Parameter
            for key, value in action_dict.items():
                if key not in ["action", "description"] and key not in params:
                    params[key] = value
            
            event = ActionEvent(
                id=f"action_{self.action_counter}_{int(time.time())}",
                task_id=task_id,
                action_type=action_type,
                params=params,
                description=action_dict.get("description", f"Schritt {i + 1}: {action_type}"),
                status=ActionStatus.PENDING
            )
            events.append(event)
        
        return events
    
    def _fallback_planning(self, task: TaskEvent) -> List[ActionEvent]:
        """Fallback-Planung ohne LLM."""
        goal_lower = task.goal.lower()
        actions = []
        
        if any(word in goal_lower for word in ["starte", "start", "öffne", "open", "launch"]):
            app_name = goal_lower
            for word in ["starte", "start", "öffne", "open", "launch", "die app", "das programm"]:
                app_name = app_name.replace(word, "")
            app_name = app_name.strip()
            
            actions = [
                {"action": "press_key", "key": "win", "description": "Windows-Taste"},
                {"action": "wait", "duration": 0.7, "description": "Warten auf Startmenü"},
                {"action": "type", "text": app_name, "description": f"'{app_name}' eingeben"},
                {"action": "wait", "duration": 0.5, "description": "Warten auf Suchergebnisse"},
                {"action": "press_key", "key": "enter", "description": "Enter drücken"},
                {"action": "wait", "duration": 2.0, "description": "Warten auf App-Start"}
            ]
        
        elif "schließe" in goal_lower or "close" in goal_lower:
            actions = [
                {"action": "press_key", "key": "alt+f4", "description": "Alt+F4 zum Schließen"}
            ]
        
        else:
            actions = [
                {"action": "wait", "duration": 1.0, "description": "Warten und analysieren"}
            ]
        
        return self._create_action_events(task.id, actions)
    
    async def replan_on_failure(
        self,
        task: TaskEvent,
        failed_action: ActionEvent,
        error: str,
        screen_state: Optional[Dict[str, Any]] = None,
        screenshot_bytes: Optional[bytes] = None
    ) -> List[ActionEvent]:
        """Plant bei Fehlschlag neu."""
        logger.warning(f"Replanning for task {task.id} after failure: {error}")
        
        # Bei click-Failures, versuche Vision-basierte Neuplanung
        if failed_action.action_type == "click" and screenshot_bytes and self.vision_agent:
            target = failed_action.params.get('target', failed_action.description)
            logger.info(f"Trying vision-based replan for click: {target}")
            
            location = await self.vision_agent.find_element_from_screenshot(
                screenshot_bytes, target
            )
            
            if location.found and location.confidence > 0.5:
                return self._create_action_events(task.id, [{
                    "action": "click",
                    "x": location.x,
                    "y": location.y,
                    "target": target,
                    "vision_confidence": location.confidence,
                    "description": f"Vision-basierter Klick auf: {location.description}"
                }])
        
        # Einfaches Fallback: Nochmal versuchen mit längeren Wartezeiten
        alternative_actions = []
        for action in task.actions:
            if action.status != ActionStatus.COMPLETED:
                action_dict = {
                    "action": action.action_type,
                    **action.params,
                    "description": action.description
                }
                if action.action_type == "wait":
                    action_dict["duration"] = action.params.get("duration", 1.0) * 2
                alternative_actions.append(action_dict)
        
        return self._create_action_events(task.id, alternative_actions)
    
    def _get_recent_history(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Gibt die letzten Plan-Historien zurück."""
        history = []
        for plan in self.plan_history[-limit:]:
            history.append({
                "goal": plan.goal,
                "actions_count": len(plan.actions),
                "success": all(a.status == ActionStatus.COMPLETED for a in plan.actions)
            })
        return history
    
    def get_stats(self) -> Dict[str, Any]:
        """Gibt Statistiken zurück."""
        total_plans = len(self.plan_history)
        successful_plans = sum(
            1 for p in self.plan_history
            if all(a.status == ActionStatus.COMPLETED for a in p.actions)
        )
        
        return {
            "total_plans": total_plans,
            "successful_plans": successful_plans,
            "success_rate": successful_plans / total_plans if total_plans > 0 else 0,
            "total_actions_created": self.action_counter,
            "vision_available": self.vision_agent is not None and self.vision_agent.is_available()
        }


# Singleton
_reasoning_instance: Optional[ReasoningAgent] = None


def get_reasoning_agent(client: Optional[OpenRouterClient] = None) -> ReasoningAgent:
    """Gibt Singleton-Instanz des Reasoning Agents zurück."""
    global _reasoning_instance
    if _reasoning_instance is None:
        _reasoning_instance = ReasoningAgent(client)
    return _reasoning_instance


def reset_reasoning_agent():
    """Setzt Reasoning Agent zurück."""
    global _reasoning_instance
    _reasoning_instance = None