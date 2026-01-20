"""
Base Backend Agent - Shared functionality for all backend agents

Provides common infrastructure for:
- Redis stream subscription
- Tool loading and mapping
- Status publishing
- Error handling
"""

import asyncio
import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, Optional

from swarm.event_bus import EventBus, SwarmEvent, get_event_bus
from swarm.debugging.agent_execution_logger import get_agent_execution_logger

logger = logging.getLogger(__name__)


class BaseBackendAgent(ABC):
    """
    Abstract base class for backend agents.

    Subclasses must implement:
    - stream: The Redis stream to listen on
    - _load_tools(): Returns dict mapping tool names to functions
    - _get_tool_name(): Maps event_type to tool name

    Subclasses may define:
    - PARAM_MAPPING: Dict mapping event_type to {classifier_param: tool_param}
    """

    # Parameter normalization: subclasses can override
    # Format: {event_type: {classifier_param: tool_param}}
    PARAM_MAPPING: Dict[str, Dict[str, str]] = {}

    def __init__(self):
        self._bus: Optional[EventBus] = None
        self._tools: Dict[str, Callable] = {}
        self._running = False
        self._execution_logger = get_agent_execution_logger()

    @property
    @abstractmethod
    def stream(self) -> str:
        """The Redis stream this agent listens to."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Agent name for logging."""
        pass

    @property
    def bus(self) -> EventBus:
        """Lazy-load EventBus."""
        if self._bus is None:
            self._bus = get_event_bus()
        return self._bus

    @property
    def tools(self) -> Dict[str, Callable]:
        """Lazy-load tools."""
        if not self._tools:
            self._tools = self._load_tools()
        return self._tools

    @abstractmethod
    def _load_tools(self) -> Dict[str, Callable]:
        """
        Load tools for this agent.

        Returns:
            Dict mapping tool function names to functions
        """
        pass

    @abstractmethod
    def _get_tool_name(self, event_type: str) -> Optional[str]:
        """
        Map event_type to tool function name.

        Args:
            event_type: Event type from Redis (e.g., "bubble.create")

        Returns:
            Tool function name (e.g., "create_bubble") or None
        """
        pass

    def _normalize_params(self, event_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize parameter names for a given event type.

        Maps classifier output names to tool expected names using PARAM_MAPPING.
        For example: {"title": "X"} -> {"bubble_name": "X"} for bubble.enter

        Also handles "_inject" key to inject fixed parameter values.
        For example: {"_inject": {"target_format": "note"}} adds target_format="note"

        Args:
            event_type: The event type being processed
            params: Original parameters from classifier

        Returns:
            Normalized parameters with correct names for the tool
        """
        mapping = self.PARAM_MAPPING.get(event_type, {})
        if not mapping:
            return params

        normalized = {}
        for key, value in params.items():
            # Check if this key should be renamed
            new_key = mapping.get(key, key)
            # Don't overwrite if the target key already exists
            if new_key not in normalized:
                normalized[new_key] = value
            elif key not in mapping:
                # Keep original if not in mapping and target exists
                normalized[key] = value

        # Handle _inject for fixed parameter injection
        inject_params = mapping.get("_inject", {})
        if inject_params:
            for inject_key, inject_value in inject_params.items():
                if inject_key not in normalized:
                    normalized[inject_key] = inject_value
                    logger.debug(f"Injected param for {event_type}: {inject_key}={inject_value}")

        logger.debug(f"Normalized params for {event_type}: {params} -> {normalized}")
        return normalized

    async def setup_consumer_group(
        self,
        group_name: str,
        stream: str = None
    ) -> bool:
        """
        Set up a Redis consumer group for parallel processing.

        Consumer groups allow multiple workers to process events from
        the same stream without duplicates.

        Args:
            group_name: Name for the consumer group
            stream: Stream name (defaults to self.stream)

        Returns:
            True if created successfully (or already exists)
        """
        target_stream = stream or self.stream

        try:
            redis = await self.bus._get_redis()

            try:
                await redis.xgroup_create(
                    target_stream,
                    group_name,
                    id='0',
                    mkstream=True
                )
                logger.info(f"{self.name}: Created consumer group '{group_name}' for {target_stream}")
            except Exception as e:
                if "BUSYGROUP" not in str(e):
                    raise
                logger.debug(f"{self.name}: Consumer group '{group_name}' already exists")

            return True

        except Exception as e:
            logger.error(f"{self.name}: Failed to setup consumer group: {e}")
            return False

    async def read_with_consumer_group(
        self,
        group_name: str,
        consumer_name: str,
        stream: str = None,
        count: int = 1,
        block_ms: int = 5000
    ) -> list:
        """
        Read events using a Redis consumer group.

        This ensures events are distributed across workers without duplicates.
        Each consumer in the group gets unique events.

        Args:
            group_name: Consumer group name
            consumer_name: This consumer's unique name
            stream: Stream to read from (defaults to self.stream)
            count: Max events to read per call
            block_ms: Milliseconds to block waiting for events

        Returns:
            List of (message_id, data) tuples
        """
        target_stream = stream or self.stream

        try:
            redis = await self.bus._get_redis()

            messages = await redis.xreadgroup(
                group_name,
                consumer_name,
                {target_stream: '>'},  # '>' means new messages only
                count=count,
                block=block_ms
            )

            if not messages:
                return []

            # Flatten the nested structure
            result = []
            for stream_name, stream_messages in messages:
                for msg_id, data in stream_messages:
                    result.append((msg_id, data))

            return result

        except Exception as e:
            logger.error(f"{self.name}: Consumer group read error: {e}")
            return []

    async def ack_message(
        self,
        group_name: str,
        message_id: str,
        stream: str = None
    ) -> bool:
        """
        Acknowledge successful processing of a message.

        Messages must be ACKed to remove them from pending entries.
        Un-ACKed messages can be claimed by other consumers for retry.

        Args:
            group_name: Consumer group name
            message_id: Message ID to acknowledge
            stream: Stream name (defaults to self.stream)

        Returns:
            True if acknowledged successfully
        """
        target_stream = stream or self.stream

        try:
            redis = await self.bus._get_redis()
            await redis.xack(target_stream, group_name, message_id)
            return True
        except Exception as e:
            logger.error(f"{self.name}: Failed to ACK message {message_id}: {e}")
            return False

    async def get_pending_messages(
        self,
        group_name: str,
        stream: str = None,
        count: int = 10
    ) -> list:
        """
        Get pending (un-ACKed) messages for this consumer group.

        Useful for monitoring and handling failed message processing.

        Args:
            group_name: Consumer group name
            stream: Stream name (defaults to self.stream)
            count: Max messages to return

        Returns:
            List of pending message info
        """
        target_stream = stream or self.stream

        try:
            redis = await self.bus._get_redis()
            pending = await redis.xpending(target_stream, group_name, count=count)
            return pending
        except Exception as e:
            logger.error(f"{self.name}: Failed to get pending messages: {e}")
            return []

    def _extract_params_from_transcript(self, event_type: str, user_input: str) -> Dict[str, Any]:
        """
        Extract missing parameters from user transcript using regex.

        This is a fallback when the LLM doesn't extract parameters properly.

        Args:
            event_type: The event type being processed
            user_input: Original user transcript

        Returns:
            Dictionary of extracted parameters
        """
        if not user_input:
            return {}

        extracted = {}
        user_input_lower = user_input.lower()

        if event_type == "bubble.enter":
            # Extract space name: "gehe in Space X", "navigiere zu X", etc.
            patterns = [
                r"(?:space|bubble|bereich)\s+['\"]?([^'\"]+?)['\"]?\s*$",
                r"(?:space|bubble|bereich)\s+['\"]?([^'\"]+?)['\"]?(?:\s+und|\s+dann|\.|$)",
                r"(?:in|zu|nach)\s+(?:den?\s+)?(?:space|bubble)?\s*['\"]?([A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9\s-]+)",
                r"navigiere?\s+(?:in|zu|nach)?\s*['\"]?([A-Za-zäöüÄÖÜß][A-Za-zäöüÄÖÜß0-9\s-]+)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    name = match.group(1).strip()
                    # Clean up common trailing words
                    name = re.sub(r'\s+(und|dann|rein|hinein)$', '', name, flags=re.IGNORECASE)
                    if name and len(name) > 1:
                        extracted["bubble_name"] = name
                        break

        elif event_type == "idea.create":
            # Extract idea title
            patterns = [
                r"(?:idee|note|notiz)\s+['\"]?([^'\"]+?)['\"]?\s*$",
                r"erstelle\s+(?:eine?\s+)?(?:idee|note|notiz)?\s*['\"]?(.+?)(?:\s+(?:mit|und|im)|$)",
                r"(?:neue?|erstelle)\s+(?:idee|note|notiz)\s+['\"]?(.+?)['\"]?(?:\s|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    title = match.group(1).strip()
                    if title and len(title) > 1:
                        extracted["title"] = title
                        break

        elif event_type == "idea.find":
            # Extract search query
            patterns = [
                r"(?:suche?|finde?)\s+(?:nach\s+)?['\"]?(.+?)['\"]?(?:\s|$)",
                r"(?:zeig|list)e?\s+(?:mir\s+)?(?:idee|note)?\s*['\"]?(.+?)['\"]?(?:\s|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    query = match.group(1).strip()
                    if query and len(query) > 1:
                        extracted["query"] = query
                        break

        elif event_type == "idea.connect":
            # Extract two idea names: "verbinde X mit Y"
            patterns = [
                r"(?:verbinde|verlinke|connect)\s+['\"]?(.+?)['\"]?\s+(?:mit|und|with|to)\s+['\"]?(.+?)['\"]?(?:\s|$)",
            ]
            for pattern in patterns:
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    extracted["idea1"] = match.group(1).strip()
                    extracted["idea2"] = match.group(2).strip()
                    break

        if extracted:
            logger.info(f"{self.name}: Extracted params from transcript: {extracted}")

        return extracted

    async def start(self):
        """Start listening to the stream."""
        if self._running:
            logger.warning(f"{self.name} already running")
            return

        self._running = True
        await self.bus.subscribe(self.stream, self._handle_event)
        logger.info(f"{self.name} started, listening on {self.stream}")

    async def stop(self):
        """Stop the agent."""
        self._running = False
        logger.info(f"{self.name} stopped")

    async def _handle_event(self, event: SwarmEvent):
        """
        Handle incoming event from Redis.

        Args:
            event: SwarmEvent from the stream
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

            # Normalize parameter names (e.g., "title" -> "bubble_name" for bubble.enter)
            tool_params = self._normalize_params(event_type, tool_params)

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

            # Execute the tool
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
            # Log tool error
            self._execution_logger.log_tool_error(
                agent_name=self.name,
                job_id=job_id,
                original_event=event_type,
                tool_name=tool_name,
                error=str(e)
            )
            await self._publish_error(job_id, str(e), event_type=event_type)

    async def _publish_status(
        self,
        job_id: str,
        status: str,
        result: Any = None,
        progress: int = 0,
        stage: str = "",
        event_type: str = ""
    ):
        """
        Publish status update to events:status stream.

        Args:
            job_id: Job ID
            status: Status string ("started", "progress", "completed")
            result: Optional result data
            progress: Progress percentage (0-100)
            stage: Current stage description
            event_type: Original event type
        """
        event = SwarmEvent(
            stream=EventBus.STREAM_STATUS,
            event_type=f"task.{status}",
            payload={
                "job_id": job_id,
                "status": status,
                "result": result,
                "progress": progress,
                "stage": stage,
                "agent": self.name,
                "original_event": event_type,
            },
            job_id=job_id
        )
        await self.bus.publish(event)

    async def _publish_error(
        self,
        job_id: str,
        error: str,
        event_type: str = ""
    ):
        """
        Publish error status to events:status stream.

        Args:
            job_id: Job ID
            error: Error message
            event_type: Original event type
        """
        event = SwarmEvent(
            stream=EventBus.STREAM_STATUS,
            event_type="task.error",
            payload={
                "job_id": job_id,
                "status": "error",
                "error": error,
                "agent": self.name,
                "original_event": event_type,
            },
            job_id=job_id
        )
        await self.bus.publish(event)
        logger.error(f"{self.name}: Error for job {job_id}: {error}")


__all__ = ["BaseBackendAgent"]
