"""
OpenClaw Desktop Backend Agent

Backend agent for the Desktop Space that listens to the desktop Redis stream
and routes tasks through the AutoGen Society of Mind Swarm.

Integrates with the existing 4-stream architecture:
- events:tasks:ideas
- events:tasks:bubbles
- events:tasks:coding
- events:tasks:desktop  ← This agent

Usage:
    agent = get_openclaw_desktop_agent()
    await agent.start()  # Starts listening to Redis stream
"""

import asyncio
import json
import logging
import os
from typing import Dict, Callable, Optional, Any

from swarm.backend_agents.base_agent import BaseBackendAgent
from swarm.event_bus import SwarmEvent

logger = logging.getLogger(__name__)

# Check if AG2 Swarm should be used
USE_AG2_DESKTOP_SWARM = os.getenv("USE_AG2_DESKTOP_SWARM", "true").lower() in ("true", "1", "yes")


class OpenClawDesktopAgent(BaseBackendAgent):
    """
    Backend agent for Desktop Space with AutoGen Society of Mind.

    Extends BaseBackendAgent to use the standard event bus subscription.
    When USE_AG2_DESKTOP_SWARM is enabled, routes complex tasks through
    the AutoGen Desktop Swarm for LLM-based reasoning and execution.
    """

    # Event type to tool name mapping
    EVENT_TO_TOOL = {
        # Core desktop events
        "desktop.execute": "execute_desktop_task",
        "desktop.task": "execute_desktop_task",
        "desktop.click": "click_element",
        "desktop.type": "type_text",
        "desktop.press_key": "press_key",
        "desktop.screenshot": "take_screenshot",
        "desktop.scroll": "scroll_screen",
        "desktop.open_app": "open_app",
        # Vision events
        "desktop.scan": "moire_scan",
        "desktop.moire.scan": "moire_scan",
        "desktop.find": "moire_find_element",
        "desktop.moire.find": "moire_find_element",
        # Task management
        "desktop.task.create": "create_task_node",
        "desktop.task.update": "update_task_status",
        "desktop.task.list": "get_task_list",
        # Messaging events (ClawedVoice)
        "messaging.whatsapp": "send_whatsapp",
        "messaging.telegram": "send_telegram",
        "messaging.send": "send_whatsapp",  # default to whatsapp
        "web.search": "web_search",
        "web.fetch": "web_fetch",
        "openclaw.status": "get_openclaw_status",
        "openclaw.notifications": "get_pending_notifications",
    }

    # Parameter normalization (classifier output → tool params)
    PARAM_MAPPING = {
        "desktop.execute": {
            "description": "task_description",
            "aufgabe": "task_description",
            "task": "task_description",
            "goal": "task_description",
        },
        "desktop.open_app": {
            "name": "app_name",
            "app": "app_name",
            "anwendung": "app_name",
            "application": "app_name",
        },
        "desktop.click": {
            "element": "element_description",
            "target": "element_description",
            "ziel": "element_description",
            "button": "element_description",
        },
        "desktop.type": {
            "content": "text",
            "inhalt": "text",
            "input": "text",
        },
        "desktop.press_key": {
            "taste": "key",
            "shortcut": "key",
            "hotkey": "key",
        },
        "desktop.scroll": {
            "richtung": "direction",
            "steps": "amount",
            "lines": "amount",
        },
        # Messaging param mappings
        "messaging.whatsapp": {
            "to": "recipient",
            "nummer": "recipient",
            "empfaenger": "recipient",
            "text": "message",
            "nachricht": "message",
            "content": "message",
        },
        "messaging.telegram": {
            "to": "recipient",
            "user": "recipient",
            "empfaenger": "recipient",
            "text": "message",
            "nachricht": "message",
            "content": "message",
        },
        "web.search": {
            "suche": "query",
            "anfrage": "query",
            "q": "query",
        },
        "web.fetch": {
            "seite": "url",
            "link": "url",
            "adresse": "url",
        },
    }

    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "OpenClawDesktopAgent"

    @property
    def stream(self) -> str:
        return "events:tasks:desktop"

    def _load_tools(self) -> Dict[str, Callable]:
        """Load desktop tools."""
        tools = {}

        try:
            from spaces.desktop.tools.adapted_desktop_tools import (
                execute_desktop_task,
                click_element,
                type_text,
                press_key,
                take_screenshot,
                scroll_screen,
                open_app,
                moire_scan,
                moire_find_element,
                create_task_node,
                update_task_status,
                get_task_list,
            )

            tools.update({
                "execute_desktop_task": execute_desktop_task,
                "click_element": click_element,
                "type_text": type_text,
                "press_key": press_key,
                "take_screenshot": take_screenshot,
                "scroll_screen": scroll_screen,
                "open_app": open_app,
                "moire_scan": moire_scan,
                "moire_find_element": moire_find_element,
                "create_task_node": create_task_node,
                "update_task_status": update_task_status,
                "get_task_list": get_task_list,
            })
            logger.info(f"{self.name}: Loaded {len(tools)} desktop tools")

        except ImportError as e:
            logger.warning(f"{self.name}: Could not load desktop tools: {e}")

        # Load messaging tools (ClawedVoice)
        try:
            from spaces.OpenClaw.tools.messaging_tools import (
                send_whatsapp,
                send_telegram,
                web_search,
                web_fetch,
                get_pending_notifications,
                get_openclaw_status,
            )

            tools.update({
                "send_whatsapp": send_whatsapp,
                "send_telegram": send_telegram,
                "web_search": web_search,
                "web_fetch": web_fetch,
                "get_pending_notifications": get_pending_notifications,
                "get_openclaw_status": get_openclaw_status,
            })
            logger.info(f"{self.name}: Loaded messaging tools (total: {len(tools)})")

        except ImportError as e:
            logger.warning(f"{self.name}: Could not load messaging tools: {e}")

        return tools

    def _get_tool_name(self, event_type: str) -> Optional[str]:
        """Map event type to tool name."""
        return self.EVENT_TO_TOOL.get(event_type)

    async def _handle_event(self, event: SwarmEvent):
        """
        Handle incoming event.

        When USE_AG2_DESKTOP_SWARM is enabled, routes through AutoGen Swarm.
        Otherwise, delegates to BaseBackendAgent's standard tool execution.
        """
        if USE_AG2_DESKTOP_SWARM:
            job_id = event.job_id or "unknown"
            event_type = event.event_type
            payload = event.payload or {}
            logger.info(f"{self.name}: Received {event_type} (job={job_id}), routing via Swarm")

            try:
                await self._publish_status(job_id, "started", event_type=event_type)
                result = await self._handle_via_swarm(event_type, payload, job_id)
                await self._publish_status(job_id, "completed", result=result, event_type=event_type)
            except Exception as e:
                logger.error(f"{self.name}: Swarm error: {e}")
                await self._publish_error(job_id, str(e), event_type=event_type)
        else:
            # Use BaseBackendAgent's standard tool execution
            await super()._handle_event(event)

    async def _handle_via_swarm(
        self,
        event_type: str,
        payload: Dict[str, Any],
        job_id: str
    ) -> str:
        """Handle event through AutoGen Desktop Swarm (with optional MCP + Vision QA)."""
        from spaces.OpenClaw.agents.desktop_swarm import run_desktop_swarm

        # Build natural language task from event
        task = self._build_swarm_task(event_type, payload)
        logger.info(f"{self.name}: [Swarm] Task: {task}")

        try:
            # run_desktop_swarm handles MCP lifecycle and uses the upgraded
            # 3-agent swarm (Coordinator + ClaudeCLI + Operator)
            result = await run_desktop_swarm(task=task)

            # Extract response from last message
            if result.messages:
                last_msg = result.messages[-1]
                content = getattr(last_msg, "content", str(last_msg))
                if content:
                    logger.info(f"{self.name}: [Swarm] Completed")
                    return content

            return "Desktop Swarm hat die Aufgabe abgeschlossen."

        except Exception as e:
            logger.error(f"{self.name}: [Swarm] Error: {e}", exc_info=True)
            return f"Swarm-Fehler: {str(e)}"

    def _build_swarm_task(self, event_type: str, payload: Dict[str, Any]) -> str:
        """Build natural language task from event_type + payload."""
        # Extract user input if available
        user_input = payload.get("_user_input", "")
        if user_input:
            return user_input

        # Build from event type and params
        clean_params = {
            k: v for k, v in payload.items()
            if not k.startswith("_") and v
        }

        # Event-specific task building
        if event_type == "desktop.open_app":
            app = clean_params.get("app_name", clean_params.get("name", ""))
            return f"Oeffne die Anwendung: {app}"

        if event_type == "desktop.click":
            element = clean_params.get("element_description", clean_params.get("element", ""))
            return f"Klicke auf das Element: {element}"

        if event_type == "desktop.type":
            text = clean_params.get("text", "")
            return f"Gib folgenden Text ein: {text}"

        if event_type == "desktop.press_key":
            key = clean_params.get("key", "")
            return f"Druecke die Taste: {key}"

        if event_type in ("desktop.execute", "desktop.task"):
            task = clean_params.get("task_description", clean_params.get("description", ""))
            return f"Fuehre folgende Desktop-Aufgabe aus: {task}"

        if event_type in ("desktop.scan", "desktop.moire.scan"):
            return "Scanne den Bildschirm und beschreibe was du siehst."

        if event_type == "desktop.screenshot":
            return "Mache einen Screenshot."

        # Fallback
        if clean_params:
            params_str = ", ".join(f"{k}={v!r}" for k, v in clean_params.items())
            return f"Desktop-Aktion: {event_type} mit {params_str}"

        return f"Fuehre Desktop-Aktion aus: {event_type}"

    # start() and stop() inherited from BaseBackendAgent


# --- Singleton Pattern ---

_openclaw_agent: Optional[OpenClawDesktopAgent] = None


def get_openclaw_desktop_agent() -> OpenClawDesktopAgent:
    """Get or create OpenClawDesktopAgent singleton."""
    global _openclaw_agent
    if _openclaw_agent is None:
        _openclaw_agent = OpenClawDesktopAgent()
    return _openclaw_agent


__all__ = [
    "OpenClawDesktopAgent",
    "get_openclaw_desktop_agent",
    "USE_AG2_DESKTOP_SWARM",
]
