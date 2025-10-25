"""
Conversation Manager for Multi-Agent Voice System

Handles:
- ElevenLabs conversation lifecycle (start, handoff, end)
- Real-time transcript capture
- Context preservation across agent switches
- Supermemory integration for context storage/retrieval
"""

import asyncio
import uuid
from typing import Optional, Dict, List, Callable
from datetime import datetime
from elevenlabs.client import ElevenLabs
from elevenlabs.conversational_ai.conversation import Conversation
from elevenlabs.conversational_ai.default_audio_interface import DefaultAudioInterface

from agent_config import get_agent_registry, AgentConfig
from memory.supermemory_client import SupermemoryClient


class ConversationManager:
    """Manages multi-agent conversations with context preservation"""

    def __init__(
        self,
        api_key: str,
        supermemory_client: SupermemoryClient,
        on_agent_switch: Optional[Callable] = None
    ):
        """
        Initialize conversation manager

        Args:
            api_key: ElevenLabs API key
            supermemory_client: Supermemory client instance
            on_agent_switch: Optional callback when switching agents
        """
        self.client = ElevenLabs(api_key=api_key)
        self.memory = supermemory_client
        self.agent_registry = get_agent_registry()
        self.on_agent_switch = on_agent_switch

        # Current conversation state
        self.session_id = str(uuid.uuid4())
        self.current_agent: Optional[AgentConfig] = None
        self.current_conversation: Optional[Conversation] = None
        self.conversation_history: List[Dict[str, str]] = []

        # Real-time transcript tracking
        self.current_messages: List[Dict[str, str]] = []

    def _on_user_transcript(self, transcript: str):
        """Callback for user speech transcript"""
        print(f"\n[User]: {transcript}")

        self.current_messages.append({
            "role": "user",
            "content": transcript,
            "timestamp": datetime.utcnow().isoformat()
        })

    def _on_agent_response(self, response: str):
        """Callback for agent response"""
        if self.current_agent:
            print(f"\n[{self.current_agent.name}]: {response}")

        self.current_messages.append({
            "role": "assistant",
            "content": response,
            "agent": self.current_agent.name if self.current_agent else "unknown",
            "timestamp": datetime.utcnow().isoformat()
        })

    async def start_conversation(
        self,
        agent_name: Optional[str] = None
    ) -> None:
        """
        Start a conversation with an agent

        Args:
            agent_name: Agent to start with (defaults to entry agent)
        """
        # Get the agent to start with
        if agent_name:
            agent = self.agent_registry.get_agent(agent_name)
        else:
            agent = self.agent_registry.get_entry_agent()

        if not agent:
            raise ValueError(f"Agent not found: {agent_name or 'entry agent'}")

        self.current_agent = agent
        self.current_messages = []

        print(f"\n{'='*60}")
        print(f"Starting conversation with: {agent.name}")
        print(f"Session ID: {self.session_id}")
        print(f"{'='*60}\n")

        # Retrieve context from previous conversations if available
        context = await self._retrieve_context_for_agent(agent.name)

        if context:
            print(f"[Memory] Retrieved {len(context)} previous memories")

        # Create audio interface
        audio_interface = DefaultAudioInterface()

        # Create conversation
        # Note: Client tools will be added in the next iteration
        self.current_conversation = Conversation(
            client=self.client,
            agent_id=agent.agent_id,
            requires_auth=False,
            audio_interface=audio_interface,
            # callback_user_transcript=self._on_user_transcript,
            # callback_agent_response=self._on_agent_response,
        )

        # Start the conversation
        await self.current_conversation.start_session()

        print(f"[{agent.name}] Conversation started - speak to interact")
        print("Press Ctrl+C to end conversation")
        print()

    async def handoff_to_agent(
        self,
        target_agent_name: str,
        context_message: Optional[str] = None
    ) -> None:
        """
        Hand off conversation to another agent

        Args:
            target_agent_name: Name of the target agent
            context_message: Optional context to pass to the new agent
        """
        if not self.current_agent:
            raise ValueError("No active conversation to hand off")

        # Check if handoff is allowed
        if not self.agent_registry.can_handoff(
            self.current_agent.name,
            target_agent_name
        ):
            raise ValueError(
                f"Handoff from {self.current_agent.name} to {target_agent_name} not allowed"
            )

        target_agent = self.agent_registry.get_agent(target_agent_name)
        if not target_agent:
            raise ValueError(f"Target agent not found: {target_agent_name}")

        print(f"\n{'='*60}")
        print(f"Handing off conversation:")
        print(f"  From: {self.current_agent.name}")
        print(f"  To: {target_agent.name}")
        print(f"{'='*60}\n")

        # Store current conversation in Supermemory
        await self._store_conversation_context(
            handoff_to=target_agent_name,
            context_message=context_message
        )

        # End current conversation
        if self.current_conversation:
            await self.current_conversation.end_session()
            self.current_conversation = None

        # Notify about agent switch
        if self.on_agent_switch:
            self.on_agent_switch(self.current_agent.name, target_agent_name)

        # Start new conversation with target agent
        await self.start_conversation(target_agent_name)

    async def end_conversation(self) -> str:
        """
        End the current conversation

        Returns:
            Conversation ID
        """
        conversation_id = None

        if self.current_conversation:
            print(f"\n{'='*60}")
            print("Ending conversation...")
            print(f"{'='*60}\n")

            # Store final conversation state
            await self._store_conversation_context()

            # End the conversation
            await self.current_conversation.end_session()
            # conversation_id = self.current_conversation.get_conversation_id()

            self.current_conversation = None
            self.current_agent = None

        return conversation_id or "unknown"

    async def _store_conversation_context(
        self,
        handoff_to: Optional[str] = None,
        context_message: Optional[str] = None
    ):
        """Store current conversation context in Supermemory"""
        if not self.current_agent:
            return

        # Add context message if provided
        if context_message:
            self.current_messages.append({
                "role": "system",
                "content": f"Handoff context: {context_message}",
                "timestamp": datetime.utcnow().isoformat()
            })

        # Store in Supermemory
        try:
            self.memory.store_conversation(
                session_id=self.session_id,
                agent_name=self.current_agent.name,
                messages=self.current_messages,
                handoff_to=handoff_to
            )
            print(f"[Memory] Stored conversation with {self.current_agent.name}")

        except Exception as e:
            print(f"[Memory] Error storing conversation: {e}")

        # Add to overall conversation history
        self.conversation_history.extend(self.current_messages)

    async def _retrieve_context_for_agent(
        self,
        agent_name: str
    ) -> List[Dict[str, any]]:
        """Retrieve relevant context for an agent from Supermemory"""
        try:
            # Get conversation history
            history = self.memory.get_conversation_history(self.session_id)

            # Get user preferences
            preferences = self.memory.get_user_preferences(self.session_id)

            # Get projects if applicable
            projects = self.memory.get_projects(self.session_id)

            context = []

            if history:
                context.append({
                    "type": "conversation_history",
                    "data": history
                })

            if preferences:
                context.append({
                    "type": "user_preferences",
                    "data": preferences
                })

            if projects:
                context.append({
                    "type": "projects",
                    "data": projects
                })

            return context

        except Exception as e:
            print(f"[Memory] Error retrieving context: {e}")
            return []


# Test functionality
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    load_dotenv()

    async def test_conversation_manager():
        print("=" * 60)
        print("Conversation Manager Test")
        print("=" * 60)
        print()

        api_key = os.getenv("ELEVENLABS_API_KEY")
        memory_client = SupermemoryClient()

        manager = ConversationManager(
            api_key=api_key,
            supermemory_client=memory_client,
            on_agent_switch=lambda from_agent, to_agent: print(
                f"[Manager] Switching from {from_agent} to {to_agent}"
            )
        )

        print(f"Session ID: {manager.session_id}")
        print(f"Entry Agent: {manager.agent_registry.get_entry_agent().name}")
        print()

        print("Test completed - manager initialized successfully")

    asyncio.run(test_conversation_manager())
