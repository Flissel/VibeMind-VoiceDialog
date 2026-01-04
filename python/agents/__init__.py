"""
VibeMind Multi-Agent System - Agent Registry

Lädt und verwaltet alle Agenten:
- Rachel (Multiverse Navigator) - Entry Agent
- Alice (Coordinator Hub)
- Adam (Desktop Worker)
- Antoni (Coding/Writing Worker)
"""

import os
from pathlib import Path
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from dotenv import load_dotenv

# Load .env from parent directory
env_path = Path(__file__).parent.parent.parent / ".env"
load_dotenv(env_path)

# Import agent modules
from . import rachel
from . import alice
from . import adam
from . import antoni

# Legacy import für Kompatibilität
from .voice_orchestrator import VoiceOrchestratorAgent


@dataclass
class AgentInfo:
    """Information über einen Agenten."""
    name: str
    slug: str
    module: Any
    config: Dict[str, Any]
    voice_id: str
    is_entry_agent: bool = False
    has_fixed_space: bool = False
    space_name: Optional[str] = None


class AgentRegistry:
    """Registry für alle verfügbaren Agenten."""
    
    def __init__(self):
        self._agents: Dict[str, AgentInfo] = {}
        self._load_agents()
    
    def _load_agents(self):
        """Lade alle Agent-Module."""
        agent_modules = [
            ("rachel", rachel),
            ("alice", alice),
            ("adam", adam),
            ("antoni", antoni),
        ]
        
        for slug, module in agent_modules:
            config = module.AGENT_CONFIG
            self._agents[slug] = AgentInfo(
                name=config["name"],
                slug=slug,
                module=module,
                config=config,
                voice_id=config["voice_id"],
                is_entry_agent=config.get("is_entry_agent", False),
                has_fixed_space=config.get("has_fixed_space", False),
                space_name=config.get("space_name"),
            )
            print(f"[AgentRegistry] Loaded: {config['name']} ({slug})")
    
    def get(self, slug: str) -> Optional[AgentInfo]:
        """Hole Agent-Info nach Slug."""
        return self._agents.get(slug)
    
    def get_by_name(self, name: str) -> Optional[AgentInfo]:
        """Hole Agent-Info nach Name."""
        for agent in self._agents.values():
            if agent.name.lower() == name.lower():
                return agent
        return None
    
    def get_entry_agent(self) -> Optional[AgentInfo]:
        """Hole den Entry-Agent (Rachel)."""
        for agent in self._agents.values():
            if agent.is_entry_agent:
                return agent
        return None
    
    def get_all(self) -> List[AgentInfo]:
        """Hole alle Agenten."""
        return list(self._agents.values())
    
    def get_agents_with_fixed_space(self) -> List[AgentInfo]:
        """Hole alle Agenten mit festem Space (für Auto-Erstellung)."""
        return [a for a in self._agents.values() if a.has_fixed_space]
    
    def get_agent_id(self, slug: str) -> Optional[str]:
        """Hole ElevenLabs Agent-ID aus .env."""
        agent = self.get(slug)
        if not agent:
            return None
        
        # Versuche Agent-ID aus Modul zu holen
        try:
            return agent.module.config.get_agent_id()
        except (AttributeError, ValueError):
            # Fallback auf env vars
            env_map = {
                "rachel": ["RACHEL_AGENT_ID", "AGENT_MULTIVERSE"],
                "alice": ["ALICE_AGENT_ID", "AGENT_PROJECT_MANAGER"],
                "adam": ["ADAM_AGENT_ID", "AGENT_DESKTOP_WORKER"],
                "antoni": ["ANTONI_AGENT_ID", "AGENT_PROJECT_WRITER"],
            }
            for env_var in env_map.get(slug, []):
                agent_id = os.getenv(env_var)
                if agent_id:
                    return agent_id
            return None
    
    def get_tools(self, slug: str) -> Dict[str, Any]:
        """Hole alle Tools eines Agenten."""
        agent = self.get(slug)
        if not agent:
            return {}
        return agent.module.get_tools()
    
    def get_tool_definitions(self, slug: str) -> List[Dict[str, Any]]:
        """Hole Tool-Definitionen für ElevenLabs."""
        agent = self.get(slug)
        if not agent:
            return []
        return agent.module.get_tool_definitions()
    
    def register_agent_tools(self, slug: str, client_tools) -> None:
        """Registriere alle Tools eines Agenten beim ClientTools-Manager."""
        agent = self.get(slug)
        if agent:
            agent.module.tools.register_tools(client_tools)
    
    def __repr__(self):
        return f"AgentRegistry(agents={list(self._agents.keys())})"


# Singleton-Instanz
_registry: Optional[AgentRegistry] = None


def get_registry() -> AgentRegistry:
    """Hole die globale Agent-Registry."""
    global _registry
    if _registry is None:
        _registry = AgentRegistry()
    return _registry


def get_agent(slug: str) -> Optional[AgentInfo]:
    """Shortcut: Hole Agent nach Slug."""
    return get_registry().get(slug)


def get_entry_agent() -> Optional[AgentInfo]:
    """Shortcut: Hole Entry-Agent."""
    return get_registry().get_entry_agent()


# Exports
__all__ = [
    "AgentRegistry",
    "AgentInfo",
    "get_registry",
    "get_agent",
    "get_entry_agent",
    # Agent-Module
    "rachel",
    "alice", 
    "adam",
    "antoni",
    # Legacy
    "VoiceOrchestratorAgent",
]


if __name__ == "__main__":
    # Test
    registry = get_registry()
    print("\n" + "="*60)
    print("Agent Registry")
    print("="*60)
    
    for agent in registry.get_all():
        print(f"\n{agent.name} ({agent.slug})")
        print(f"  Voice: {agent.voice_id}")
        print(f"  Entry Agent: {agent.is_entry_agent}")
        print(f"  Fixed Space: {agent.has_fixed_space}")
        if agent.space_name:
            print(f"  Space Name: {agent.space_name}")
        print(f"  Agent-ID: {registry.get_agent_id(agent.slug)}")
    
    print(f"\nEntry Agent: {registry.get_entry_agent()}")
