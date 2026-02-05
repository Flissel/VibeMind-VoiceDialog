"""
Voice Bridge for VibeMind Swarm

Bridges ElevenLabs voice input to the AutoGen Swarm team.
Provides a tool that can be registered with ElevenLabs ClientTools.
"""

import asyncio
import logging
from typing import Dict, Any, Optional, Callable
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SwarmResult:
    """Result from Swarm execution."""
    response: str
    agent_name: str
    tool_calls: int = 0
    handoffs: int = 0
    success: bool = True
    error: Optional[str] = None


class VoiceBridge:
    """
    Bridge between ElevenLabs voice and AutoGen Swarm team.

    Converts voice input to Swarm tasks and extracts spoken responses.
    """

    def __init__(
        self,
        swarm_team,
        event_manager=None,
        entry_agent: str = "planning_agent",  # Start with planning agent for complex requests
    ):
        """
        Initialize the voice bridge.

        Args:
            swarm_team: The AutoGen Swarm team instance
            event_manager: Optional RedisEventManager for event publishing
            entry_agent: Name of the agent to start with (now planning_agent)
        """
        self.team = swarm_team
        self.event_manager = event_manager
        self.entry_agent = entry_agent
        self._conversation_context = []
        self._loop = None
        self._transcript_manager = None

    def _get_event_loop(self):
        """Get or create an event loop."""
        if self._loop is None or self._loop.is_closed():
            try:
                self._loop = asyncio.get_event_loop()
            except RuntimeError:
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        return self._loop

    async def handle_voice_input_async(self, text: str) -> SwarmResult:
        """
        Process voice input through Swarm asynchronously.

        Args:
            text: Transcribed voice input

        Returns:
            SwarmResult with response text and metadata
        """
        logger.info(f"Voice input: {text}")

        # Initialize transcript manager if needed
        if self._transcript_manager is None:
            from swarm.tools.transcript_manager import get_transcript_manager
            self._transcript_manager = await get_transcript_manager()

        # Add user input to transcript
        await self._transcript_manager.add_entry(
            "user_input",
            text,
            {"agent": "user", "input_type": "voice"}
        )

        try:
            # Reset swarm state before each run to start fresh
            # This prevents "handoff target user is not a participant" errors
            await self.team.reset()

            # Run the swarm with the input (termination_condition is set at team creation)
            result = await self.team.run(task=text)

            # Extract the final response
            response_text = self._extract_response(result)
            agent_name = self._get_responding_agent(result)

            # Count tool calls and handoffs
            tool_calls, handoffs = self._count_actions(result)

            # Add agent response to transcript
            await self._transcript_manager.add_entry(
                "agent_response",
                response_text,
                {
                    "agent": agent_name,
                    "tool_calls": tool_calls,
                    "handoffs": handoffs,
                    "response_type": "voice"
                }
            )

            # Publish event if manager available
            if self.event_manager:
                from swarm.event_streams import SpaceEvent, EventType
                await self.event_manager.publish_event(
                    "voice",
                    SpaceEvent(
                        event_type=EventType.AGENT_HANDOFF,
                        agent=agent_name,
                        payload={
                            "input": text,
                            "response": response_text[:200],
                            "tool_calls": tool_calls,
                            "handoffs": handoffs,
                        }
                    )
                )

            logger.info(f"Response from {agent_name}: {response_text[:100]}...")

            return SwarmResult(
                response=response_text,
                agent_name=agent_name,
                tool_calls=tool_calls,
                handoffs=handoffs,
                success=True,
            )

        except Exception as e:
            logger.error(f"Swarm execution error: {e}")

            # Add error to transcript
            await self._transcript_manager.add_entry(
                "system_event",
                f"Error: {str(e)}",
                {"error": True, "error_type": "swarm_execution"}
            )

            return SwarmResult(
                response=f"Sorry, I encountered an error: {str(e)}",
                agent_name="system",
                success=False,
                error=str(e),
            )

    def handle_voice_input(self, text: str) -> str:
        """
        Process voice input synchronously.

        Args:
            text: Transcribed voice input

        Returns:
            Response text for TTS
        """
        loop = self._get_event_loop()

        if loop.is_running():
            # Already in async context - create task
            future = asyncio.ensure_future(self.handle_voice_input_async(text))
            # This is tricky - we're in a sync context but loop is running
            # Best effort: return placeholder
            return "Processing your request..."

        # Normal sync call
        result = loop.run_until_complete(self.handle_voice_input_async(text))
        return result.response

    def _extract_response(self, result) -> str:
        """Extract the final text response from Swarm result."""
        try:
            # TaskResult has messages attribute
            if hasattr(result, 'messages') and result.messages:
                # Get last text message that's not a handoff or tool call
                for msg in reversed(result.messages):
                    if hasattr(msg, 'content'):
                        content = msg.content
                        # Skip list content (FunctionCall results)
                        if isinstance(content, list):
                            continue
                        # Skip empty content
                        if not content or not str(content).strip():
                            continue
                        # Skip handoff messages
                        if str(content).startswith("Transferred to"):
                            continue
                        # Skip tool result markers
                        if str(content).startswith("[") and "]" in str(content)[:50]:
                            continue
                        return str(content)

            # Second pass: look for any ToolCallResultMessage with content
            if hasattr(result, 'messages') and result.messages:
                for msg in reversed(result.messages):
                    msg_type = type(msg).__name__
                    if 'Result' in msg_type and hasattr(msg, 'content'):
                        content = str(msg.content)
                        if content and content.strip() and len(content) > 10:
                            return content

            return "Task completed."

        except Exception as e:
            logger.warning(f"Error extracting response: {e}")
            return "I completed the task but couldn't format the response."

    def _get_responding_agent(self, result) -> str:
        """Get the name of the agent that provided the final response."""
        try:
            if hasattr(result, 'messages') and result.messages:
                last_msg = result.messages[-1]
                if hasattr(last_msg, 'source'):
                    return last_msg.source
        except Exception:
            pass
        return "unknown"

    def _count_actions(self, result) -> tuple:
        """Count tool calls and handoffs in the result."""
        tool_calls = 0
        handoffs = 0

        try:
            if hasattr(result, 'messages'):
                for msg in result.messages:
                    # Check for tool calls
                    if hasattr(msg, 'content'):
                        content = msg.content
                        if isinstance(content, list):
                            # FunctionCall list
                            tool_calls += len(content)
                    # Check for handoffs
                    if hasattr(msg, 'target'):
                        handoffs += 1
        except Exception:
            pass

        return tool_calls, handoffs

    def as_elevenlabs_tool(self) -> Callable:
        """
        Return a function compatible with ElevenLabs ClientTools.

        The returned function takes params dict and returns string response.
        """
        def process_command(params: Dict[str, Any]) -> str:
            """Process voice command through Swarm."""
            text = params.get("command", params.get("text", ""))
            if not text:
                return "I didn't catch that. Could you repeat?"

            return self.handle_voice_input(text)

        return process_command

    def as_simple_tool(self) -> Callable:
        """
        Return a simple callable for direct use.
        """
        return lambda text: self.handle_voice_input(text)


