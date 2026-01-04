"""
VibeMind Multiverse Spaces

Verschiedene Spaces im Multiverse:
- Ideas Space (Rachel's Bubbles) - Ideen-Verwaltung
- Desktop Automation Space (Adam's Workspace) - Desktop-Kontrolle
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Dict, Any


class SpaceType(Enum):
    """Verfügbare Space-Typen im Multiverse."""
    IDEAS = "ideas"
    DESKTOP_AUTOMATION = "desktop_automation"
    # Zukünftige Spaces:
    # CODING_WORKSHOP = "coding_workshop"  # Antoni's Space
    # PROJECT_HUB = "project_hub"  # Alice's Space


@dataclass
class SpaceConfig:
    """Konfiguration für einen Multiverse-Space."""
    type: SpaceType
    name: str
    description: str
    position: Dict[str, float]  # x, y, z im 3D-Raum
    agent_slug: Optional[str] = None  # Zuständiger Agent
    color: int = 0x4488ff  # Hex-Farbe
    visualization: str = "bubble"  # bubble, planet, nebula, etc.
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


# Space-Definitionen
SPACES = {
    SpaceType.IDEAS: SpaceConfig(
        type=SpaceType.IDEAS,
        name="Ideas Universe",
        description="Rachels Ideen-Bubbles - Sammlung und Organisation von Ideen",
        position={"x": 0, "y": 0, "z": 0},
        agent_slug="rachel",
        color=0x4488ff,
        visualization="bubbles",
        metadata={
            "entry_point": True,
            "allows_creation": True,
        }
    ),
    SpaceType.DESKTOP_AUTOMATION: SpaceConfig(
        type=SpaceType.DESKTOP_AUTOMATION,
        name="Desktop Automation Space",
        description="Adams Desktop-Kontrolle - System-Operationen und App-Steuerung",
        position={"x": 10, "y": 0, "z": -5},  # Weiter entfernt im Raum
        agent_slug="adam",
        color=0xff8844,  # Warmes Orange
        visualization="light_planet",  # Spezieller Licht-Planet
        metadata={
            "entry_point": False,
            "requires_hand_motion": True,
            "planet_config": {
                "core_intensity": 1.0,
                "pulsation_speed": 0.5,
                "gravity_effect": True,
            }
        }
    ),
}


def get_space(space_type: SpaceType) -> Optional[SpaceConfig]:
    """Hole Space-Konfiguration nach Typ."""
    return SPACES.get(space_type)


def get_all_spaces():
    """Hole alle Space-Konfigurationen."""
    return list(SPACES.values())


def get_space_by_agent(agent_slug: str) -> Optional[SpaceConfig]:
    """Hole Space-Konfiguration nach zuständigem Agent."""
    for space in SPACES.values():
        if space.agent_slug == agent_slug:
            return space
    return None


__all__ = [
    "SpaceType",
    "SpaceConfig",
    "SPACES",
    "get_space",
    "get_all_spaces",
    "get_space_by_agent",
]