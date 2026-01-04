"""
MoireTracker v2 Agents Module

Enthält alle spezialisierten Agenten:
- InteractionAgent: Desktop-Automation via PyAutoGUI
- OrchestratorV2: Event-driven Task-Koordination
- ReasoningAgent: Task-Planung mit Vision
- VisionAgent: Element-Lokalisierung
- DataAnalystAgent: UI-Daten Strukturierung
- MonitorAgent: Bildschirm-Überwachung
"""

from .interaction import InteractionAgent, get_interaction_agent
from .reasoning import ReasoningAgent, get_reasoning_agent

# Lazy imports für optionale Agenten
__all__ = [
    "InteractionAgent",
    "get_interaction_agent",
    "ReasoningAgent", 
    "get_reasoning_agent",
]

# Optional imports
def get_orchestrator():
    """Lazy import für OrchestratorV2."""
    from .orchestrator_v2 import OrchestratorV2
    return OrchestratorV2

def get_vision_agent():
    """Lazy import für VisionAgent."""
    from .vision_agent import VisionAnalystAgent, get_vision_agent as _get
    return _get()

def get_data_analyst():
    """Lazy import für DataAnalystAgent."""
    from .data_analyst import DataAnalystAgent, get_data_analyst as _get
    return _get()

def get_monitor_agent():
    """Lazy import für MonitorAgent."""
    from .monitor import MonitorAgent, get_monitor_agent as _get
    return _get()