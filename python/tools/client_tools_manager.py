"""
Client Tools Manager
Manages registration and routing of ElevenLabs client tools to specialized agents
"""

from typing import Dict, Any, Callable
from elevenlabs.conversational_ai.conversation import ClientTools


class ClientToolsManager:
    """
    Manages the registration and routing of client tools to specialized agents.

    This class acts as a bridge between the ElevenLabs Conversation SDK and
    the specialized agent system. When the ElevenLabs agent calls a client tool,
    this manager routes it to the appropriate Python agent for execution.
    """

    def __init__(self):
        """Initialize the Client Tools Manager"""
        self.client_tools = ClientTools()
        self.agents: Dict[str, Any] = {}
        self.tool_registry: Dict[str, str] = {}
        print("[ClientToolsManager] Initialized")

    def register_agent(self, agent_name: str, agent_instance: Any) -> None:
        """
        Register a specialized agent

        Args:
            agent_name: Unique name for the agent (e.g., "research", "code")
            agent_instance: Instance of the agent class
        """
        self.agents[agent_name] = agent_instance
        print(f"[ClientToolsManager] Registered agent: {agent_name} ({type(agent_instance).__name__})")

    def register_tool(self, tool_name: str, agent_name: str, is_async: bool = False) -> None:
        """
        Register a client tool that maps to an agent

        Args:
            tool_name: Name of the tool (must match ElevenLabs dashboard config)
            agent_name: Name of the agent to route this tool to
            is_async: Whether the tool function is async

        Raises:
            ValueError: If agent_name is not registered
        """
        if agent_name not in self.agents:
            raise ValueError(f"Agent '{agent_name}' not registered. Register it first using register_agent()")

        # Create a tool function that routes to the agent
        tool_func = self._create_tool_function(tool_name, agent_name)

        # Register with ElevenLabs ClientTools
        self.client_tools.register(tool_name, tool_func, is_async=is_async)

        # Store in our registry
        self.tool_registry[tool_name] = agent_name

        print(f"[ClientToolsManager] Registered tool: '{tool_name}' -> {agent_name}")

    def _create_tool_function(self, tool_name: str, agent_name: str) -> Callable:
        """
        Create a tool function that routes calls to an agent

        Args:
            tool_name: Name of the tool
            agent_name: Name of the agent to route to

        Returns:
            Callable function that executes the agent
        """
        def tool_function(params: Dict[str, Any]) -> Dict[str, Any]:
            """
            Tool function executed when ElevenLabs agent calls this tool

            Args:
                params: Parameters from the tool call

            Returns:
                Results dictionary to send back to the agent
            """
            agent = self.agents.get(agent_name)
            if not agent:
                error_msg = f"Agent '{agent_name}' not found for tool '{tool_name}'"
                print(f"[ClientToolsManager] ERROR: {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg
                }

            try:
                print(f"[ClientToolsManager] Executing tool '{tool_name}' via {agent_name}")
                print(f"[ClientToolsManager] Parameters: {params}")

                # Execute the agent
                result = agent.execute(params)

                print(f"[ClientToolsManager] Tool '{tool_name}' executed successfully")
                return result

            except Exception as e:
                error_msg = f"Error executing tool '{tool_name}': {str(e)}"
                print(f"[ClientToolsManager] ERROR: {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg,
                    "exception_type": type(e).__name__
                }

        return tool_function

    def get_client_tools(self) -> ClientTools:
        """
        Get the ClientTools instance for use in Conversation

        Returns:
            ClientTools instance with all registered tools
        """
        return self.client_tools

    def list_registered_tools(self) -> Dict[str, str]:
        """
        Get a dictionary of all registered tools and their agents

        Returns:
            Dictionary mapping tool names to agent names
        """
        return dict(self.tool_registry)

    def __str__(self) -> str:
        return f"ClientToolsManager(agents={len(self.agents)}, tools={len(self.tool_registry)})"
