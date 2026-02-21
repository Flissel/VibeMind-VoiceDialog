"""
Base User Agent for VibeMind Event Buffer System

User Agents are the "face" of each space - they handle:
- Direct user interaction
- Clarification when input is unclear
- Delegation to workers for execution
- TTS output coordination
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Callable, TYPE_CHECKING

from swarm.navigation import SpaceType
from swarm.event_buffer import InputEvent, TaskInfo, get_event_buffer

if TYPE_CHECKING:
    from autogen_agentchat.agents import AssistantAgent

logger = logging.getLogger(__name__)


def _create_safe_function_tool(func: Callable, description: str):
    """
    Create a FunctionTool that handles empty arguments from OpenRouter/Claude.

    OpenRouter/Claude sometimes returns empty string "" instead of "{}"
    for no-argument functions, causing json.loads("") to fail.

    This solution: wrap the function to always accept kwargs and ignore empty args.
    """
    from autogen_core.tools import FunctionTool
    import functools
    import inspect

    # Get function signature
    sig = inspect.signature(func)
    params = list(sig.parameters.keys())

    if len(params) == 0:
        # No-arg function: wrap to accept but ignore any kwargs
        @functools.wraps(func)
        def wrapper(**kwargs) -> str:
            # Ignore any args passed, call original with no args
            return func()

        # Create FunctionTool from wrapper
        tool = FunctionTool(wrapper, description=description)
        # Override name to use original function name
        tool._name = func.__name__
        return tool
    else:
        # Function has params: use as-is
        return FunctionTool(func, description=description)


@dataclass
class UserAgentConfig:
    """Configuration for a User Agent."""
    name: str  # e.g., "rachel"
    display_name: str  # e.g., "Rachel"
    space_type: SpaceType
    voice_id: str  # ElevenLabs voice
    greeting: str = ""

    # Clarification settings
    max_clarification_attempts: int = 2
    clarification_phrases: List[str] = field(default_factory=list)


class BaseUserAgent(ABC):
    """
    Base class for User Agents.

    User Agents:
    - Receive user input from their space's queue
    - Clarify if input is unclear
    - Delegate to workers for execution
    - Coordinate TTS output
    """

    def __init__(
        self,
        config: UserAgentConfig,
        model_client: Any = None,
        tts_callback: Optional[Callable[[str], Any]] = None,
        use_cloud: bool = True,
    ):
        """
        Initialize user agent.

        Args:
            config: Agent configuration
            model_client: LLM client for clarification (if None, uses cloud client)
            tts_callback: Callback to speak responses
            use_cloud: If True and no model_client, use OpenRouter cloud client
        """
        self.config = config
        self._model_client = model_client
        self._use_cloud = use_cloud
        self.tts_callback = tts_callback

        # State
        self._is_active = False
        self._current_input: Optional[InputEvent] = None
        self._clarification_count = 0
        self._conversation_context: List[Dict[str, str]] = []

        # Workers managed by this agent
        self._workers: Dict[str, Any] = {}

        # AutoGen agent (created lazily)
        self._autogen_agent: Optional["AssistantAgent"] = None

        logger.info(f"BaseUserAgent initialized: {self.config.name}")

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def model_client(self):
        """Lazy-load model client (cloud client if not provided)."""
        if self._model_client is None and self._use_cloud:
            try:
                from swarm.cloud_client import get_model_client
                self._model_client = get_model_client()
                logger.info(f"{self.config.name}: Loaded cloud client (OpenRouter)")
            except Exception as e:
                logger.error(f"Failed to load cloud client: {e}")
        return self._model_client

    @property
    def display_name(self) -> str:
        return self.config.display_name

    @property
    def space_type(self) -> SpaceType:
        return self.config.space_type

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get the system prompt for this user agent."""
        pass

    @abstractmethod
    def get_tools(self) -> List[Callable]:
        """Get the tools available to this user agent."""
        pass

    @abstractmethod
    async def process_input(self, event: InputEvent) -> str:
        """
        Process user input and return response.

        This is the main entry point for handling user input.
        Subclasses should implement domain-specific logic.

        Args:
            event: The input event to process

        Returns:
            Response text for TTS
        """
        pass

    async def clarify(self, original_input: str, reason: str = "") -> Optional[str]:
        """
        Ask user for clarification.

        Args:
            original_input: The unclear input
            reason: Why clarification is needed

        Returns:
            Clarification question to ask, or None if max attempts reached
        """
        self._clarification_count += 1

        if self._clarification_count > self.config.max_clarification_attempts:
            logger.warning(f"Max clarification attempts reached for: {original_input}")
            return None

        # Build clarification question
        phrases = self.config.clarification_phrases or [
            "Kannst du das genauer erklären?",
            "Was genau meinst du damit?",
            "Ich brauche mehr Details.",
        ]

        question = phrases[min(self._clarification_count - 1, len(phrases) - 1)]
        if reason:
            question = f"{reason} {question}"

        return question

    async def delegate_to_worker(
        self,
        worker_name: str,
        task: InputEvent,
    ) -> Optional[TaskInfo]:
        """
        Delegate a task to a worker.

        Args:
            worker_name: Name of worker to delegate to
            task: The task to execute

        Returns:
            TaskInfo if worker found, None otherwise
        """
        worker = self._workers.get(worker_name)
        if not worker:
            logger.warning(f"Worker not found: {worker_name}")
            return None

        # Create task info
        event_buffer = get_event_buffer()
        task_info = event_buffer.start_task(task)

        # Queue task for worker
        if hasattr(worker, 'queue_task'):
            await worker.queue_task(task_info)
        else:
            logger.warning(f"Worker {worker_name} has no queue_task method")

        return task_info

    def register_worker(self, name: str, worker: Any) -> None:
        """Register a worker with this user agent."""
        self._workers[name] = worker
        logger.debug(f"Registered worker {name} with {self.name}")

    async def speak(self, text: str) -> None:
        """
        Send text to TTS.

        Args:
            text: Text to speak
        """
        if self.tts_callback:
            try:
                result = self.tts_callback(text)
                if asyncio.iscoroutine(result):
                    await result
            except Exception as e:
                logger.error(f"TTS callback error: {e}")

    def reset_clarification(self) -> None:
        """Reset clarification counter."""
        self._clarification_count = 0

    def add_to_context(self, role: str, content: str) -> None:
        """Add message to conversation context."""
        self._conversation_context.append({"role": role, "content": content})
        # Keep context bounded
        if len(self._conversation_context) > 20:
            self._conversation_context = self._conversation_context[-10:]

    def clear_context(self) -> None:
        """Clear conversation context."""
        self._conversation_context.clear()

    def create_autogen_agent(self) -> "AssistantAgent":
        """
        Create AutoGen AssistantAgent for this user agent.

        Returns:
            Configured AssistantAgent
        """
        from autogen_agentchat.agents import AssistantAgent
        from autogen_core.tools import FunctionTool

        if self._autogen_agent is None:
            # Wrap raw functions in FunctionTool for proper AutoGen tool calling
            raw_tools = self.get_tools()
            wrapped_tools = []
            for func in raw_tools:
                # Use function's docstring as description, fallback to name
                description = func.__doc__ or f"Execute {func.__name__}"
                # Clean up multi-line docstrings
                if description:
                    description = description.strip().split('\n')[0]

                # Create SafeFunctionTool that handles empty arguments
                safe_tool = _create_safe_function_tool(func, description)
                wrapped_tools.append(safe_tool)
                logger.debug(f"Wrapped tool: {func.__name__} -> {description[:50]}...")

            logger.info(f"Wrapped {len(wrapped_tools)} tools for {self.name}")

            self._autogen_agent = AssistantAgent(
                name=f"{self.name}_user_agent",
                model_client=self.model_client,
                tools=wrapped_tools,
                handoffs=["shuttle_agent", "user"],
                system_message=self.get_system_prompt(),
            )
            logger.info(f"Created AutoGen agent for {self.name}")

        return self._autogen_agent

    async def process_input_with_llm(self, event: InputEvent) -> str:
        """
        Process input using LLM-based tool selection via AutoGen.

        The LLM decides which tools to call based on:
        - User input semantics
        - Tool descriptions
        - Conversation history

        Args:
            event: Input event to process

        Returns:
            Response text from LLM (after tool execution)
        """
        if self.model_client is None:
            logger.warning(f"{self.name}: No model_client, falling back to clarification")
            return await self.clarify(event.text, "Ich kann das gerade nicht verarbeiten.")

        try:
            # Ensure AutoGen agent exists
            agent = self.create_autogen_agent()

            # Add to conversation context
            self.add_to_context("user", event.text)

            # Reset agent state and run with user input
            # AutoGen AssistantAgent handles tool selection internally
            from autogen_agentchat.teams import RoundRobinGroupChat
            from autogen_agentchat.conditions import TextMentionTermination, MaxMessageTermination

            # Create a simple single-agent "team" for tool execution
            termination = (
                TextMentionTermination("TERMINATE") |
                MaxMessageTermination(max_messages=10)
            )

            team = RoundRobinGroupChat(
                participants=[agent],
                termination_condition=termination,
            )

            # Run the agent with the user's input
            logger.info(f"{self.name}: Processing via LLM: {event.text[:50]}...")
            result = await team.run(task=event.text)

            # Extract response text from result
            response = self._extract_llm_response(result)

            # Add response to context
            self.add_to_context("assistant", response)

            # Reset clarification count on successful processing
            self.reset_clarification()

            logger.info(f"{self.name}: LLM response: {response[:100]}...")
            return response

        except Exception as e:
            logger.error(f"{self.name}: LLM processing error: {e}")
            import traceback
            traceback.print_exc()
            # Fallback to clarification
            return f"Es gab einen Fehler bei der Verarbeitung: {str(e)}"

    def _extract_llm_response(self, result) -> str:
        """
        Extract text response from AutoGen result.

        Args:
            result: Result from team.run()

        Returns:
            Extracted text response
        """
        try:
            if hasattr(result, 'messages') and result.messages:
                # Find the last meaningful response
                for msg in reversed(result.messages):
                    if hasattr(msg, 'content'):
                        content = msg.content

                        # Skip function call lists
                        if isinstance(content, list):
                            continue

                        # Skip empty content
                        if not content or not str(content).strip():
                            continue

                        # Skip "Transferred to..." messages
                        if str(content).startswith("Transferred to"):
                            continue

                        # Skip TERMINATE markers
                        if "TERMINATE" in str(content):
                            content = str(content).replace("TERMINATE", "").strip()
                            if content:
                                return content
                            continue

                        return str(content)

            return "Aufgabe erledigt."

        except Exception as e:
            logger.warning(f"Response extraction error: {e}")
            return "Ich konnte die Antwort nicht formatieren."


# Shared clarification phrases (German + English)
CLARIFICATION_PHRASES_DE = [
    "Kannst du das genauer erklären?",
    "Was genau meinst du damit?",
    "Ich brauche mehr Details dazu.",
]

CLARIFICATION_PHRASES_EN = [
    "Could you explain that more specifically?",
    "What exactly do you mean?",
    "I need more details about that.",
]


__all__ = [
    "BaseUserAgent",
    "UserAgentConfig",
    "CLARIFICATION_PHRASES_DE",
    "CLARIFICATION_PHRASES_EN",
]
