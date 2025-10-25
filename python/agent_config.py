"""
Agent Configuration for Multi-Agent Voice System

Defines the 4 specialized agents, their capabilities, and handoff rules.
"""

import os
from typing import Dict, List, Optional
from dotenv import load_dotenv

load_dotenv()


class AgentConfig:
    """Configuration for a single agent"""

    def __init__(
        self,
        name: str,
        agent_id: str,
        voice_id: str,
        role: str,
        can_handoff_to: List[str],
        tools: List[str]
    ):
        self.name = name
        self.agent_id = agent_id
        self.voice_id = voice_id
        self.role = role
        self.can_handoff_to = can_handoff_to
        self.tools = tools

    def __repr__(self):
        return f"AgentConfig({self.name}, tools={len(self.tools)}, handoffs={len(self.can_handoff_to)})"


class AgentRegistry:
    """Registry of all agents in the system"""

    def __init__(self):
        self.agents: Dict[str, AgentConfig] = {}
        self._load_agents()

    def _load_agents(self):
        """Load agent configurations from environment variables"""

        # Agent definitions
        agent_defs = {
            "ConversationalMemory": {
                "env_var": "AGENT_CONVERSATIONAL_MEMORY",
                "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Rachel
                "role": "Entry point, learns user preferences and routes to specialists",
                "can_handoff_to": ["ProjectManager"],
                "tools": [
                    "handoff_to_agent",
                    "remember_preference",
                    "recall_user_info"
                ]
            },
            "ProjectManager": {
                "env_var": "AGENT_PROJECT_MANAGER",
                "voice_id": "Xb7hH8MSUJpSbSDYk0k2",  # Alice
                "role": "Manages projects, tracks progress, delegates to workers",
                "can_handoff_to": ["DesktopWorker", "ProjectWriter", "ConversationalMemory"],
                "tools": [
                    "handoff_to_agent",
                    "list_projects",
                    "get_project_status",
                    "update_project"
                ]
            },
            "DesktopWorker": {
                "env_var": "AGENT_DESKTOP_WORKER",
                "voice_id": "pNInz6obpgDQGcFmaJgB",  # Adam
                "role": "Executes desktop automation and system commands",
                "can_handoff_to": ["ProjectManager"],
                "tools": [
                    "handoff_to_agent",
                    "scan_desktop",
                    "open_application",
                    "click_element",
                    "type_text",
                    "get_window_info"
                ]
            },
            "ProjectWriter": {
                "env_var": "AGENT_PROJECT_WRITER",
                "voice_id": "ErXwobaYiN019PkySvjV",  # Antoni
                "role": "Writes code, documentation, and project content",
                "can_handoff_to": ["ProjectManager"],
                "tools": [
                    "handoff_to_agent",
                    "write_code",
                    "create_documentation",
                    "update_file",
                    "generate_readme"
                ]
            }
        }

        # Load each agent from environment
        for agent_name, config in agent_defs.items():
            agent_id = os.getenv(config["env_var"])

            if not agent_id:
                print(f"WARNING: {config['env_var']} not set in .env - {agent_name} agent not available")
                continue

            self.agents[agent_name] = AgentConfig(
                name=agent_name,
                agent_id=agent_id,
                voice_id=config["voice_id"],
                role=config["role"],
                can_handoff_to=config["can_handoff_to"],
                tools=config["tools"]
            )

    def get_agent(self, name: str) -> Optional[AgentConfig]:
        """Get agent configuration by name"""
        return self.agents.get(name)

    def get_agent_by_id(self, agent_id: str) -> Optional[AgentConfig]:
        """Get agent configuration by agent ID"""
        for agent in self.agents.values():
            if agent.agent_id == agent_id:
                return agent
        return None

    def list_agents(self) -> List[str]:
        """List all available agent names"""
        return list(self.agents.keys())

    def can_handoff(self, from_agent: str, to_agent: str) -> bool:
        """Check if handoff from one agent to another is allowed"""
        agent = self.get_agent(from_agent)
        if not agent:
            return False
        return to_agent in agent.can_handoff_to

    def get_entry_agent(self) -> Optional[AgentConfig]:
        """Get the entry point agent (Conversational Memory)"""
        return self.get_agent("ConversationalMemory")

    def __repr__(self):
        return f"AgentRegistry(agents={len(self.agents)})"


# Global instance
_registry = None


def get_agent_registry() -> AgentRegistry:
    """Get the global agent registry instance"""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


if __name__ == "__main__":
    # Test the configuration
    registry = get_agent_registry()

    print("=" * 60)
    print("Agent Registry")
    print("=" * 60)
    print()

    for agent_name in registry.list_agents():
        agent = registry.get_agent(agent_name)
        print(f"Agent: {agent.name}")
        print(f"  ID: {agent.agent_id}")
        print(f"  Voice: {agent.voice_id}")
        print(f"  Role: {agent.role}")
        print(f"  Tools: {', '.join(agent.tools)}")
        print(f"  Can handoff to: {', '.join(agent.can_handoff_to)}")
        print()

    print(f"Entry Agent: {registry.get_entry_agent().name}")