async def create_voice_bridge(
    model_client=None,
    event_manager=None,
) -> VoiceBridge:
    """
    Create a VoiceBridge with a full Swarm team.

    Args:
        model_client: Optional pre-configured model client
        event_manager: Optional RedisEventManager

    Returns:
        Configured VoiceBridge instance
    """
    from autogen_agentchat.teams import Swarm
    from autogen_agentchat.conditions import TextMentionTermination, HandoffTermination, MaxMessageTermination

    # Get or create model client
    if model_client is None:
        from swarm.ollama_client import get_ollama_client
        ollama = get_ollama_client()
        model_client = ollama.client

    # Get or create event manager
    if event_manager is None:
        from swarm.event_streams import get_event_manager
        event_manager = await get_event_manager()

    # Create all agents
    from swarm.agents import (
        create_ideas_agent,
        create_shuttle_agent,
        create_coding_agent,
        create_desktop_agent,
        create_data_agent,
        create_query_agent,
        create_planning_agent,
    )

    ideas_agent, ideas_subs = create_ideas_agent(model_client)
    shuttle_agent = create_shuttle_agent(model_client)
    coding_agent, coding_subs = create_coding_agent(model_client)
    desktop_agent, desktop_subs = create_desktop_agent(model_client)

    # Create background data agent (silent operation)
    data_agent = create_data_agent(model_client)

    # Create query agent for user-facing data analysis
    query_agent = create_query_agent(model_client)

    # Create planning agent for complex task decomposition
    planning_agent = create_planning_agent(model_client)

    # Create termination conditions:
    # - HandoffTermination: stops when agent hands off to "user"
    # - TextMentionTermination: stops when "TERMINATE" is mentioned
    # - MaxMessageTermination: safety limit to prevent infinite loops
    termination = (
        HandoffTermination(target="user") |
        TextMentionTermination("TERMINATE") |
        MaxMessageTermination(max_messages=20)
    )

    # Create Swarm team with termination condition
    # Note: data_agent is not included in the main team - it runs independently
    # Sub-agents are registered as participants so handoffs can reach them
    team = Swarm(
        participants=[
            planning_agent, ideas_agent, shuttle_agent, coding_agent, desktop_agent, query_agent,
            *ideas_subs, *coding_subs, *desktop_subs,
        ],
        termination_condition=termination,
    )

    # Create bridge
    bridge = VoiceBridge(
        swarm_team=team,
        event_manager=event_manager,
        entry_agent="ideas_agent",
    )

    logger.info("Created VoiceBridge with Swarm team")
    return bridge


__all__ = [
    "VoiceBridge",
    "SwarmResult",
    "create_voice_bridge",
]
