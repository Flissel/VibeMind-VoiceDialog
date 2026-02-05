"""
Shuttle Orchestrator Agent - Backend Agent for Shuttle Domain

Manages shuttle workflow orchestration including:
- Intent Classification
- Execution Plan Generation
- Execution Plan Distribution

Uses AutoGen 4.0 for LLM-based reasoning and coordination.
"""

import asyncio
import json
import logging
import os
from typing import Dict, Callable, Optional, Any

from swarm.backend_agents.base_agent import BaseBackendAgent
from swarm.event_bus import EventBus, SwarmEvent

logger = logging.getLogger(__name__)

USE_AG2_SWARM = os.getenv("USE_AG2_SWARM", "false").lower() in ("true", "1", "yes")


class ShuttleOrchestratorAgent(BaseBackendAgent):
    """
    Backend agent for Shuttle domain orchestration.
    
    Manages shuttle workflow including intent classification,
    execution plan generation, and task distribution to workers.
    """
    
    # Event type to tool name mapping
    EVENT_TO_TOOL = {
        # Shuttle events
        "shuttle.list": "list_bubbles_with_requirements",
        "shuttle.get": "get_bubble_requirements",
        "shuttle.process": "process_bubble_requirements",
        # Intent classification events
        "shuttle.classify_intent": "classify_intent",
        "shuttle.generate_plan": "generate_execution_plan",
        "shuttle.distribute_task": "distribute_task",
    }
    
    # Parameter normalization: map classifier output to tool expected params
    PARAM_MAPPING = {
        "shuttle.list": {},
        "shuttle.get": {
            "bubble_id": "bubble_id",
            "id": "bubble_id",
        },
        "shuttle.process": {
            "bubble_id": "bubble_id",
            "id": "bubble_id",
        },
        "shuttle.classify_intent": {
            "user_input": "user_input",
            "transcript": "user_input",
            "text": "user_input",
        },
        "shuttle.generate_plan": {
            "intent": "intent",
            "user_input": "user_input",
            "context": "context",
        },
        "shuttle.distribute_task": {
            "plan": "execution_plan",
            "worker_type": "worker_type",
            "task_data": "task_data",
        },
    }
    
    @property
    def stream(self) -> str:
        return EventBus.STREAM_TASKS_SHUTTLES
    
    @property
    def name(self) -> str:
        return "ShuttleOrchestratorAgent"
    
    def _load_tools(self) -> Dict[str, Callable]:
        """Load shuttle tools."""
        tools = {}
        
        # Load shuttle tools
        try:
            from tools.bubble_requirements_tool import (
                list_bubbles_with_requirements,
                get_bubble_requirements,
                process_bubble_requirements,
            )
            
            tools.update({
                "list_bubbles_with_requirements": list_bubbles_with_requirements,
                "get_bubble_requirements": get_bubble_requirements,
                "process_bubble_requirements": process_bubble_requirements,
            })
            logger.info(f"{self.name}: Loaded 3 shuttle tools")
            
        except ImportError as e:
            logger.warning(f"{self.name}: Could not load shuttle tools: {e}")
        
        return tools
    
    def _get_tool_name(self, event_type: str) -> Optional[str]:
        """Map event type to tool name."""
        return self.EVENT_TO_TOOL.get(event_type)
    
    async def _handle_event(self, event: SwarmEvent):
        """
        Handle incoming event from Redis.
        
        Args:
            event: SwarmEvent from stream
        """
        job_id = event.job_id or "unknown"
        event_type = event.event_type
        payload = event.payload
        
        logger.info(f"{self.name}: Received {event_type} (job={job_id})")
        
        # Log event received
        self._execution_logger.log_event_received(
            agent_name=self.name,
            job_id=job_id,
            event_type=event_type,
            payload=payload
        )
        
        # Get tool for this event type
        tool_name = self._get_tool_name(event_type)
        if not tool_name:
            error_msg = f"Unknown event type: {event_type}"
            self._execution_logger.log_tool_error(
                agent_name=self.name,
                job_id=job_id,
                original_event=event_type,
                tool_name=None,
                error=error_msg
            )
            await self._publish_error(job_id, error_msg)
            return
        
        tool = self.tools.get(tool_name)
        if not tool:
            error_msg = f"Tool not found: {tool_name}"
            self._execution_logger.log_tool_error(
                agent_name=self.name,
                job_id=job_id,
                original_event=event_type,
                tool_name=tool_name,
                error=error_msg
            )
            await self._publish_error(job_id, error_msg)
            return
        
        # Execute tool
        try:
            await self._publish_status(job_id, "started", event_type=event_type)
            
            # Remove internal fields from payload before passing to tool
            tool_params = {k: v for k, v in payload.items()
                          if k not in ["job_id", "user_id", "session_id", "priority", "bubble_context", "metadata"]}
            
            # Extract user_input for fallback parameter extraction
            user_input = tool_params.pop("_user_input", "")
            
            # Extract conversation history for contextual resolution
            conversation_history = tool_params.pop("_conversation_history", [])
            if conversation_history:
                logger.debug(f"{self.name}: Received {len(conversation_history)} messages of conversation history")
            
            # Normalize parameter names
            tool_params = self._normalize_params(event_type, tool_params)
            
            # Resolve contextual references using conversation history
            if conversation_history:
                context_resolved = self._resolve_context_references(
                    event_type, user_input, tool_params, conversation_history
                )
                for key, value in context_resolved.items():
                    if key not in tool_params or not tool_params.get(key):
                        tool_params[key] = value
                        logger.info(f"{self.name}: Resolved '{key}' from conversation context: {value}")
            
            # Fallback: extract missing params from transcript
            if user_input:
                extracted = self._extract_params_from_transcript(event_type, user_input)
                for key, value in extracted.items():
                    if key not in tool_params or not tool_params.get(key):
                        tool_params[key] = value
                        logger.info(f"{self.name}: Filled missing param '{key}' from transcript")
            
            # Log tool started
            self._execution_logger.log_tool_started(
                agent_name=self.name,
                job_id=job_id,
                original_event=event_type,
                tool_name=tool_name,
                params=tool_params
            )
            
            # Execute tool
            result = tool(**tool_params)
            
            # Handle async tools
            if asyncio.iscoroutine(result):
                result = await result
            
            # Log tool completed
            self._execution_logger.log_tool_completed(
                agent_name=self.name,
                job_id=job_id,
                original_event=event_type,
                tool_name=tool_name,
                result=result
            )
            
            await self._publish_status(
                job_id,
                "completed",
                result=result,
                event_type=event_type
            )
            logger.info(f"{self.name}: Completed {event_type} (job={job_id})")
            
        except Exception as e:
            logger.error(f"{self.name}: Error executing {tool_name}: {e}")
            self._execution_logger.log_tool_error(
                agent_name=self.name,
                job_id=job_id,
                original_event=event_type,
                tool_name=tool_name,
                error=str(e)
            )
            await self._publish_error(job_id, str(e), event_type=event_type)
    
    # --- AG2 Swarm Integration ---
    
    async def _handle_event(self, event):
        """
        Handle incoming event.
        
        When USE_AG2_SWARM is enabled, routes through AutoGen 0.4 Swarm
        for LLM-based reasoning. Otherwise falls back to direct dispatch.
        """
        if not USE_AG2_SWARM:
            return await super()._handle_event(event)
        
        # AG2 Swarm path
        job_id = event.job_id or "unknown"
        event_type = event.event_type
        payload = event.payload
        
        logger.info(f"{self.name}: [AG2 Swarm] Received {event_type} (job={job_id})")
        
        try:
            await self._publish_status(job_id, "started", event_type=event_type)
            
            # Build natural language task from event
            task = self._build_swarm_task(event_type, payload)
            logger.info(f"{self.name}: [AG2 Swarm] Task: {task}")
            
            # Run through Swarm
            result = await self._run_swarm(task)
            
            await self._publish_status(
                job_id,
                "completed",
                result=result,
                event_type=event_type,
            )
            logger.info(f"{self.name}: [AG2 Swarm] Completed {event_type} (job={job_id})")
            
        except Exception as e:
            logger.error(f"{self.name}: [AG2 Swarm] Error: {e}", exc_info=True)
            await self._publish_error(job_id, str(e), event_type=event_type)
    
    def _build_swarm_task(self, event_type: str, payload: Dict[str, Any]) -> str:
        """
        Build a natural language task description from event_type + payload.
        
        The Swarm coordinator uses this to decide which specialist agent to invoke.
        """
        # Clean payload: remove internal fields
        clean = {
            k: v for k, v in payload.items()
            if k not in (
                "job_id", "user_id", "session_id", "priority",
                "bubble_context", "metadata", "_user_input", "_conversation_history",
            ) and v  # skip empty values
        }
        
        # Use user_input if available (most natural for LLM)
        user_input = payload.get("_user_input", "")
        if user_input:
            return f"{user_input}\n\n[Event: {event_type}, Params: {json.dumps(clean, ensure_ascii=False)}]"
        
        # Fallback: structured task
        if clean:
            params_str = ", ".join(f"{k}={v!r}" for k, v in clean.items())
            return f"Führe aus: {event_type} mit {params_str}"
        
        return f"Führe aus: {event_type}"
    
    async def _run_swarm(self, task: str) -> str:
        """
        Run a task through AG2 Shuttle Swarm.
        
        Returns final response text from the Swarm.
        """
        from swarm.backend_agents.shuttle_swarm import get_shuttle_swarm
        
        swarm = get_shuttle_swarm()
        task_result = await swarm.run(task=task)
        
        # Extract final message content
        if task_result.messages:
            last_msg = task_result.messages[-1]
            content = getattr(last_msg, "content", str(last_msg))
            if content:
                return content
        
        return "Swarm hat die Aufgabe abgeschlossen (keine Antwort)."


# Singleton instance
_shuttle_orchestrator_agent: Optional[ShuttleOrchestratorAgent] = None


def get_shuttle_orchestrator_agent() -> ShuttleOrchestratorAgent:
    """Get or create ShuttleOrchestratorAgent singleton."""
    global _shuttle_orchestrator_agent
    if _shuttle_orchestrator_agent is None:
        _shuttle_orchestrator_agent = ShuttleOrchestratorAgent()
    return _shuttle_orchestrator_agent


__all__ = [
    "ShuttleOrchestratorAgent",
    "get_shuttle_orchestrator_agent",
]
