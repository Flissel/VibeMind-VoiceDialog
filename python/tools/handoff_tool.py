"""
Handoff Tool for Multi-Agent Voice System

This tool is registered with all ElevenLabs agents to enable
agent-to-agent handoffs during voice conversations.
"""

from typing import Dict, Any, Optional
from agent_config import get_agent_registry


class HandoffTool:
    """Tool for handing off conversations between agents"""

    def __init__(self, conversation_manager):
        """
        Initialize handoff tool

        Args:
            conversation_manager: ConversationManager instance
        """
        self.conversation_manager = conversation_manager
        self.agent_registry = get_agent_registry()

    def get_schema(self) -> Dict[str, Any]:
        """
        Get JSON schema for the handoff tool

        This schema is used by ElevenLabs to understand how to call this tool.
        """
        return {
            "type": "function",
            "function": {
                "name": "handoff_to_agent",
                "description": "Transfer the conversation to another specialist agent. Use this when the user's request requires expertise from a different agent.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_agent": {
                            "type": "string",
                            "description": "The specialist agent to hand off to",
                            "enum": [
                                "ConversationalMemory",
                                "ProjectManager",
                                "DesktopWorker",
                                "ProjectWriter"
                            ]
                        },
                        "reason": {
                            "type": "string",
                            "description": "Brief explanation of why you're handing off (what the user needs help with)"
                        },
                        "context": {
                            "type": "string",
                            "description": "Important context the next agent should know (user's request, preferences, etc.)"
                        }
                    },
                    "required": ["target_agent", "reason", "context"]
                }
            }
        }

    async def execute(
        self,
        target_agent: str,
        reason: str,
        context: str
    ) -> Dict[str, Any]:
        """
        Execute the handoff to another agent

        Args:
            target_agent: Name of the target agent
            reason: Why we're handing off
            context: Context to pass to the new agent

        Returns:
            Result dict with handoff status
        """
        try:
            # Validate target agent exists
            target = self.agent_registry.get_agent(target_agent)
            if not target:
                return {
                    "status": "error",
                    "message": f"Agent '{target_agent}' not found"
                }

            # Check if handoff is allowed
            current_agent_name = self.conversation_manager.current_agent.name
            if not self.agent_registry.can_handoff(current_agent_name, target_agent):
                return {
                    "status": "error",
                    "message": f"Handoff from {current_agent_name} to {target_agent} not allowed"
                }

            # Prepare handoff message
            handoff_message = f"Reason: {reason}\nContext: {context}"

            # Execute the handoff
            await self.conversation_manager.handoff_to_agent(
                target_agent_name=target_agent,
                context_message=handoff_message
            )

            return {
                "status": "success",
                "message": f"Successfully handed off to {target_agent}",
                "target_agent": target_agent,
                "target_voice": target.voice_id
            }

        except Exception as e:
            return {
                "status": "error",
                "message": f"Handoff failed: {str(e)}"
            }


def create_handoff_function(conversation_manager):
    """
    Create a handoff function that can be registered with ElevenLabs ClientTools

    Args:
        conversation_manager: ConversationManager instance

    Returns:
        Callable function for client tools
    """
    tool = HandoffTool(conversation_manager)

    async def handoff_to_agent(params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handoff function for ElevenLabs ClientTools

        Args:
            params: Parameters from ElevenLabs (target_agent, reason, context)

        Returns:
            Result dict
        """
        target_agent = params.get("target_agent")
        reason = params.get("reason", "User requested")
        context = params.get("context", "No additional context provided")

        if not target_agent:
            return {
                "status": "error",
                "message": "target_agent parameter is required"
            }

        result = await tool.execute(
            target_agent=target_agent,
            reason=reason,
            context=context
        )

        return result

    return handoff_to_agent, tool.get_schema()


# Example usage and documentation
if __name__ == "__main__":
    print("=" * 60)
    print("Handoff Tool Schema")
    print("=" * 60)
    print()

    # Create a mock conversation manager for testing
    class MockManager:
        class Agent:
            name = "ConversationalMemory"

        current_agent = Agent()

    tool = HandoffTool(MockManager())
    schema = tool.get_schema()

    import json
    print(json.dumps(schema, indent=2))
    print()

    print("=" * 60)
    print("Usage in ElevenLabs Dashboard")
    print("=" * 60)
    print()
    print("When configuring client tools in ElevenLabs dashboard:")
    print("1. Tool Name: handoff_to_agent")
    print("2. Description: Transfer conversation to another specialist agent")
    print("3. Parameters schema: (use JSON above)")
    print()
    print("The agent will automatically call this tool when it detects")
    print("that the user's request requires another specialist.")
    print()
    print("Example scenarios:")
    print("  - User asks about projects → handoff to ProjectManager")
    print("  - User wants to open an app → handoff to DesktopWorker")
    print("  - User wants code written → handoff to ProjectWriter")
